import { create } from "./utils/elements.js";
import { checkEscape } from "./utils/listeners.js";
import {
  connect,
  incrementReconnectAttempt,
  isCircuitBreakerOpen,
} from "./utils/ws.js";

import * as settings from "./settings.js";
import * as pipeline from "./pipeline.js";
import * as calibration from "./steps/calibration.js";
import * as simulation from "./steps/simulation.js";
import * as projection from "./steps/projection.js";

const wsUrl = "ws";
const storageKey = "holmes--pipeline";

/*********/
/* model */
/*********/

function initModel() {
  const saved = readSavedPipeline();
  // built before the model so the calibration bench can be validated against
  // the config it was fitted under
  const config = {
    calibrationStation: null,
    simulationStation: null,
    calibrationPeriod: null,
    simulationPeriod: null,
    weatherMethod: null,
    weatherNStations: 3,
    hydroModels: ["gr4j"],
    modelMode: "single",
    snowModel: "none",
    params: null,
    ...saved.config,
  };
  return {
    preventEscape: false,
    loading: false,
    ws: null,
    settings: settings.initSettings(),
    // transient step state (never persisted)
    stations: null,
    streamflow: {},
    weather: null,
    modelInfo: null,
    modelDetail: null,
    // the calibration bench; settings, fitted params and objective history are
    // restored here, the request caches and live run state are not
    calibration: calibration.initCalibration(saved.calibration ?? null, config),
    // the simulation bench; only its settings are restored, the result is
    // refetched on view (full daily series are too large to persist)
    simulation: simulation.initSimulation(saved.simulation ?? null),
    // same shape as simulation: settings restored, result refetched on view
    projection: projection.initProjection(saved.projection ?? null),
    map: null,
    activeDialogStation: null,
    visibility: { open: true, closed: false },
    step: saved.step ?? "stations",
    config,
    snapshots: saved.snapshots ?? {},
  };
}

function readSavedPipeline() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(storageKey)) ?? {};
    if (saved.step !== undefined && !(saved.step in pipeline.stepById)) {
      delete saved.step;
    }
    return saved;
  } catch (e) {
    console.error("Failed to read saved pipeline state:", e);
    return {};
  }
}

const initialMsg = [{ type: "settings/GetVersion" }, { type: "Connect" }];

/**********/
/* update */
/**********/

async function update(model, msg, dispatch) {
  switch (msg.type) {
    case "CheckEscape":
      if (checkEscape(model, msg.data, dispatch)) {
        return {
          ...model,
          settings: settings.closeOnEscape(model.settings, msg.data),
        };
      }
      return model;
    case "SetPreventEscape":
      setTimeout(() => {
        dispatch({ type: "UnsetPreventEscape" });
      }, 0);
      return { ...model, preventEscape: true };
    case "UnsetPreventEscape":
      return { ...model, preventEscape: false };
    case "SelectStep":
      if (pipeline.status(model, msg.data) === "locked") {
        return model;
      }
      // the map (and any open station dialog) persists across steps, so the
      // dialog would otherwise survive into the next step
      return persist({ ...model, step: msg.data, activeDialogStation: null });
    case "SetConfig":
      if (!(msg.data.key in model.config)) {
        console.error(`Unknown config key: ${msg.data.key}`);
        return model;
      }
      return persist(
        pipeline.autoComplete({
          ...model,
          config: { ...model.config, [msg.data.key]: msg.data.value },
        }),
      );
    case "Connect":
      connect(wsUrl, handleMessage, dispatch, dispatch);
      return { ...model, loading: true };
    case "Connected":
      if (model.stations === null) {
        dispatch({ type: "stations/GetStations" });
      }
      // drop the weather cache so the weather view refetches, retrying a
      // request lost while disconnected (streamflow retries via GotStations);
      // clear a model_info request lost mid-flight so the model step refetches
      return {
        ...model,
        loading: false,
        ws: msg.data,
        weather: null,
        modelInfo: model.modelInfo === "pending" ? null : model.modelInfo,
        // retry calibration requests lost with the old socket: clear a pending
        // info fetch and a pending series load, and drop the calibrating flags
        // since the server threads died with the connection (results, attempts
        // and draft params survive so the bench is not lost)
        calibration: {
          ...model.calibration,
          info:
            model.calibration.info === "pending"
              ? null
              : model.calibration.info,
          series:
            model.calibration.series && model.calibration.series.data === null
              ? null
              : model.calibration.series,
          calibrating: {},
        },
        // retry a simulation request lost with the old socket: a pending key
        // (no result for it yet) is cleared so fetch-on-view re-sends
        simulation: {
          ...model.simulation,
          requestKey:
            model.simulation.result?.key === model.simulation.requestKey
              ? model.simulation.requestKey
              : null,
        },
        // same retry for a projection request lost with the old socket
        projection: {
          ...model.projection,
          requestKey:
            model.projection.result?.key === model.projection.requestKey
              ? model.projection.requestKey
              : null,
        },
      };
    case "Disconnected": {
      if (isCircuitBreakerOpen(wsUrl)) {
        console.error("Connection lost.");
        return { ...model, ws: null };
      }
      const reconnectState = incrementReconnectAttempt(wsUrl);
      setTimeout(() => dispatch({ type: "Connect" }), reconnectState.delay);
      return { ...model, ws: null };
    }
    default: {
      // module-specific messages are prefixed ("settings/…", "stations/…")
      const prefix = msg.type.split("/")[0];
      if (prefix === "settings") {
        return settings.update(model, msg, dispatch);
      }
      const step = pipeline.stepById[prefix];
      if (!step) {
        return model;
      }
      // every step message goes through persist: the calibration bench changes
      // on frames no single message name can enumerate, and persist coalesces
      // the writes anyway, so listing them would only be a way to miss one
      return persist(step.module.update(model, msg, dispatch));
    }
  }
}

// localStorage writes are synchronous and JSON.stringify of a long objective
// history is not cheap, while a streamed SCE frame lands many times a second.
// writes are therefore coalesced: the newest model wins and at most one write
// happens per window. flushPersist also runs on pagehide, so the last frames
// before a reload are never the ones that get dropped
const persistDelay = 500;
let persistPending = null;
let persistTimer = null;

function persist(model) {
  persistPending = model;
  if (persistTimer === null) {
    persistTimer = window.setTimeout(flushPersist, persistDelay);
  }
  return model;
}

function flushPersist() {
  if (persistTimer !== null) {
    window.clearTimeout(persistTimer);
    persistTimer = null;
  }
  const model = persistPending;
  persistPending = null;
  if (model === null) {
    return;
  }
  const saved = {
    step: model.step,
    config: model.config,
    snapshots: model.snapshots,
    calibration: {
      settings: model.calibration.settings,
      // the two keys the stored bench is only valid under; initCalibration
      // drops it unless both still match the restored config
      contextKey: model.calibration.contextKey,
      dataKey: model.calibration.dataKey,
      draft: model.calibration.draft,
      attempts: model.calibration.attempts,
    },
    simulation: {
      settings: model.simulation.settings,
    },
    projection: {
      settings: model.projection.settings,
    },
  };
  if (writeSaved(saved)) {
    return;
  }
  // the objective history is the only unbounded part of the payload (one entry
  // per SCE step, per model), so it is what gets dropped when the quota is hit
  // — losing the history beats losing the settings and the pipeline config
  console.error("Pipeline state too large to save; dropping attempt history.");
  saved.calibration.attempts = {};
  writeSaved(saved);
}

function writeSaved(saved) {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(saved));
    return true;
  } catch (e) {
    console.error("Failed to save pipeline state:", e);
    return false;
  }
}

function handleMessage(event, dispatch) {
  let msg;
  try {
    msg = JSON.parse(event.data);
  } catch (e) {
    console.error("Failed to parse WebSocket message:", e);
    return;
  }
  switch (msg.type) {
    case "error":
      console.error(msg.data);
      break;
    case "stations":
      dispatch({ type: "stations/GotStations", data: msg.data });
      break;
    case "streamflow":
      dispatch({ type: "stations/GotStreamflow", data: msg.data });
      break;
    case "weather":
      dispatch({ type: "weather/GotWeather", data: msg.data });
      break;
    case "model_info":
      dispatch({ type: "model/GotModelInfo", data: msg.data });
      break;
    case "calibration_info":
      dispatch({ type: "calibration/GotInfo", data: msg.data });
      break;
    case "calibration_data":
      dispatch({ type: "calibration/GotSeries", data: msg.data });
      break;
    case "calibration_result":
      dispatch({ type: "calibration/GotResult", data: msg.data });
      break;
    case "calibration_step":
      dispatch({ type: "calibration/GotStep", data: msg.data });
      break;
    case "calibration_error":
      dispatch({ type: "calibration/GotError", data: msg.data });
      break;
    case "simulation_result":
      dispatch({ type: "simulation/GotResult", data: msg.data });
      break;
    case "simulation_error":
      dispatch({ type: "simulation/GotError", data: msg.data });
      break;
    case "projection_result":
      dispatch({ type: "projection/GotResult", data: msg.data });
      break;
    case "projection_error":
      dispatch({ type: "projection/GotError", data: msg.data });
      break;
    default:
      console.error("Unknown websocket message:", msg.type);
      break;
  }
}

/********/
/* view */
/********/

async function initView(model, dispatch) {
  await injectSvgSprite();
  document.body.append(
    create("main", {}, [
      create("div", { id: "canvas" }),
      create("div", { id: "map" }),
      create("nav", { id: "sidebar" }),
      create("div", { id: "controls" }),
      create(
        "h1",
        { id: "wordmark", title: "HydrOLogical Modeling Educational Software" },
        "HOLMES",
      ),
      settings.initSettingsView(dispatch),
    ]),
  );
  document.body.addEventListener("click", (event) =>
    dispatch({ type: "CheckEscape", data: event }),
  );
  document.body.addEventListener("keydown", (event) =>
    dispatch({ type: "CheckEscape", data: event }),
  );
  loadingView(model);
}

async function injectSvgSprite() {
  if (!document.getElementById("svg-sprite")) {
    try {
      const resp = await fetch("/static/assets/icons/icons.svg");
      if (!resp.ok) {
        console.error("Failed to load SVG sprite:", resp.status);
        return;
      }
      const sprite = await resp.text();
      document.body.insertAdjacentHTML("beforebegin", sprite);
    } catch (e) {
      console.error("Failed to inject SVG sprite:", e);
    }
  }
}

function view(model, dispatch) {
  loadingView(model);
  settings.settingsView(model);
  pipeline.sidebarView(model, dispatch);
  const step = pipeline.stepById[model.step];
  // the map div persists across steps; steps opt in via the descriptor
  document.getElementById("map").classList.toggle("map--hidden", !step.map);
  step.module.controlsView(model, dispatch);
  step.module.canvasView(model, dispatch);
}

function loadingView(model) {
  const loading = model.loading || model.settings.loading;

  const faviconLink = document.querySelector("link[rel~='icon']");
  if (!faviconLink) return;

  if (loading) {
    if (!faviconLink.href.endsWith("/loading.svg")) {
      faviconLink.href = "/static/assets/icons/loading.svg";
    }
  } else {
    if (!faviconLink.href.endsWith("/favicon.svg")) {
      faviconLink.href = "/static/assets/icons/favicon.svg";
    }
  }
}

/********/
/* init */
/********/

async function init() {
  let queue = [];
  let processing = false;

  let model = initModel();

  const processQueue = async () => {
    processing = true;
    while (queue.length > 0) {
      const msg = queue.shift();
      model = await update(model, msg, dispatch);
      console.log(msg, model);
      view(model, dispatch);
    }
    processing = false;
  };

  const dispatch = async (msg) => {
    queue.push(msg);
    if (!processing) {
      processQueue();
    }
  };

  // a reload can land inside the coalescing window, so the pending write is
  // forced out before the page goes away
  window.addEventListener("pagehide", flushPersist);

  await initView(model, dispatch);
  initialMsg.forEach((msg) => {
    dispatch(msg);
  });
}

window.addEventListener("load", init);
