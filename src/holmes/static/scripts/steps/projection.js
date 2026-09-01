import { clear, create, createLoading } from "../utils/elements.js";
import { regimeView, splitColumnView } from "../utils/plot.js";
import { downloadBlob, toCsv } from "../utils/export.js";
import { modelLabels } from "../utils/misc.js";
import { t } from "../utils/text.js";
import { complete } from "../pipeline.js";

/*********/
/* model */
/*********/

// the keys are the labels of the data's `ensemble` column, which is what the
// server filters on; the pairing here only drives the controls (the server
// validates against the data), and member counts are echoed by the server
// (read from the data), never hardcoded
const climateModels = [
  { key: "ClimEx", label: "ClimEx (CRCM5)", scenarios: ["rcp8.5"] },
  {
    key: "ESPO-G6-R2",
    label: "ESPO-G6-R2 (CMIP6)",
    scenarios: ["ssp2-4.5", "ssp3-7.0"],
  },
];
const scenarioLabels = {
  "rcp8.5": "RCP8.5",
  "ssp2-4.5": "SSP2-4.5",
  "ssp3-7.0": "SSP3-7.0",
};
const horizons = ["2020-2049", "2040-2069", "2070-2099"];

// column order of the indicators figure; keys match the server payload
// `band` groups the columns onto the two segments of the chart's split y
// scale: the minima are two orders of magnitude below the freshet maxima and
// show no spread at all when they share a scale with them
const indicatorColumns = [
  { key: "winter_min", label: t("Winter min", "Min hiver"), band: "low" },
  {
    key: "spring_max",
    label: t("Spring max", "Max printemps"),
    band: "high",
  },
  { key: "summer_min", label: t("Summer min", "Min été"), band: "low" },
  { key: "autumn_max", label: t("Autumn max", "Max automne"), band: "high" },
];

const defaultSettings = {
  climateModel: "ClimEx",
  scenario: "rcp8.5",
  horizon: "2020-2049",
};

// only the settings survive a reload: the result holds hundreds of member
// curves (far too large for localStorage) and is refetched on view
export function initProjection(saved) {
  const stored = saved && typeof saved === "object" ? saved : {};
  return {
    settings: initSettings(stored.settings ?? null),
    // the key of the in-flight request, recorded even when the socket was
    // closed so the view stops re-dispatching; Connected clears it to retry
    requestKey: null,
    requestId: 0,
    result: null,
    // per-scenario member counts from the last reply, for the tab labels
    memberCounts: null,
    hover: null,
  };
}

function initSettings(saved) {
  const stored = saved && typeof saved === "object" ? saved : {};
  const climate =
    climateModels.find((c) => c.key === stored.climateModel) ??
    climateModels[0];
  return {
    climateModel: climate.key,
    // a stale localStorage can never produce a scenario the climate model
    // does not serve
    scenario: climate.scenarios.includes(stored.scenario)
      ? stored.scenario
      : climate.scenarios[0],
    horizon: horizons.includes(stored.horizon)
      ? stored.horizon
      : defaultSettings.horizon,
  };
}

/**********/
/* update */
/**********/

export function update(model, msg) {
  switch (msg.type) {
    case "projection/GetResult": {
      const proj = model.projection;
      const key = requestKey(model);
      if (
        key === null ||
        proj.result?.key === key ||
        proj.requestKey === key
      ) {
        return model;
      }
      // a new id supersedes any earlier reply still in flight
      const requestId = proj.requestId + 1;
      if (model.ws?.readyState === WebSocket.OPEN) {
        model.ws.send(
          JSON.stringify({
            type: "projection_data",
            ...requestParams(model),
            requestId,
          }),
        );
      }
      return { ...model, projection: { ...proj, requestKey: key, requestId } };
    }
    case "projection/GotResult": {
      const proj = model.projection;
      // drop a superseded reply: the echoed id must match the live request
      if (msg.data.requestId !== proj.requestId || proj.requestKey === null) {
        return model;
      }
      const next = {
        ...model,
        projection: {
          ...proj,
          memberCounts: msg.data.memberCounts ?? proj.memberCounts,
          result: {
            key: proj.requestKey,
            results: msg.data.results,
            median: msg.data.median,
            historical: msg.data.historical,
          },
        },
      };
      // the step provides no config keys, so autoComplete never fires; it is
      // done the moment a result for the current upstream context lands
      return complete(next, "projection");
    }
    case "projection/GotError":
      // the pending key deliberately stays: clearing it would make
      // fetch-on-view re-send immediately and hammer a failing server in a
      // loop. a reconnect (or any context change) clears it and retries
      console.error(msg.data.message);
      return model;
    case "projection/SetClimateModel": {
      const proj = model.projection;
      const climate = climateModels.find((c) => c.key === msg.data);
      if (!climate) {
        return model;
      }
      // the settings are part of the request key, so fetch-on-view refires;
      // the scenario follows the climate model when it no longer applies
      return {
        ...model,
        projection: {
          ...proj,
          settings: {
            ...proj.settings,
            climateModel: climate.key,
            scenario: climate.scenarios.includes(proj.settings.scenario)
              ? proj.settings.scenario
              : climate.scenarios[0],
          },
        },
      };
    }
    case "projection/SetScenario": {
      const proj = model.projection;
      return {
        ...model,
        projection: {
          ...proj,
          settings: { ...proj.settings, scenario: msg.data },
        },
      };
    }
    case "projection/SetHorizon": {
      const proj = model.projection;
      return {
        ...model,
        projection: {
          ...proj,
          settings: { ...proj.settings, horizon: msg.data },
        },
      };
    }
    case "projection/Hover":
      // a lone model has nothing to be picked out from (the row highlight
      // already skips it), so its traces must not dim under the cursor
      if ((model.config.hydroModels ?? []).length < 2) {
        return model;
      }
      return {
        ...model,
        projection: { ...model.projection, hover: msg.data },
      };
    case "projection/Rerender":
      return { ...model };
    case "projection/Export":
      exportResults(model);
      return model;
    default:
      return model;
  }
}

// the request carries everything the run depends on: the simulation station
// and period (the historical reference simulates the observed weather over
// that period), the simulation step's warmup, the weather method, the
// ensemble and its calibrated parameters, and the climate picks. the snow
// parameters are identical for every model by construction, so one array
// rides for all of them
function requestParams(model) {
  const config = model.config;
  const settings = model.projection.settings;
  const station = config.simulationStation;
  const period = config.simulationPeriod;
  const method = config.weatherMethod;
  const models = config.hydroModels ?? [];
  const params = config.params;
  if (!station || !period || !method || models.length === 0 || !params) {
    return null;
  }
  const hydroParams = {};
  for (const m of models) {
    const hydro = params.models?.[m]?.hydro;
    if (!hydro) {
      return null;
    }
    hydroParams[m] = hydro.map(Number);
  }
  return {
    station,
    start: period.start,
    end: period.end,
    method,
    n_stations: config.weatherNStations,
    hydroModels: models,
    snowModel: config.snowModel,
    hydroParams,
    snowParams: params.models?.[models[0]]?.snow ?? null,
    // the same warmup the simulation step uses, so the two references agree
    warmupYears: model.simulation.settings.warmupYears,
    climateModel: settings.climateModel,
    scenario: settings.scenario,
    horizon: settings.horizon,
  };
}

function requestKey(model) {
  const p = requestParams(model);
  return p
    ? [
        p.station,
        p.start,
        p.end,
        p.method,
        p.n_stations,
        p.hydroModels.join(),
        p.snowModel,
        JSON.stringify(p.hydroParams),
        JSON.stringify(p.snowParams),
        p.warmupYears,
        p.climateModel,
        p.scenario,
        p.horizon,
      ].join("|")
    : null;
}

/********/
/* view */
/********/

export function controlsView(model, dispatch) {
  const controls = document.getElementById("controls");
  // structure is built once per step entry, then reconciled in place:
  // rebuilding under a click swallows it
  if (controls.dataset.step !== "projection") {
    controls.dataset.step = "projection";
    clear(controls);
    controls.append(
      create("h2", {}, t("Projection", "Projection")),
      climateModelField(model, dispatch),
      segField(t("Scenario", "Scénario"), "projection__scenario"),
      segField(t("Horizon", "Horizon"), "projection__horizon"),
      create("div", { id: "projection__models" }),
      create("div", { class: "simulation__actions" }, [
        create(
          "button",
          { id: "projection__export", type: "button" },
          t("Export", "Exporter"),
          [
            {
              event: "click",
              fct: () => dispatch({ type: "projection/Export" }),
            },
          ],
        ),
      ]),
    );
  }
  syncControls(model, dispatch);
}

function climateModelField(model, dispatch) {
  return create("label", { class: "controls__field" }, [
    create("span", {}, t("Climate model", "Modèle climatique")),
    create(
      "select",
      { id: "projection__climate-model" },
      climateModels.map((c) =>
        create(
          "option",
          c.key === model.projection.settings.climateModel
            ? { value: c.key, selected: "" }
            : { value: c.key },
          c.label,
        ),
      ),
      [
        {
          event: "change",
          // read the value fresh (never a stale closure over the model)
          fct: () =>
            dispatch({
              type: "projection/SetClimateModel",
              data: document.getElementById("projection__climate-model")
                .value,
            }),
        },
      ],
    ),
  ]);
}

// the segmented pills are (re)filled by the sync functions, since their
// button count depends on the climate model
function segField(label, id) {
  return create("div", { class: "controls__field" }, [
    create("span", {}, label),
    create("div", { id, class: "projection__seg" }),
  ]);
}

function syncControls(model, dispatch) {
  syncClimateModel(model);
  syncScenario(model, dispatch);
  syncHorizon(model, dispatch);
  syncModelRows(model, dispatch);
  document.getElementById("projection__export").disabled =
    currentResult(model) === null;
}

function syncClimateModel(model) {
  const select = document.getElementById("projection__climate-model");
  if (document.activeElement !== select) {
    select.value = model.projection.settings.climateModel;
  }
}

function syncScenario(model, dispatch) {
  const proj = model.projection;
  const seg = document.getElementById("projection__scenario");
  const climate = climateModels.find(
    (c) => c.key === proj.settings.climateModel,
  );
  // buttons are rebuilt only when the climate model changes their count;
  // labels and the selected state reconcile in place so a click is never
  // swallowed by a rebuild
  if (seg.dataset.signature !== climate.key) {
    seg.dataset.signature = climate.key;
    clear(seg);
    climate.scenarios.forEach((s) =>
      seg.append(
        create(
          "button",
          { type: "button", class: "projection__seg-btn", "data-value": s },
          "",
          [
            {
              event: "click",
              fct: () => dispatch({ type: "projection/SetScenario", data: s }),
            },
          ],
        ),
      ),
    );
  }
  seg.querySelectorAll("button").forEach((btn) => {
    const s = btn.dataset.value;
    const count = proj.memberCounts?.[s];
    btn.textContent = count
      ? `${scenarioLabels[s]} (${count} ${t("members", "membres")})`
      : scenarioLabels[s];
    btn.classList.toggle(
      "projection__seg-btn--selected",
      s === proj.settings.scenario,
    );
  });
}

function syncHorizon(model, dispatch) {
  const seg = document.getElementById("projection__horizon");
  if (!seg.dataset.signature) {
    seg.dataset.signature = "horizons";
    horizons.forEach((h) =>
      seg.append(
        create(
          "button",
          { type: "button", class: "projection__seg-btn", "data-value": h },
          h.replace("-", "–"),
          [
            {
              event: "click",
              fct: () => dispatch({ type: "projection/SetHorizon", data: h }),
            },
          ],
        ),
      ),
    );
  }
  seg.querySelectorAll("button").forEach((btn) => {
    btn.classList.toggle(
      "projection__seg-btn--selected",
      btn.dataset.value === model.projection.settings.horizon,
    );
  });
}

function syncModelRows(model, dispatch) {
  const proj = model.projection;
  const container = document.getElementById("projection__models");
  const models = model.config.hydroModels ?? [];
  // rows are rebuilt only when the ensemble changes, so a hover is never
  // interrupted by a rebuild underneath the cursor
  const signature = models.join();
  if (container.dataset.signature !== signature) {
    container.dataset.signature = signature;
    clear(container);
    models.forEach((m) => container.append(modelRow(m, dispatch)));
  }
  models.forEach((m) => {
    const row = container.querySelector(
      `.projection__model[data-model="${m}"]`,
    );
    // the highlight exists to pick one model out of an ensemble; with a lone
    // model there is nothing to pick it out from
    row.classList.toggle(
      "projection__model--highlight",
      proj.hover === m && models.length > 1,
    );
  });
}

// no metric chip: there are no observations in the projection window to
// score against
function modelRow(m, dispatch) {
  return create(
    "div",
    { class: "projection__model", "data-model": m },
    [create("b", {}, modelLabels[m] ?? m)],
    [
      {
        event: "mouseenter",
        fct: () => dispatch({ type: "projection/Hover", data: m }),
      },
      {
        event: "mouseleave",
        fct: () => dispatch({ type: "projection/Hover", data: null }),
      },
    ],
  );
}

export function canvasView(model, dispatch) {
  const canvas = document.getElementById("canvas");
  if (canvas.dataset.step !== "projection") {
    canvas.dataset.step = "projection";
    clear(canvas);
    // inside #canvas so other steps' clearing removes the panel for free
    canvas.append(
      create("div", { id: "projection-charts" }, [
        chartFigure("regime"),
        chartFigure("indicators"),
      ]),
    );
    observePanelResize(dispatch);
  }
  fetchOnView(model, dispatch);
  chartsView(model);
}

// only the regime figure is captioned; the indicators chart says what it
// plots in its y-axis title, and an empty figcaption would still eat a line
function chartFigure(name) {
  return create("figure", { id: `projection__${name}` }, [
    ...(name === "regime" ? [create("figcaption", {})] : []),
    create("div", { class: "hydrographs__loading" }, [createLoading()]),
    create("svg", { class: "plot", id: `projection__${name}-svg` }),
  ]);
}

// charts must re-read their box on resize, so a debounced no-op message
// re-runs the view and the size signature forces the redraw
function observePanelResize(dispatch) {
  let timeout;
  const observer = new ResizeObserver(() => {
    clearTimeout(timeout);
    timeout = setTimeout(() => dispatch({ type: "projection/Rerender" }), 100);
  });
  observer.observe(document.getElementById("projection-charts"));
}

// fetch-on-view: fires on first entry and whenever an upstream change
// (station, method, ensemble, params) or a picker moves the key
function fetchOnView(model, dispatch) {
  const proj = model.projection;
  const key = requestKey(model);
  if (key !== null && key !== proj.result?.key && key !== proj.requestKey) {
    dispatch({ type: "projection/GetResult" });
  }
}

function chartsView(model) {
  const current = currentResult(model);
  const loading = current === null;
  for (const name of ["regime", "indicators"]) {
    document
      .getElementById(`projection__${name}`)
      .classList.toggle("hydrographs__figure--loading", loading);
  }
  if (loading) {
    return;
  }
  captionsView(model);
  regimeChartView(model, current);
  indicatorsChartView(model, current);
  hoverHighlightView(model.projection.hover);
}

function captionsView(model) {
  const { scenario, horizon } = model.projection.settings;
  const id = model.config.simulationStation;
  const station = model.stations?.find((s) => s.id === id);
  document
    .getElementById("projection__regime")
    .querySelector("figcaption").textContent =
    `${station ? station.name : id} — ${scenarioLabels[scenario]} ${horizon.replace("-", "–")}`;
}

function regimeChartView(model, current) {
  const svg = document.getElementById("projection__regime-svg");
  const signature = chartSignature(current, svg);
  if (svg.dataset.signature === signature) {
    return;
  }
  svg.dataset.signature = signature;

  const models = (model.config.hydroModels ?? []).filter(
    (m) => current.results[m],
  );
  const series = models.flatMap((m) =>
    Object.entries(current.results[m].members).map(([member, data]) => ({
      key: `${m}/${member}`,
      model: m,
      kind: "member",
      points: regimePoints(data.regime),
    })),
  );
  // a lone model's median is the complete median, so drawing both would
  // just double one line
  if (models.length > 1) {
    series.push(
      ...models.map((m) => ({
        key: m,
        model: m,
        kind: "model",
        points: regimePoints(current.results[m].medianRegime),
      })),
    );
  }
  series.push({
    key: "historical",
    kind: "historical",
    // green, the simulation station's colour
    colour: "green",
    label: historicalLabel(model.config.simulationPeriod),
    points: regimePoints(current.historical?.regime ?? []),
  });
  series.push({
    key: "median",
    kind: "median",
    points: regimePoints(current.median?.regime ?? []),
  });
  regimeView(svg, series, {
    label: t("Streamflow (mm/day)", "Débit (mm/jour)"),
  });
}

// the reference is the observed weather simulated over the simulation
// period, so the legend names that period
function historicalLabel(period) {
  return period
    ? `${t("historical", "historique")} (${period.start} – ${period.end})`
    : t("historical", "historique");
}

function regimePoints(regime) {
  return regime.map((v, i) => ({ x: i + 1, y: v }));
}

function indicatorsChartView(model, current) {
  const svg = document.getElementById("projection__indicators-svg");
  const signature = chartSignature(current, svg);
  if (svg.dataset.signature === signature) {
    return;
  }
  svg.dataset.signature = signature;

  const models = (model.config.hydroModels ?? []).filter(
    (m) => current.results[m],
  );
  const columns = indicatorColumns.map(({ key, label, band }) => ({
    key,
    label,
    band,
    dots: models.flatMap((m) =>
      Object.values(current.results[m].members).map((member) => ({
        model: m,
        value: member.indicators?.[key] ?? null,
      })),
    ),
    median: current.median?.indicators?.[key] ?? null,
    historical: current.historical?.indicators?.[key] ?? null,
  }));
  splitColumnView(svg, columns, {
    historicalLabel: historicalLabel(model.config.simulationPeriod),
    label: t("Indicators (mm/day)", "Indicateurs (mm/jour)"),
  });
}

// everything that should force a redraw; matching it preserves the brush
// zoom. the key already carries the ensemble, params and climate picks
function chartSignature(current, svg) {
  return [current.key, `${svg.clientWidth}x${svg.clientHeight}`].join("|");
}

// cross-highlight the hovered model across both charts without redrawing:
// dim the others while a hover is active, clear both classes when none is
function hoverHighlightView(hover) {
  for (const id of ["projection__regime-svg", "projection__indicators-svg"]) {
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
  // the dot chart has no content group: restore the reference ticks on top,
  // then raise the hovered model's dots above the rest of the cloud (the
  // ticks keep painting over everything)
  const dots = document.getElementById("projection__indicators-svg");
  if (hover) {
    dots
      .querySelectorAll(`circle[data-model="${hover}"]`)
      .forEach((c) => dots.appendChild(c));
  }
  // scoped to direct children: the legend swatches are .series-tick as well,
  // and appending them here would move them out of their translated group
  dots
    .querySelectorAll(":scope > .series-tick")
    .forEach((tick) => dots.appendChild(tick));
}

// SVG paints in document order, so the hovered model is moved to the end of
// its group to read over the model medians; clearing the hover restores the
// order the draw recorded (the complete median carries no data-model, so it
// stays on top either way)
function raiseHovered(content, hover) {
  // reset first, so moving from one hovered model to the next does not leave
  // the previous one stranded on top
  const paths = [...content.querySelectorAll("path.series-line")].sort(
    (a, b) => a.dataset.order - b.dataset.order,
  );
  paths.forEach((p) => content.append(p));
  if (!hover) {
    return;
  }
  // raise the model's members first, then its median so it reads over them
  paths
    .filter((p) => p.getAttribute("data-model") === hover)
    .sort((a, b) => a.dataset.order - b.dataset.order)
    .forEach((p) => content.append(p));
}

function exportResults(model) {
  const p = requestParams(model);
  const current = currentResult(model);
  if (!p || !current) {
    return;
  }
  const models = (model.config.hydroModels ?? []).filter(
    (m) => current.results[m],
  );
  const base = `projection_${p.station}_${p.climateModel}_${p.scenario}_${p.horizon}`;
  downloadBlob(
    `${base}.json`,
    "application/json",
    JSON.stringify(exportJson(model, p, current, models), null, 2),
  );
  downloadBlob(
    `${base}_regime.csv`,
    "text/csv",
    exportRegimeCsv(current, models),
  );
  downloadBlob(
    `${base}_indicators.csv`,
    "text/csv",
    exportIndicatorsCsv(current, models),
  );
}

function exportJson(model, p, current, models) {
  const out = {};
  for (const m of models) {
    out[m] = {
      hydro: model.config.params.models?.[m]?.hydro ?? null,
      snow: model.config.params.models?.[m]?.snow ?? null,
      medianIndicators: current.results[m]?.medianIndicators ?? null,
    };
  }
  return {
    config: {
      station: p.station,
      weatherMethod: p.method,
      weatherNStations: p.n_stations,
      snowModel: model.config.snowModel,
      warmupYears: p.warmupYears,
      climateModel: p.climateModel,
      scenario: p.scenario,
      horizon: p.horizon,
    },
    models: out,
    // a lone model's member-median *is* the overall median (the charts merge
    // them too), so the field would only duplicate its medianIndicators
    ...(models.length > 1
      ? { median: { indicators: current.median?.indicators ?? null } }
      : {}),
    historical: { indicators: current.historical?.indicators ?? null },
  };
}

function exportRegimeCsv(current, models) {
  const withMedian = models.length > 1;
  const header = [
    "day_of_year",
    ...models,
    ...(withMedian ? ["median"] : []),
    "historical",
  ];
  const rows = (current.median?.regime ?? []).map((_, i) => {
    const cells = [i + 1];
    for (const m of models) {
      cells.push(current.results[m]?.medianRegime?.[i] ?? null);
    }
    if (withMedian) {
      cells.push(current.median?.regime?.[i] ?? null);
    }
    cells.push(current.historical?.regime?.[i] ?? null);
    return cells;
  });
  return toCsv(header, rows);
}

function exportIndicatorsCsv(current, models) {
  const keys = indicatorColumns.map((c) => c.key);
  const header = ["model", "member", ...keys];
  const rows = [];
  for (const m of models) {
    for (const [member, data] of Object.entries(
      current.results[m]?.members ?? {},
    )) {
      rows.push([m, member, ...keys.map((k) => data.indicators?.[k] ?? null)]);
    }
    // the per-model median (across climate members) stays informative even
    // for a lone model
    rows.push([
      m,
      "median",
      ...keys.map((k) => current.results[m]?.medianIndicators?.[k] ?? null),
    ]);
  }
  // the overall median duplicates the lone model's median row above
  if (models.length > 1) {
    rows.push([
      "all",
      "median",
      ...keys.map((k) => current.median?.indicators?.[k] ?? null),
    ]);
  }
  rows.push([
    "historical",
    "",
    ...keys.map((k) => current.historical?.indicators?.[k] ?? null),
  ]);
  return toCsv(header, rows);
}

/**********/
/* shared */
/**********/

// the stored result, but only while it still describes the current upstream
// context; a stale one keeps the panel in its loading state instead
function currentResult(model) {
  const proj = model.projection;
  const key = requestKey(model);
  return proj.result?.key === key ? proj.result : null;
}
