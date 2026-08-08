import {
  clear,
  create,
  createLoading,
  createSlider,
} from "../utils/elements.js";
import { multiSeriesView } from "../utils/plot.js";
import { downloadBlob, toCsv } from "../utils/export.js";
import { complete } from "../pipeline.js";

/*********/
/* model */
/*********/

// objective / transformation / algorithm option lists; the ids are the values
// sent verbatim on the wire
const objectives = [
  { id: "rmse", label: "RMSE" },
  { id: "nse", label: "NSE" },
  { id: "kge", label: "KGE" },
];
const transformations = [
  { id: "none", label: "None" },
  { id: "log", label: "Log" },
  { id: "sqrt", label: "Sqrt" },
];
const algorithms = [
  { id: "manual", label: "Manual" },
  { id: "sce", label: "SCE" },
];

// display names mirror the model step; kept local since that list is not
// exported and this step must not touch it
const modelLabels = {
  gr4j: "GR4J",
  bucket: "Bucket",
  cequeau: "CEQUEAU",
  crec: "CREC",
  gardenia: "Gardénia",
  hbv: "HBV",
  hymod: "HYMOD",
  ihacres: "IHACRES",
  martine: "Martine",
  mohyse: "MOHYSE",
  mordor: "MORDOR",
  nam: "NAM",
  pdm: "PDM",
  sacramento: "Sacramento",
  simhyd: "SIMHYD",
  smar: "SMAR",
  tank: "Tank",
  topmodel: "TOPMODEL",
  wageningen: "Wageningen",
  xinanjiang: "Xinanjiang",
};

// import-dialog labels for the config keys an import can replace
const configLabels = {
  calibrationStation: "Calibration station",
  calibrationPeriod: "Calibration period",
  weatherMethod: "Weather method",
  weatherNStations: "Weather stations",
  snowModel: "Snow model",
  hydroModels: "Models",
};

// what survives a reload: the settings, the fitted parameters and the objective
// history. `series` and `info` are request caches and `calibrating` tracks
// server threads that died with the page, so all three restart empty.
// a bench worth keeping longer than that is exported to a JSON file and
// imported back (the Import button), not filed in localStorage

// saved values are validated rather than trusted, since a stale or hand-edited
// localStorage would otherwise put a <select> in a state with no matching
// <option> and send an unknown id on the wire
const defaultSettings = {
  objective: "rmse",
  transformation: "none",
  algorithm: "manual",
  warmupYears: 3,
  // seeded from the server's defaults on the first calibration_info reply
  algorithmParams: null,
};

export function initCalibration(saved, config) {
  const stored = saved && typeof saved === "object" ? saved : {};
  const base = {
    info: null,
    series: null,
    contextKey: null,
    // the data context the stored attempts were fitted under. `series` cannot
    // serve: it is nulled on restore and again by Connected, while this must
    // stay pinned to the history for as long as the history exists
    dataKey: null,
    settings: initSettings(stored.settings ?? null),
    draft: {},
    attempts: {},
    simulations: {},
    calibrating: {},
    requestIds: {},
    // requests whose reply must not add a point to the objective history
    silentIds: {},
    runId: 0,
    hover: null,
    // the import modal's content: {message} for a bad file, {imported,
    // changed} while a config replacement awaits confirmation
    importDialog: null,
  };
  // a fit and its objectives only describe the context that produced them, so
  // both are dropped unless the restored config still matches. the two halves
  // are checked here rather than relying on GetSeries, because a reload landing
  // inside the write-coalescing window can save a config the pending bench has
  // already been invalidated by
  const context = contextKey(config);
  const data = seriesKey(config, base.settings);
  if (stored.contextKey !== context || stored.dataKey !== data) {
    return base;
  }
  return {
    ...base,
    contextKey: context,
    dataKey: data,
    draft: numberArrayMap(stored.draft),
    attempts: attemptsMap(stored.attempts),
  };
}

// { model: [{params, objectives}, …] }; an attempt missing either field would
// crash the chart builders, which index both without checking
function attemptsMap(stored) {
  if (!stored || typeof stored !== "object") {
    return {};
  }
  const out = {};
  for (const [m, list] of Object.entries(stored)) {
    if (!Array.isArray(list)) {
      continue;
    }
    const valid = list.filter(
      (a) =>
        a &&
        Array.isArray(a.params) &&
        a.objectives &&
        typeof a.objectives === "object",
    );
    if (valid.length) {
      out[m] = valid;
    }
  }
  return out;
}

// { model: [number, …] }, dropping anything that is not exactly that
function numberArrayMap(stored) {
  if (!stored || typeof stored !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(stored).filter(
      ([, v]) => Array.isArray(v) && v.every(Number.isFinite),
    ),
  );
}

function initSettings(saved) {
  if (saved === null || typeof saved !== "object") {
    return { ...defaultSettings };
  }
  return {
    ...defaultSettings,
    objective: pickOption(objectives, saved.objective, "objective"),
    transformation: pickOption(
      transformations,
      saved.transformation,
      "transformation",
    ),
    algorithm: pickOption(algorithms, saved.algorithm, "algorithm"),
    // clamped to the slider's 0–5 range, since older saves allowed any value
    warmupYears: Number.isInteger(saved.warmupYears)
      ? Math.min(Math.max(saved.warmupYears, 0), 5)
      : defaultSettings.warmupYears,
    // the hyperparameter names and ranges come from the server, so they cannot
    // be checked here; a bad value is clamped by the number input's min/max
    algorithmParams:
      saved.algorithmParams && typeof saved.algorithmParams === "object"
        ? saved.algorithmParams
        : null,
  };
}

function pickOption(options, value, key) {
  return options.some((o) => o.id === value) ? value : defaultSettings[key];
}

/**********/
/* update */
/**********/

export function update(model, msg, dispatch) {
  switch (msg.type) {
    case "calibration/GetInfo": {
      const cal = model.calibration;
      // guard so a disconnected socket or an in-flight request doesn't spin
      // the dispatch queue; "pending" marks the request until the reply lands
      if (cal.info || model.ws?.readyState !== WebSocket.OPEN) {
        return model;
      }
      model.ws.send(JSON.stringify({ type: "calibration_info" }));
      return { ...model, calibration: { ...cal, info: "pending" } };
    }
    case "calibration/GotInfo": {
      const cal = model.calibration;
      const info = msg.data;
      // seed the SCE hyperparameters from their defaults on first load only,
      // so a user's edits survive a reconnect that re-requests the info
      const settings = cal.settings.algorithmParams
        ? cal.settings
        : { ...cal.settings, algorithmParams: sceDefaults(info) };
      // seed default hydro parameters for every selected model still missing a
      // draft; existing drafts (edited or streamed) are left untouched
      const draft = { ...cal.draft };
      for (const m of model.config.hydroModels ?? []) {
        if (!draft[m] && info.hydro?.[m]) {
          draft[m] = info.hydro[m].map((p) => p.default);
        }
      }
      return { ...model, calibration: { ...cal, info, settings, draft } };
    }
    case "calibration/GetSeries": {
      const cal = model.calibration;
      const key = seriesKey(model.config, cal.settings);
      if (key === null || cal.series?.key === key) {
        return model;
      }
      const params = seriesParams(model.config, cal.settings);
      if (model.ws?.readyState === WebSocket.OPEN) {
        // a context change mid-run also stops the server threads: their
        // frames now carry a stale runId and would be dropped anyway, so
        // without the stop the done frame that clears the busy flags never
        // lands
        if (Object.values(cal.calibrating).some(Boolean)) {
          model.ws.send(JSON.stringify({ type: "calibration_stop" }));
        }
        model.ws.send(JSON.stringify({ type: "calibration_data", ...params }));
      }
      // a *changed* data context invalidates every stored history (objectives
      // computed on a different period are incomparable) but leaves the draft
      // params. a null series is not a change: it is the first load of the
      // page or a reconnect, where the restored bench still describes this
      // very request, so the history has to survive it
      const changed = cal.series !== null;
      if (changed) {
        dropParams(model, dispatch);
      }
      // the key is recorded even when the send is skipped so the view stops
      // re-dispatching; Connected clears a data:null series to retry it
      return {
        ...model,
        calibration: {
          ...cal,
          series: { key, qnbv: null, data: null },
          // moves with the history it describes, in the same transition
          dataKey: key,
          attempts: changed ? {} : cal.attempts,
          simulations: changed ? {} : cal.simulations,
          // cleared with the simulations so simulateOnView re-runs each model
          // against the new period; an in-flight reply now matches no id and
          // is dropped by GotResult, which is what it should be
          requestIds: changed ? {} : cal.requestIds,
          silentIds: changed ? {} : cal.silentIds,
          calibrating: {},
          runId: cal.runId + 1,
        },
      };
    }
    case "calibration/ContextChanged": {
      // a snow-model change invalidates every objective (the forcings the
      // models saw are different); a hydroModels change restarts the bench so
      // the objective plot always reads as one run of the current ensemble
      const cal = model.calibration;
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        Object.values(cal.calibrating).some(Boolean)
      ) {
        model.ws.send(JSON.stringify({ type: "calibration_stop" }));
      }
      dropParams(model, dispatch);
      return {
        ...model,
        calibration: {
          ...cal,
          contextKey: contextKey(model.config),
          attempts: {},
          simulations: {},
          // as in GetSeries: cleared with the simulations so simulateOnView
          // re-runs every model under the new snow model / ensemble
          requestIds: {},
          silentIds: {},
          calibrating: {},
          runId: cal.runId + 1,
        },
      };
    }
    case "calibration/GotSeries": {
      const cal = model.calibration;
      const key = seriesKey(model.config, cal.settings);
      // drop a superseded reply: the echoed request must match the live key
      const echoed = `${msg.data.station}|${msg.data.start}|${msg.data.end}|${msg.data.method}|${msg.data.n_stations}|${msg.data.warmupYears}`;
      if (echoed !== key) {
        return model;
      }
      // convert the date grid once on arrival
      const dates = msg.data.data.map((d) => new Date(d.datetime * 1000));
      const observations = msg.data.data.map((d) => d.streamflow);
      return {
        ...model,
        calibration: {
          ...cal,
          series: { key, qnbv: msg.data.qnbv, data: { dates, observations } },
        },
      };
    }
    case "calibration/SetSetting": {
      const cal = model.calibration;
      const { key, value } = msg.data;
      const settings = { ...cal.settings, [key]: value };
      // transformation and warmup change how the objectives are computed, so
      // the stored histories become incomparable; the objective choice only
      // re-reads an already-stored metric, so it keeps them
      const invalidates = key === "transformation" || key === "warmupYears";
      // an active run must end when its frames would report objectives from
      // the old settings, or when switching to manual hides the Stop button
      const stops = invalidates || (key === "algorithm" && value === "manual");
      if (
        stops &&
        model.ws?.readyState === WebSocket.OPEN &&
        Object.values(cal.calibrating).some(Boolean)
      ) {
        model.ws.send(JSON.stringify({ type: "calibration_stop" }));
      }
      if (invalidates) {
        dropParams(model, dispatch);
      }
      return {
        ...model,
        calibration: {
          ...cal,
          settings,
          attempts: invalidates ? {} : cal.attempts,
          simulations: invalidates ? {} : cal.simulations,
          calibrating: stops ? {} : cal.calibrating,
          runId: stops ? cal.runId + 1 : cal.runId,
        },
      };
    }
    case "calibration/SetAlgorithmParam": {
      const cal = model.calibration;
      const { name, value } = msg.data;
      return {
        ...model,
        calibration: {
          ...cal,
          settings: {
            ...cal.settings,
            algorithmParams: { ...cal.settings.algorithmParams, [name]: value },
          },
        },
      };
    }
    case "calibration/SetParam": {
      const cal = model.calibration;
      const { model: target, index, value } = msg.data;
      const current = cal.draft[target] ?? defaultParams(cal.info, target);
      const next = [...current];
      next[index] = value;
      return {
        ...model,
        calibration: { ...cal, draft: { ...cal.draft, [target]: next } },
      };
    }
    case "calibration/Simulate": {
      const cal = model.calibration;
      const { model: target, silent } = msg.data;
      if (model.ws?.readyState !== WebSocket.OPEN || !cal.series?.data) {
        return model;
      }
      // a new id supersedes any earlier manual reply for this model
      const requestId = (cal.requestIds[target] ?? 0) + 1;
      const params = cal.draft[target] ?? defaultParams(cal.info, target);
      model.ws.send(
        JSON.stringify({
          type: "calibration_manual",
          ...seriesParams(model.config, cal.settings),
          hydroModel: target,
          snowModel: model.config.snowModel,
          hydroParams: params.map(Number),
          transformation: cal.settings.transformation,
          requestId,
        }),
      );
      return {
        ...model,
        calibration: {
          ...cal,
          requestIds: { ...cal.requestIds, [target]: requestId },
          // a silent run redraws the simulation without adding a point to the
          // objective history; the id is recorded so only *this* reply is
          // silent, and a slider moved before it lands still counts normally
          silentIds: silent
            ? { ...cal.silentIds, [target]: requestId }
            : cal.silentIds,
        },
      };
    }
    case "calibration/GotResult": {
      const cal = model.calibration;
      const { hydroModel, requestId } = msg.data;
      // drop a superseded manual reply, or one that outlived its data context
      if (requestId !== cal.requestIds[hydroModel] || !cal.series?.data) {
        return model;
      }
      // the reload re-run reproduces a fit the history already records, so it
      // contributes the simulation and nothing else — unless this model has no
      // history, where its objective is the only one there is and dropping it
      // would leave the plot with a simulation and no score for it
      const silent =
        cal.silentIds[hydroModel] === requestId &&
        (cal.attempts[hydroModel]?.length ?? 0) > 0;
      const next = {
        ...model,
        calibration: {
          ...cal,
          attempts: silent
            ? cal.attempts
            : appendAttempt(cal.attempts, hydroModel, msg.data),
          simulations: {
            ...cal.simulations,
            [hydroModel]: msg.data.simulation,
          },
        },
      };
      return maybeComplete(next, dispatch);
    }
    case "calibration/Start": {
      const cal = model.calibration;
      if (
        model.ws?.readyState !== WebSocket.OPEN ||
        !cal.series?.data ||
        !isInfoLoaded(cal.info)
      ) {
        return model;
      }
      const runId = cal.runId + 1;
      const models = model.config.hydroModels ?? [];
      const calibrating = {};
      for (const m of models) {
        calibrating[m] = true;
      }
      model.ws.send(
        JSON.stringify({
          type: "calibration_start",
          ...seriesParams(model.config, cal.settings),
          hydroModels: models,
          snowModel: model.config.snowModel,
          objective: cal.settings.objective,
          transformation: cal.settings.transformation,
          algorithm: cal.settings.algorithm,
          algorithmParams: cal.settings.algorithmParams,
          runId,
        }),
      );
      return { ...model, calibration: { ...cal, runId, calibrating } };
    }
    case "calibration/Stop": {
      if (model.ws?.readyState === WebSocket.OPEN) {
        const payload = { type: "calibration_stop" };
        if (msg.data?.model) {
          payload.hydroModel = msg.data.model;
        }
        model.ws.send(JSON.stringify(payload));
      }
      // the flags are cleared by the final streamed frames, not here
      return model;
    }
    case "calibration/GotStep": {
      const cal = model.calibration;
      const { hydroModel, runId, done } = msg.data;
      // a frame from a superseded run is ignored
      if (runId !== cal.runId) {
        return model;
      }
      const next = {
        ...model,
        calibration: {
          ...cal,
          attempts: appendAttempt(cal.attempts, hydroModel, msg.data),
          // the streamed params drive the disabled sliders' animation
          draft: { ...cal.draft, [hydroModel]: msg.data.params },
          simulations:
            msg.data.simulation != null
              ? { ...cal.simulations, [hydroModel]: msg.data.simulation }
              : cal.simulations,
          calibrating: done
            ? { ...cal.calibrating, [hydroModel]: false }
            : cal.calibrating,
        },
      };
      return maybeComplete(next, dispatch);
    }
    case "calibration/GotError": {
      const cal = model.calibration;
      console.error(msg.data.message);
      // a run-wide error clears every flag; a per-model error only its own
      const calibrating =
        msg.data.hydroModel == null
          ? {}
          : { ...cal.calibrating, [msg.data.hydroModel]: false };
      return { ...model, calibration: { ...cal, calibrating } };
    }
    case "calibration/Reset": {
      // clears the fit — drafts back to the model defaults, history and
      // simulations gone — but keeps `settings`, which describe how to
      // calibrate rather than the result of having done so
      const cal = model.calibration;
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        Object.values(cal.calibrating).some(Boolean)
      ) {
        model.ws.send(JSON.stringify({ type: "calibration_stop" }));
      }
      const draft = {};
      for (const m of model.config.hydroModels ?? []) {
        draft[m] = defaultParams(cal.info, m);
      }
      dropParams(model, dispatch);
      return {
        ...model,
        calibration: {
          ...cal,
          draft,
          attempts: {},
          simulations: {},
          // cleared like ContextChanged, so simulateOnView redraws the
          // default-parameter simulation instead of leaving an empty chart
          requestIds: {},
          silentIds: {},
          calibrating: {},
          runId: cal.runId + 1,
        },
      };
    }
    case "calibration/Import": {
      // the decision half of an import: diff the file's config against the
      // live one; a difference opens the styled modal instead of restoring
      // anything, and ImportConfirm carries on from there
      const imported = msg.data;
      const changed = importConfigDiff(model, imported);
      if (changed.length > 0) {
        return {
          ...model,
          calibration: {
            ...model.calibration,
            importDialog: { imported, changed },
          },
        };
      }
      return proceedImport(model, imported, changed, dispatch);
    }
    case "calibration/ImportConfirm": {
      const dialog = model.calibration.importDialog;
      if (!dialog?.imported) {
        return model;
      }
      return proceedImport(model, dialog.imported, dialog.changed, dispatch);
    }
    case "calibration/ImportCancel":
      return {
        ...model,
        calibration: { ...model.calibration, importDialog: null },
      };
    case "calibration/ImportError":
      return {
        ...model,
        calibration: {
          ...model.calibration,
          importDialog: { message: msg.data },
        },
      };
    case "calibration/ImportApply": {
      // restores the imported bench: the full attempt history, the fitted
      // parameters, and the settings they were produced under — a
      // transformation the scores do not describe would make them a lie. the
      // simulations are not exported, so this leaves exactly the state a
      // reload leaves, and simulateOnView re-runs each model from there,
      // which is what refills params and completes the step
      const cal = model.calibration;
      const imported = msg.data;
      const settings = initSettings(imported.config);
      const dataKey = seriesKey(model.config, settings);
      // the SetConfigs from Import have all landed by now (serial queue); a
      // null key means the imported config was unusable after all
      if (dataKey === null) {
        return model;
      }
      const attempts = attemptsMap(
        Object.fromEntries(
          Object.entries(imported.models).map(([m, saved]) => [
            m,
            saved.attempts,
          ]),
        ),
      );
      const draft = {};
      for (const [m, list] of Object.entries(attempts)) {
        draft[m] = list[list.length - 1].params;
      }
      return {
        ...model,
        calibration: {
          ...cal,
          settings,
          // pinned to the restored history like everywhere else
          contextKey: contextKey(model.config),
          dataKey,
          // a null series makes the next GetSeries read as a first load,
          // which is the branch that preserves the restored attempts —
          // exactly the path a reload takes
          series: null,
          draft: { ...cal.draft, ...draft },
          attempts,
          simulations: {},
          // as in Reset: cleared so simulateOnView re-runs every model, here
          // against the restored parameters
          requestIds: {},
          silentIds: {},
          calibrating: {},
          runId: cal.runId + 1,
        },
      };
    }
    case "calibration/Hover":
      return {
        ...model,
        calibration: { ...model.calibration, hover: msg.data },
      };
    case "calibration/Rerender":
      return { ...model };
    case "calibration/Export":
      exportResults(model);
      return model;
    default:
      return model;
  }
}

function appendAttempt(attempts, hydroModel, data) {
  return {
    ...attempts,
    [hydroModel]: [
      ...(attempts[hydroModel] ?? []),
      { params: data.params, objectives: data.objectives },
    ],
  };
}

// the config keys the imported file was produced under that differ from the
// live ones; order-sensitive on hydroModels, which is what contextKey is too
function importConfigDiff(model, imported) {
  const cfg = imported.config;
  const target = {
    calibrationStation: cfg.station,
    calibrationPeriod: { start: cfg.start, end: cfg.end },
    weatherMethod: cfg.weatherMethod,
    weatherNStations: cfg.weatherNStations,
    snowModel: cfg.snowModel,
    hydroModels: Object.keys(imported.models),
  };
  return Object.entries(target)
    .filter(
      ([key, value]) =>
        JSON.stringify(model.config[key]) !== JSON.stringify(value),
    )
    .map(([key, value]) => ({ key, value }));
}

// the go half shared by a matching import and a confirmed replacement: stop a
// live run, invalidate downstream params, queue the SetConfigs, and queue the
// restore. the restore runs in ImportApply, a follow-up message, because the
// serial queue processes the SetConfigs (and the intermediate GetSeries churn
// they trigger) first — restoring here would hand the bench to that churn to
// wipe
function proceedImport(model, imported, changed, dispatch) {
  const cal = model.calibration;
  if (
    model.ws?.readyState === WebSocket.OPEN &&
    Object.values(cal.calibrating).some(Boolean)
  ) {
    model.ws.send(JSON.stringify({ type: "calibration_stop" }));
  }
  dropParams(model, dispatch);
  for (const { key, value } of changed) {
    dispatch({ type: "SetConfig", data: { key, value } });
  }
  dispatch({ type: "calibration/ImportApply", data: imported });
  return {
    ...model,
    calibration: { ...cal, calibrating: {}, importDialog: null },
  };
}

// the mirror of maybeComplete: whenever the stored attempts are thrown away,
// the params built from them are stale too. simulation and projection `use`
// params, so clearing it re-locks both until the new context is calibrated —
// without this they stay open on parameters fitted to another station, period,
// weather method or ensemble. guarded so a no-op change does not churn
// localStorage through SetConfig's persist
function dropParams(model, dispatch) {
  if (model.config.params !== null) {
    dispatch({ type: "SetConfig", data: { key: "params", value: null } });
  }
}

// the whole step is one config key (params); it is only filled once every
// selected model has at least one attempt. complete() is explicit because a
// streamed frame can land while the user sits on another step, where
// autoComplete (which only snapshots the current step) would never fire
function maybeComplete(model, dispatch) {
  const cal = model.calibration;
  const models = model.config.hydroModels ?? [];
  const ready =
    models.length > 0 && models.every((m) => cal.attempts[m]?.length > 0);
  if (!ready) {
    return model;
  }
  dispatch({
    type: "SetConfig",
    data: { key: "params", value: buildParams(model) },
  });
  return complete(model, "calibration");
}

// the params payload downstream steps consume: per model the latest fitted
// hydro parameters, the snow parameters (CemaNeige's melt/threshold plus the
// scraped mean annual snow depth), and the latest objective scores
function buildParams(model) {
  const cal = model.calibration;
  const models = {};
  for (const m of model.config.hydroModels) {
    const attempts = cal.attempts[m];
    const latest = attempts[attempts.length - 1];
    models[m] = {
      hydro: latest.params,
      snow:
        model.config.snowModel === "cemaneige"
          ? [0.25, 3.74, cal.series.qnbv]
          : null,
      objectives: latest.objectives,
    };
  }
  return {
    objective: cal.settings.objective,
    transformation: cal.settings.transformation,
    algorithm: cal.settings.algorithm,
    algorithmParams: cal.settings.algorithmParams,
    warmupYears: cal.settings.warmupYears,
    models,
  };
}

// the calibration data request is keyed by everything that invalidates it: the
// station, its period and the weather method (with its station count), plus
// the warmup, which prepends its years before the period and so changes the
// date grid the simulations are drawn against
function seriesParams(config, settings) {
  const station = config.calibrationStation;
  const period = config.calibrationPeriod;
  const method = config.weatherMethod;
  if (!station || !period || !method) {
    return null;
  }
  return {
    station,
    start: period.start,
    end: period.end,
    method,
    n_stations: config.weatherNStations,
    warmupYears: settings.warmupYears,
  };
}

function seriesKey(config, settings) {
  const p = seriesParams(config, settings);
  return p
    ? `${p.station}|${p.start}|${p.end}|${p.method}|${p.n_stations}|${p.warmupYears}`
    : null;
}

// everything outside the data request that makes stored attempts incomparable.
// takes a bare config rather than the model so initCalibration can check a
// restored bench before there is a model to read
function contextKey(config) {
  return `${config.snowModel}|${(config.hydroModels ?? []).join()}`;
}

/********/
/* view */
/********/

export function controlsView(model, dispatch) {
  const controls = document.getElementById("controls");
  // structure is built once per step entry, then reconciled in place:
  // rebuilding under a click swallows it
  if (controls.dataset.step !== "calibration") {
    controls.dataset.step = "calibration";
    clear(controls);
    controls.append(
      titleView(dispatch),
      settingSelect("objective", "Objective", objectives, dispatch),
      settingSelect(
        "transformation",
        "Transformation",
        transformations,
        dispatch,
      ),
      settingSelect("algorithm", "Algorithm", algorithms, dispatch),
      warmupField(model, dispatch),
      create("details", { class: "controls__details" }, [
        create("summary", {}, "Algorithm settings"),
        create("div", { id: "calibration__algo-params" }),
      ]),
      create("div", { id: "calibration__models" }),
      actionsView(dispatch),
      create(
        "dialog",
        { id: "calibration__import-dialog" },
        [],
        // Escape closes the native modal itself; the cancel event keeps the
        // model in sync with that close
        [
          {
            event: "cancel",
            fct: () => dispatch({ type: "calibration/ImportCancel" }),
          },
        ],
      ),
    );
  }
  syncControls(model, dispatch);
}

// the title row: the heading plus a subtle Clear that empties the bench. it
// deliberately leaves the settings alone, so the objective, transformation,
// algorithm and warmup the user picked survive a reset of the fit itself
function titleView(dispatch) {
  return create("div", { class: "calibration__title" }, [
    create("h2", {}, "Calibration"),
    create(
      "button",
      { id: "calibration__clear", class: "calibration__clear", type: "button" },
      "Clear",
      [{ event: "click", fct: () => dispatch({ type: "calibration/Reset" }) }],
    ),
  ]);
}

function settingSelect(key, label, options, dispatch) {
  return create("label", { class: "controls__field" }, [
    create("span", {}, label),
    create(
      "select",
      { id: `calibration__setting-${key}` },
      options.map((o) => create("option", { value: o.id }, o.label)),
      [
        {
          event: "change",
          fct: (event) =>
            dispatch({
              type: "calibration/SetSetting",
              data: { key: key, value: event.target.value },
            }),
        },
      ],
    ),
  ]);
}

function warmupField(model, dispatch) {
  return create("label", { class: "controls__field" }, [
    create("span", {}, "Warmup years"),
    createSlider(
      "calibration__warmup",
      0,
      5,
      true,
      [
        {
          event: "change",
          // read the raw value fresh from the number input (never a stale
          // closure over the model)
          fct: () =>
            dispatch({
              type: "calibration/SetSetting",
              data: {
                key: "warmupYears",
                value: Number(
                  document.getElementById("calibration__warmup").value,
                ),
              },
            }),
        },
      ],
      model.calibration.settings.warmupYears,
    ),
  ]);
}

function actionsView(dispatch) {
  return create("div", { class: "calibration__actions" }, [
    create(
      "button",
      { id: "calibration__calibrate", type: "button" },
      "Calibrate",
      [
        {
          event: "click",
          // the same button starts and stops a run; its mode is set in sync so
          // the built-once handler never reads a stale model
          fct: (event) =>
            dispatch(
              event.currentTarget.dataset.mode === "stop"
                ? { type: "calibration/Stop", data: { model: null } }
                : { type: "calibration/Start" },
            ),
        },
      ],
    ),
    create("button", { id: "calibration__export", type: "button" }, "Export", [
      { event: "click", fct: () => dispatch({ type: "calibration/Export" }) },
    ]),
    // a native file input drives the import; the button only proxies the
    // click so the input can stay hidden
    create("button", { id: "calibration__import", type: "button" }, "Import", [
      {
        event: "click",
        fct: () =>
          document.getElementById("calibration__import-file").click(),
      },
    ]),
    create(
      "input",
      {
        id: "calibration__import-file",
        type: "file",
        accept: ".json,application/json",
        hidden: "",
      },
      [],
      [{ event: "change", fct: (event) => importFile(event.target, dispatch) }],
    ),
  ]);
}

// reads and shape-checks the file here; every decision against live state
// (config diff, confirmation) belongs to the Import handler, because this
// built-once closure's model would be stale
async function importFile(input, dispatch) {
  const file = input.files?.[0];
  // reset so re-picking the same file still fires change
  input.value = "";
  if (!file) {
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch (error) {
    console.error(error);
    dispatch({
      type: "calibration/ImportError",
      data: "This file is not valid JSON.",
    });
    return;
  }
  if (!validImport(parsed)) {
    dispatch({
      type: "calibration/ImportError",
      data: "This file is not a calibration export.",
    });
    return;
  }
  dispatch({ type: "calibration/Import", data: parsed });
}

// a user-picked file is untrusted: everything the restore indexes is checked,
// and the enums that would otherwise go out on the wire are pinned to known
// values (modelLabels doubles as the list of valid hydro models)
function validImport(parsed) {
  const cfg = parsed?.config;
  return (
    cfg !== null &&
    typeof cfg === "object" &&
    typeof cfg.station === "string" &&
    typeof cfg.start === "string" &&
    typeof cfg.end === "string" &&
    cfg.start <= cfg.end &&
    ["nearest_stations", "era5", "ministry_grid"].includes(
      cfg.weatherMethod,
    ) &&
    Number.isInteger(cfg.weatherNStations) &&
    ["cemaneige", "none"].includes(cfg.snowModel) &&
    parsed.models !== null &&
    typeof parsed.models === "object" &&
    Object.keys(parsed.models).length > 0 &&
    Object.keys(parsed.models).every((m) => m in modelLabels) &&
    Object.values(parsed.models).every(
      (m) =>
        m &&
        Array.isArray(m.attempts) &&
        m.attempts.length > 0 &&
        m.attempts.every(
          (a) =>
            a &&
            Array.isArray(a.params) &&
            a.params.every(Number.isFinite) &&
            a.objectives !== null &&
            typeof a.objectives === "object",
        ),
    )
  );
}

function syncControls(model, dispatch) {
  const busy = anyCalibrating(model.calibration);
  syncSettings(model, busy);
  syncAlgorithmParams(model, dispatch, busy);
  syncModelSections(model, dispatch);
  syncActions(model, busy);
  syncImportDialog(model, dispatch);
}

// the modal mirrors cal.importDialog: content is rebuilt when that state
// changes, and the native showModal/close pair tracks its presence. the
// config cannot move while the modal is open (it blocks the page), so the
// "current" values rendered at open time stay true
function syncImportDialog(model, dispatch) {
  const dialog = document.getElementById("calibration__import-dialog");
  const state = model.calibration.importDialog;
  const signature = state ? JSON.stringify(state) : "none";
  if (dialog.dataset.signature === signature) {
    return;
  }
  dialog.dataset.signature = signature;
  clear(dialog);
  if (!state) {
    dialog.close();
    return;
  }
  dialog.append(
    ...(state.message
      ? importErrorContent(state, dispatch)
      : importConfirmContent(model, state, dispatch)),
  );
  if (!dialog.open) {
    dialog.showModal();
  }
}

function importErrorContent(state, dispatch) {
  return [
    create("p", {}, state.message),
    create("div", { class: "calibration__dialog-actions" }, [
      create("button", { type: "button" }, "OK", [
        {
          event: "click",
          fct: () => dispatch({ type: "calibration/ImportCancel" }),
        },
      ]),
    ]),
  ];
}

function importConfirmContent(model, state, dispatch) {
  return [
    create(
      "p",
      {},
      "This calibration was exported under a different configuration." +
        " Replace the current one?",
    ),
    create(
      "ul",
      {},
      state.changed.map(({ key, value }) =>
        create("li", {}, [
          create("b", {}, configLabels[key] ?? key),
          `: ${formatConfigValue(model.config[key])} → ` +
            formatConfigValue(value),
        ]),
      ),
    ),
    create("div", { class: "calibration__dialog-actions" }, [
      create(
        "button",
        { type: "button", class: "calibration__dialog-secondary" },
        "Cancel",
        [
          {
            event: "click",
            fct: () => dispatch({ type: "calibration/ImportCancel" }),
          },
        ],
      ),
      create("button", { type: "button" }, "Replace", [
        {
          event: "click",
          fct: () => dispatch({ type: "calibration/ImportConfirm" }),
        },
      ]),
    ]),
  ];
}

function formatConfigValue(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (Array.isArray(value)) {
    return value.map((v) => modelLabels[v] ?? v).join(", ");
  }
  // the only object-valued key an import can replace is a period
  if (typeof value === "object") {
    return `${value.start} – ${value.end}`;
  }
  return String(value);
}

// settings mirror the model unless the user is mid-edit, and lock while any
// model calibrates (they are baked into the running SCE search)
function syncSettings(model, busy) {
  const cal = model.calibration;
  for (const key of ["objective", "transformation", "algorithm"]) {
    const select = document.getElementById(`calibration__setting-${key}`);
    if (document.activeElement !== select) {
      select.value = cal.settings[key];
    }
    select.disabled = busy;
  }
  // the slider is two inputs (number + range): both mirror the model unless
  // one is mid-edit, and both lock while calibrating
  const warmup = document.getElementById("calibration__warmup");
  const warmupRange = warmup.parentNode.querySelector("input[type='range']");
  if (
    document.activeElement !== warmup &&
    document.activeElement !== warmupRange
  ) {
    warmup.value = cal.settings.warmupYears;
    warmupRange.value = cal.settings.warmupYears;
  }
  warmup.disabled = busy;
  warmupRange.disabled = busy;
}

function syncAlgorithmParams(model, dispatch, busy) {
  const cal = model.calibration;
  if (!isInfoLoaded(cal.info)) {
    return;
  }
  const params = cal.info.algorithms?.[cal.settings.algorithm] ?? [];
  const container = document.getElementById("calibration__algo-params");
  // manual has no hyperparameters, so the settings panel is pure noise
  container.closest("details").hidden = params.length === 0;
  // rebuilt only when the algorithm's parameter set changes
  if (container.dataset.algorithm !== cal.settings.algorithm) {
    container.dataset.algorithm = cal.settings.algorithm;
    clear(container);
    params.forEach((p) => container.append(algorithmParamRow(p, dispatch)));
  }
  for (const p of params) {
    const input = document.getElementById(`calibration__algo-${p.name}`);
    if (!input) {
      continue;
    }
    if (document.activeElement !== input) {
      input.value = cal.settings.algorithmParams?.[p.name] ?? p.default;
    }
    input.disabled = busy;
  }
}

// plain number inputs for every SCE hyperparameter: several are unbounded
// (max: null), so a slider would have no track to sit on
function algorithmParamRow(p, dispatch) {
  const attrs = {
    type: "number",
    id: `calibration__algo-${p.name}`,
    step: p.integer ? "1" : "any",
  };
  if (p.min != null) {
    attrs.min = p.min;
  }
  if (p.max != null) {
    attrs.max = p.max;
  }
  return create("label", { class: "controls__field" }, [
    create("span", {}, p.name),
    create(
      "input",
      attrs,
      [],
      [
        {
          event: "change",
          fct: (event) =>
            dispatch({
              type: "calibration/SetAlgorithmParam",
              data: { name: p.name, value: event.target.valueAsNumber },
            }),
        },
      ],
    ),
  ]);
}

function syncModelSections(model, dispatch) {
  const cal = model.calibration;
  const container = document.getElementById("calibration__models");
  const models = model.config.hydroModels ?? [];
  // the sections are rebuilt only when the selection or the info-loaded state
  // changes, so a click on a slider is never swallowed by a rebuild
  const signature = `${models.join()}|${isInfoLoaded(cal.info) ? "loaded" : "loading"}`;
  if (container.dataset.signature !== signature) {
    container.dataset.signature = signature;
    clear(container);
    models.forEach((m) => container.append(modelSection(model, m, dispatch)));
  }
  models.forEach((m) => syncModelSection(model, m));
}

function modelSection(model, m, dispatch) {
  const cal = model.calibration;
  const params = isInfoLoaded(cal.info) ? (cal.info.hydro?.[m] ?? []) : [];
  const attrs = {
    class: "controls__details calibration__model",
    "data-model": m,
  };
  // a lone model opens by default; an ensemble stays collapsed to fit
  if ((model.config.hydroModels ?? []).length === 1) {
    attrs.open = "";
  }
  return create(
    "details",
    attrs,
    [
      create("summary", {}, [
        create("b", {}, modelLabels[m] ?? m),
        create(
          "span",
          { class: "calibration__objective", id: `calibration__chip-${m}` },
          "—",
        ),
        create(
          "button",
          {
            class: "calibration__stop",
            id: `calibration__stop-${m}`,
            type: "button",
            hidden: "",
          },
          "Stop",
          [
            {
              event: "click",
              fct: (event) => {
                // inside a <summary>, a click would otherwise toggle the panel
                event.preventDefault();
                dispatch({
                  type: "calibration/Stop",
                  data: { model: m },
                });
              },
            },
          ],
        ),
      ]),
      ...params.map((p, i) => paramRow(model, m, p, i, dispatch)),
    ],
    [
      {
        event: "mouseenter",
        fct: () => dispatch({ type: "calibration/Hover", data: m }),
      },
      {
        event: "mouseleave",
        fct: () => dispatch({ type: "calibration/Hover", data: null }),
      },
    ],
  );
}

function paramRow(model, m, p, i, dispatch) {
  const value = model.calibration.draft[m]?.[i] ?? p.default;
  const sliderId = `calibration__slider-${m}-${i}`;
  return create("div", { class: "calibration__param" }, [
    create("span", {}, p.name),
    createSlider(
      sliderId,
      p.min,
      p.max,
      false,
      [
        {
          event: "change",
          // read the raw value fresh from the number input (never a stale
          // closure over the model), then simulate this model with it
          fct: () => {
            const v = Number(document.getElementById(sliderId).value);
            dispatch({
              type: "calibration/SetParam",
              data: { model: m, index: i, value: v },
            });
            dispatch({ type: "calibration/Simulate", data: { model: m } });
          },
        },
      ],
      value,
      paramTransform(p),
    ),
  ]);
}

// a parameter spanning two or more orders of magnitude within a positive range
// slides on a log scale so its lower decades are not squashed to nothing
function paramTransform(p) {
  if (p.min > 0 && p.max / p.min >= 100) {
    return { toSlider: Math.log10, fromSlider: (x) => 10 ** x };
  }
  return null;
}

function syncModelSection(model, m) {
  const cal = model.calibration;
  const calibrating = !!cal.calibrating[m];
  const details = document.querySelector(
    `.calibration__model[data-model="${m}"]`,
  );
  if (!details) {
    return;
  }
  details.classList.toggle("calibration__model--busy", calibrating);
  // the highlight exists to pick one model out of an ensemble; with a lone
  // model there is nothing to pick it out from, so it would only be noise
  const single = (model.config.hydroModels ?? []).length === 1;
  details.classList.toggle(
    "calibration__model--highlight",
    cal.hover === m && !single,
  );

  const attempts = cal.attempts[m] ?? [];
  const latest = attempts[attempts.length - 1];
  // named, since the chip shows whichever objective is selected
  const objective = cal.settings.objective;
  document.getElementById(`calibration__chip-${m}`).textContent =
    `${objective} ${
      latest ? formatObjective(latest.objectives[objective]) : "—"
    }`;

  document.getElementById(`calibration__stop-${m}`).hidden = !calibrating;

  const params = isInfoLoaded(cal.info) ? (cal.info.hydro?.[m] ?? []) : [];
  params.forEach((p, i) => {
    const number = document.getElementById(`calibration__slider-${m}-${i}`);
    if (!number) {
      return;
    }
    const range = number.parentNode.querySelector("input[type='range']");
    const value = cal.draft[m]?.[i] ?? p.default;
    const focused =
      document.activeElement === number || document.activeElement === range;
    // update the values while calibrating (the animation) or when the field is
    // idle, but never clobber a value the user is mid-drag on
    if (calibrating || !focused) {
      number.value = value;
      const transform = paramTransform(p);
      range.value = transform ? transform.toSlider(value) : value;
    }
    number.disabled = calibrating;
    range.disabled = calibrating;
  });
}

function syncActions(model, busy) {
  const cal = model.calibration;
  const models = model.config.hydroModels ?? [];
  const calibrate = document.getElementById("calibration__calibrate");
  calibrate.dataset.mode = busy ? "stop" : "calibrate";
  calibrate.textContent = busy ? "Stop" : "Calibrate";
  // manual calibration means slider moves only: nothing to launch
  calibrate.hidden = cal.settings.algorithm === "manual";

  document.getElementById("calibration__export").disabled = !(
    models.length > 0 && models.every((m) => cal.attempts[m]?.length > 0)
  );

  // importing stops a running fit, so lock it while one runs
  document.getElementById("calibration__import").disabled = busy;

  // nothing fitted yet means nothing to clear
  document.getElementById("calibration__clear").disabled = !models.some(
    (m) => cal.attempts[m]?.length > 0,
  );
}

export function canvasView(model, dispatch) {
  const canvas = document.getElementById("canvas");
  if (canvas.dataset.step !== "calibration") {
    canvas.dataset.step = "calibration";
    clear(canvas);
    // inside #canvas so other steps' clearing removes the panel for free
    canvas.append(
      create("div", { id: "calibration-charts" }, [
        chartFigure("objective"),
        chartFigure("streamflow"),
      ]),
    );
    observePanelResize(dispatch);
  }
  fetchOnView(model, dispatch);
  chartsView(model);
}

function chartFigure(name) {
  return create("figure", { id: `calibration__${name}` }, [
    create("figcaption", {}),
    create("div", { class: "hydrographs__loading" }, [createLoading()]),
    create("svg", { class: "plot", id: `calibration__${name}-svg` }),
  ]);
}

// charts must re-read their box on resize, so a debounced no-op message
// re-runs the view and the size signature forces the redraw
function observePanelResize(dispatch) {
  let timeout;
  const observer = new ResizeObserver(() => {
    clearTimeout(timeout);
    timeout = setTimeout(() => dispatch({ type: "calibration/Rerender" }), 100);
  });
  observer.observe(document.getElementById("calibration-charts"));
}

// fetch-on-view: the info fetch guards itself, and GetSeries fires on first
// entry and whenever an upstream change (station/period/method/warmup) moves
// the key
function fetchOnView(model, dispatch) {
  if (
    model.calibration.info === null &&
    model.ws?.readyState === WebSocket.OPEN
  ) {
    dispatch({ type: "calibration/GetInfo" });
  }
  const key = seriesKey(model.config, model.calibration.settings);
  if (key !== null && key !== model.calibration.series?.key) {
    dispatch({ type: "calibration/GetSeries" });
  }
  if (contextKey(model.config) !== model.calibration.contextKey) {
    dispatch({ type: "calibration/ContextChanged" });
  }
  simulateOnView(model, dispatch);
}

// the fitted parameters and the objective history are restored from
// localStorage but the simulations are not (a full daily series per model is
// far too large to store), so each model is re-run once from its restored
// draft. this uses the manual route, which is the same "run these params over
// this period" call the simulation step will make. the run is `silent`, which
// GotResult honours only when the model already has a history: it would
// otherwise double the last point, but with no history its objective is the
// only one there is and gets recorded. requestIds gates it — Simulate stamps
// one immediately, so a model is requested once per data context even if the
// reply never lands
function simulateOnView(model, dispatch) {
  const cal = model.calibration;
  if (!cal.series?.data || !isInfoLoaded(cal.info) || anyCalibrating(cal)) {
    return;
  }
  for (const m of model.config.hydroModels ?? []) {
    if (
      cal.draft[m] &&
      cal.simulations[m] == null &&
      cal.requestIds[m] == null
    ) {
      dispatch({
        type: "calibration/Simulate",
        data: { model: m, silent: true },
      });
    }
  }
}

function chartsView(model) {
  const cal = model.calibration;
  const loading = !cal.series?.data;
  document
    .getElementById("calibration__objective")
    .classList.toggle("hydrographs__figure--loading", loading);
  document
    .getElementById("calibration__streamflow")
    .classList.toggle("hydrographs__figure--loading", loading);
  if (loading) {
    return;
  }
  captionsView(model);
  objectiveChartView(model);
  streamflowChartView(model);
  hoverHighlightView(cal.hover);
}

function captionsView(model) {
  const cal = model.calibration;
  document
    .getElementById("calibration__objective")
    .querySelector("figcaption").textContent =
    `Objective (${cal.settings.objective.toUpperCase()})`;
  const id = model.config.calibrationStation;
  const station = model.stations?.find((s) => s.id === id);
  document
    .getElementById("calibration__streamflow")
    .querySelector("figcaption").textContent = station
    ? `${station.name} (${id})`
    : "Streamflow";
}

function objectiveChartView(model) {
  const cal = model.calibration;
  const svg = document.getElementById("calibration__objective-svg");
  const signature = chartSignature(model, svg);
  if (svg.dataset.signature === signature) {
    return;
  }
  svg.dataset.signature = signature;

  const obj = cal.settings.objective;
  const withAttempts = (model.config.hydroModels ?? []).filter(
    (m) => cal.attempts[m]?.length,
  );
  // nothing fitted yet: clear the panel rather than draw an empty frame
  if (withAttempts.length === 0) {
    d3.select(svg).selectAll("*").remove();
    return;
  }
  const valueArrays = withAttempts.map((m) =>
    cal.attempts[m].map((a) => a.objectives[obj] ?? null),
  );
  const maxLen = Math.max(...valueArrays.map((v) => v.length));
  const series = simulationSeries(
    withAttempts,
    (m) =>
      cal.attempts[m].map((a, i) => ({
        x: i + 1,
        y: a.objectives[obj] ?? null,
      })),
    () => objectiveMedian(valueArrays, maxLen),
  );
  multiSeriesView(svg, series, {
    xType: "linear",
    label: obj.toUpperCase(),
    warmupEnd: null,
    // the ideal score: RMSE aims at 0, NSE and KGE at 1
    reference: obj === "rmse" ? 0 : 1,
    // a handful of steps reads as nothing without markers, and a single one
    // draws no line segment at all; past ten they crowd into a solid band
    showPoints: maxLen <= 10,
  });
}

// both charts draw the same ensemble shape: one faint line per model plus the
// median on top. a lone model has no ensemble to summarise, so it *is* the
// median — drawn in that style, and labelled "simulation" rather than "median"
function simulationSeries(models, pointsOf, medianPoints) {
  if (models.length === 0) {
    return [];
  }
  if (models.length === 1) {
    // no `model` field, so the line carries no data-model hook and the hover
    // cross-highlight skips it: there is nothing to pick it out from
    return [
      {
        key: models[0],
        kind: "median",
        label: "simulation",
        points: pointsOf(models[0]),
      },
    ];
  }
  return [
    ...models.map((m) => ({
      key: m,
      model: m,
      kind: "model",
      points: pointsOf(m),
    })),
    { key: "median", kind: "median", points: medianPoints() },
  ];
}

function streamflowChartView(model) {
  const cal = model.calibration;
  const svg = document.getElementById("calibration__streamflow-svg");
  const signature = chartSignature(model, svg);
  if (svg.dataset.signature === signature) {
    return;
  }
  svg.dataset.signature = signature;

  const dates = cal.series.data.dates;
  const withSims = (model.config.hydroModels ?? []).filter(
    (m) => cal.simulations[m] != null,
  );
  const series = simulationSeries(
    withSims,
    (m) => dates.map((d, i) => ({ x: d, y: cal.simulations[m][i] ?? null })),
    () => {
      const sims = withSims.map((m) => cal.simulations[m]);
      return dates.map((d, i) => ({ x: d, y: pointwiseMedian(sims, i) }));
    },
  );
  series.push({
    key: "observations",
    kind: "observations",
    // purple, so a hovered model (which turns --theme blue) never reads as the
    // observed series
    colour: "purple",
    points: dates.map((d, i) => ({ x: d, y: cal.series.data.observations[i] })),
  });
  // the series carries the warmup lead ahead of the period, so the band runs
  // from its start to the period start rather than a row count into it
  const period = model.config.calibrationPeriod;
  const warmupEnd =
    cal.settings.warmupYears > 0 && dates.length && period
      ? new Date(period.start)
      : null;
  multiSeriesView(svg, series, {
    xType: "time",
    label: "Streamflow (mm)",
    warmupEnd,
    reference: null,
  });
}

// everything that should force a redraw; matching it preserves the brush zoom.
// both charts share one signature (the extra terms only cost redundant redraws)
function chartSignature(model, svg) {
  const cal = model.calibration;
  const models = model.config.hydroModels ?? [];
  return [
    cal.series?.key,
    models.map((m) => cal.attempts[m]?.length ?? 0).join(","),
    models.map((m) => (cal.simulations[m] ? 1 : 0)).join(","),
    cal.settings.objective,
    cal.settings.warmupYears,
    `${svg.clientWidth}x${svg.clientHeight}`,
  ].join("|");
}

// cross-highlight the hovered model across both charts without redrawing: dim
// the others while a hover is active, clear both classes when none is
function hoverHighlightView(hover) {
  for (const id of [
    "calibration__objective-svg",
    "calibration__streamflow-svg",
  ]) {
    const svg = document.getElementById(id);
    svg.querySelectorAll("[data-model]").forEach((mark) => {
      const hovered = hover && mark.getAttribute("data-model") === hover;
      mark.classList.toggle("series--active", !!hovered);
      mark.classList.toggle("series--dim", !!hover && !hovered);
    });
    svg
      .querySelectorAll(".chart-content")
      .forEach((c) => raiseHovered(c, hover));
  }
}

// SVG paints in document order, so the hovered model is moved to the end of
// its group to read over the median and the observations; clearing the hover
// restores the order the draw recorded. the point markers ride along so they
// never end up under the line they belong to
function raiseHovered(content, hover) {
  // reset first, so moving from one hovered model to the next does not leave
  // the previous one stranded on top
  const paths = [...content.querySelectorAll("path.series-line")].sort(
    (a, b) => a.dataset.order - b.dataset.order,
  );
  paths.forEach((p) => content.append(p));
  const hovered =
    hover && paths.find((p) => p.getAttribute("data-model") === hover);
  if (hovered) {
    content.append(hovered);
  }
  content.querySelectorAll("circle.series-point").forEach((c) => {
    if (!hover || c.getAttribute("data-model") === hover) {
      content.append(c);
    }
  });
}

function exportResults(model) {
  const cal = model.calibration;
  const p = seriesParams(model.config, cal.settings);
  if (!p || !cal.series?.data) {
    return;
  }
  const models = model.config.hydroModels ?? [];
  const base = `calibration_${p.station}_${p.start}_${p.end}`;
  downloadBlob(
    `${base}.json`,
    "application/json",
    JSON.stringify(exportJson(model, p, models), null, 2),
  );
  downloadBlob(`${base}.csv`, "text/csv", exportCsv(model, models));
}

function exportJson(model, p, models) {
  const cal = model.calibration;
  const out = {};
  for (const m of models) {
    const attempts = cal.attempts[m] ?? [];
    const latest = attempts[attempts.length - 1];
    const names = (
      isInfoLoaded(cal.info) ? (cal.info.hydro?.[m] ?? []) : []
    ).map((d) => d.name);
    const hydro = {};
    if (latest) {
      latest.params.forEach((v, i) => {
        hydro[names[i] ?? `x${i + 1}`] = v;
      });
    }
    out[m] = {
      hydro,
      snow:
        model.config.snowModel === "cemaneige"
          ? [0.25, 3.74, cal.series.qnbv]
          : null,
      attempts,
    };
  }
  return {
    config: {
      station: p.station,
      start: p.start,
      end: p.end,
      weatherMethod: p.method,
      weatherNStations: p.n_stations,
      snowModel: model.config.snowModel,
      objective: cal.settings.objective,
      transformation: cal.settings.transformation,
      warmupYears: cal.settings.warmupYears,
      algorithm: cal.settings.algorithm,
      algorithmParams: cal.settings.algorithmParams,
    },
    models: out,
  };
}

function exportCsv(model, models) {
  const cal = model.calibration;
  const dates = cal.series.data.dates;
  // a lone model *is* the median (the charts merge them too), so the column
  // would only duplicate it
  const withMedian = models.length > 1;
  const header = [
    "datetime",
    "observations",
    ...models,
    ...(withMedian ? ["median"] : []),
  ];
  const sims = models.map((m) => cal.simulations[m]).filter((s) => s != null);
  const rows = dates.map((d, i) => {
    const cells = [d, cal.series.data.observations[i]];
    for (const m of models) {
      const sim = cal.simulations[m];
      cells.push(sim != null ? (sim[i] ?? null) : null);
    }
    if (withMedian) {
      cells.push(pointwiseMedian(sims, i));
    }
    return cells;
  });
  return toCsv(header, rows);
}

/**********/
/* shared */
/**********/

function anyCalibrating(cal) {
  return Object.values(cal.calibrating).some(Boolean);
}

// "pending" (a string) and null both read as not-yet-loaded
function isInfoLoaded(info) {
  return info != null && typeof info === "object";
}

function sceDefaults(info) {
  return Object.fromEntries(
    (info.algorithms?.sce ?? []).map((p) => [p.name, p.default]),
  );
}

function defaultParams(info, m) {
  return isInfoLoaded(info)
    ? (info.hydro?.[m] ?? []).map((p) => p.default)
    : [];
}

// ~3 significant figures, or an em dash for a degenerate (null) score
function formatObjective(v) {
  if (v === null || v === undefined || !Number.isFinite(v)) {
    return "—";
  }
  return parseFloat(v.toPrecision(3)).toString();
}

// forward-fill each model's last value out to maxLen, then take the null-safe
// median column by column (models with no finite value there contribute none)
function objectiveMedian(valueArrays, maxLen) {
  const points = [];
  for (let i = 0; i < maxLen; i++) {
    const vals = [];
    for (const arr of valueArrays) {
      const v = i < arr.length ? arr[i] : arr[arr.length - 1];
      if (isFiniteNumber(v)) {
        vals.push(v);
      }
    }
    points.push({ x: i + 1, y: vals.length ? median(vals) : null });
  }
  return points;
}

// null-safe median across the series at one aligned index
function pointwiseMedian(seriesList, i) {
  const vals = [];
  for (const series of seriesList) {
    const v = series[i];
    if (isFiniteNumber(v)) {
      vals.push(v);
    }
  }
  return vals.length ? median(vals) : null;
}

function isFiniteNumber(v) {
  return v !== null && v !== undefined && Number.isFinite(v);
}

function median(vals) {
  const sorted = [...vals].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
