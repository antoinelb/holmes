import { clear, create, createLoading, createSlider } from "../utils/elements.js";
import { dotProfileView, multiSeriesView } from "../utils/plot.js";
import { downloadBlob, toCsv } from "../utils/export.js";
import { complete } from "../pipeline.js";

/*********/
/* model */
/*********/

// the six display metrics of the old holmes simulation screen, all with an
// optimal value of 1; the order is the row order of the dot profile
const metricRows = [
  { key: "kge", label: "High flows (KGE)" },
  { key: "kge_sqrt", label: "Medium flows (KGE-sqrt)" },
  { key: "kge_log", label: "Low flows (KGE-log)" },
  { key: "mean_bias", label: "Water balance" },
  { key: "deviation_bias", label: "Flow variability" },
  { key: "correlation", label: "Correlation" },
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

// shorter than calibration's default 3: the simulation period is typically a
// few years, and the warmup band would otherwise swallow most of it
const defaultSettings = { warmupYears: 1 };

// only the settings survive a reload: the result holds full daily series per
// model (far too large for localStorage) and is refetched on view
export function initSimulation(saved) {
  const stored = saved && typeof saved === "object" ? saved : {};
  return {
    settings: initSettings(stored.settings ?? null),
    // the key of the in-flight request, recorded even when the socket was
    // closed so the view stops re-dispatching; Connected clears it to retry
    requestKey: null,
    requestId: 0,
    result: null,
    hover: null,
  };
}

function initSettings(saved) {
  if (saved === null || typeof saved !== "object") {
    return { ...defaultSettings };
  }
  return {
    ...defaultSettings,
    // clamped to the slider's 0–5 range rather than trusted
    warmupYears: Number.isInteger(saved.warmupYears)
      ? Math.min(Math.max(saved.warmupYears, 0), 5)
      : defaultSettings.warmupYears,
  };
}

/**********/
/* update */
/**********/

export function update(model, msg) {
  switch (msg.type) {
    case "simulation/GetResult": {
      const sim = model.simulation;
      const key = requestKey(model.config, sim.settings);
      if (key === null || sim.result?.key === key || sim.requestKey === key) {
        return model;
      }
      // a new id supersedes any earlier reply still in flight
      const requestId = sim.requestId + 1;
      if (model.ws?.readyState === WebSocket.OPEN) {
        model.ws.send(
          JSON.stringify({
            type: "simulation_data",
            ...requestParams(model.config, sim.settings),
            requestId,
          }),
        );
      }
      return { ...model, simulation: { ...sim, requestKey: key, requestId } };
    }
    case "simulation/GotResult": {
      const sim = model.simulation;
      // drop a superseded reply: the echoed id must match the live request
      if (msg.data.requestId !== sim.requestId || sim.requestKey === null) {
        return model;
      }
      // convert the date grid once on arrival
      const dates = msg.data.data.map((d) => new Date(d.datetime * 1000));
      const observations = msg.data.data.map((d) => d.streamflow);
      const next = {
        ...model,
        simulation: {
          ...sim,
          result: {
            key: sim.requestKey,
            dates,
            observations,
            results: msg.data.results,
            median: msg.data.median,
          },
        },
      };
      // the step provides no config keys, so autoComplete never fires; it is
      // done the moment a result for the current upstream context lands
      return complete(next, "simulation");
    }
    case "simulation/GotError":
      // the pending key deliberately stays: clearing it would make
      // fetch-on-view re-send immediately and hammer a failing server in a
      // loop. a reconnect (or any context change) clears it and retries
      console.error(msg.data.message);
      return model;
    case "simulation/SetWarmup": {
      const sim = model.simulation;
      // the warmup is part of the request key, so fetch-on-view refires; the
      // stale result stays drawn under the loading state until it lands
      return {
        ...model,
        simulation: {
          ...sim,
          settings: { ...sim.settings, warmupYears: msg.data },
        },
      };
    }
    case "simulation/Hover":
      return {
        ...model,
        simulation: { ...model.simulation, hover: msg.data },
      };
    case "simulation/Rerender":
      return { ...model };
    case "simulation/Export":
      exportResults(model);
      return model;
    default:
      return model;
  }
}

// the request carries everything the run depends on: the simulation station
// and period, the weather method, the ensemble and its calibrated parameters.
// the snow parameters (incl. the calibration-window qnbv) are identical for
// every model by construction, so one array rides for all of them
function requestParams(config, settings) {
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
    warmupYears: settings.warmupYears,
  };
}

function requestKey(config, settings) {
  const p = requestParams(config, settings);
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
  if (controls.dataset.step !== "simulation") {
    controls.dataset.step = "simulation";
    clear(controls);
    controls.append(
      create("h2", {}, "Simulation"),
      warmupField(model, dispatch),
      create("div", { id: "simulation__models" }),
      create("div", { class: "simulation__actions" }, [
        create(
          "button",
          { id: "simulation__export", type: "button" },
          "Export",
          [
            {
              event: "click",
              fct: () => dispatch({ type: "simulation/Export" }),
            },
          ],
        ),
      ]),
    );
  }
  syncControls(model, dispatch);
}

function warmupField(model, dispatch) {
  return create("label", { class: "controls__field" }, [
    create("span", {}, "Warmup years"),
    createSlider(
      "simulation__warmup",
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
              type: "simulation/SetWarmup",
              data: Number(
                document.getElementById("simulation__warmup").value,
              ),
            }),
        },
      ],
      model.simulation.settings.warmupYears,
    ),
  ]);
}

function syncControls(model, dispatch) {
  syncWarmup(model);
  syncModelRows(model, dispatch);
  const current = currentResult(model);
  document.getElementById("simulation__export").disabled = current === null;
}

// the slider is two inputs (number + range): both mirror the model unless
// one is mid-edit
function syncWarmup(model) {
  const warmup = document.getElementById("simulation__warmup");
  const range = warmup.parentNode.querySelector("input[type='range']");
  if (
    document.activeElement !== warmup &&
    document.activeElement !== range
  ) {
    warmup.value = model.simulation.settings.warmupYears;
    range.value = model.simulation.settings.warmupYears;
  }
}

function syncModelRows(model, dispatch) {
  const sim = model.simulation;
  const container = document.getElementById("simulation__models");
  const models = model.config.hydroModels ?? [];
  // rows are rebuilt only when the ensemble changes, so a hover is never
  // interrupted by a rebuild underneath the cursor
  const signature = models.join();
  if (container.dataset.signature !== signature) {
    container.dataset.signature = signature;
    clear(container);
    models.forEach((m) => container.append(modelRow(m, dispatch)));
  }
  const current = currentResult(model);
  models.forEach((m) => {
    const row = container.querySelector(
      `.simulation__model[data-model="${m}"]`,
    );
    // the highlight exists to pick one model out of an ensemble; with a lone
    // model there is nothing to pick it out from
    row.classList.toggle(
      "simulation__model--highlight",
      sim.hover === m && models.length > 1,
    );
    document.getElementById(`simulation__chip-${m}`).textContent =
      `kge ${formatObjective(current?.results?.[m]?.metrics?.kge)}`;
  });
}

function modelRow(m, dispatch) {
  return create(
    "div",
    { class: "simulation__model", "data-model": m },
    [
      create("b", {}, modelLabels[m] ?? m),
      create(
        "span",
        { class: "simulation__metric", id: `simulation__chip-${m}` },
        "kge —",
      ),
    ],
    [
      {
        event: "mouseenter",
        fct: () => dispatch({ type: "simulation/Hover", data: m }),
      },
      {
        event: "mouseleave",
        fct: () => dispatch({ type: "simulation/Hover", data: null }),
      },
    ],
  );
}

export function canvasView(model, dispatch) {
  const canvas = document.getElementById("canvas");
  if (canvas.dataset.step !== "simulation") {
    canvas.dataset.step = "simulation";
    clear(canvas);
    // inside #canvas so other steps' clearing removes the panel for free
    canvas.append(
      create("div", { id: "simulation-charts" }, [
        chartFigure("metrics"),
        chartFigure("streamflow"),
      ]),
    );
    observePanelResize(dispatch);
  }
  fetchOnView(model, dispatch);
  chartsView(model);
}

function chartFigure(name) {
  return create("figure", { id: `simulation__${name}` }, [
    create("figcaption", {}),
    create("div", { class: "hydrographs__loading" }, [createLoading()]),
    create("svg", { class: "plot", id: `simulation__${name}-svg` }),
  ]);
}

// charts must re-read their box on resize, so a debounced no-op message
// re-runs the view and the size signature forces the redraw
function observePanelResize(dispatch) {
  let timeout;
  const observer = new ResizeObserver(() => {
    clearTimeout(timeout);
    timeout = setTimeout(() => dispatch({ type: "simulation/Rerender" }), 100);
  });
  observer.observe(document.getElementById("simulation-charts"));
}

// fetch-on-view: fires on first entry and whenever an upstream change
// (station, period, method, ensemble, params or warmup) moves the key
function fetchOnView(model, dispatch) {
  const sim = model.simulation;
  const key = requestKey(model.config, sim.settings);
  if (key !== null && key !== sim.result?.key && key !== sim.requestKey) {
    dispatch({ type: "simulation/GetResult" });
  }
}

function chartsView(model) {
  const current = currentResult(model);
  const loading = current === null;
  for (const name of ["metrics", "streamflow"]) {
    document
      .getElementById(`simulation__${name}`)
      .classList.toggle("hydrographs__figure--loading", loading);
  }
  if (loading) {
    return;
  }
  captionsView(model);
  metricsChartView(model, current);
  streamflowChartView(model, current);
  hoverHighlightView(model.simulation.hover);
}

function captionsView(model) {
  document
    .getElementById("simulation__metrics")
    .querySelector("figcaption").textContent = "Metrics";
  const id = model.config.simulationStation;
  const station = model.stations?.find((s) => s.id === id);
  document
    .getElementById("simulation__streamflow")
    .querySelector("figcaption").textContent = station
    ? `${station.name} (${id})`
    : "Streamflow";
}

function metricsChartView(model, current) {
  const svg = document.getElementById("simulation__metrics-svg");
  const signature = chartSignature(current, svg);
  if (svg.dataset.signature === signature) {
    return;
  }
  svg.dataset.signature = signature;

  const models = model.config.hydroModels ?? [];
  const rows = metricRows.map((metric) => ({
    key: metric.key,
    label: metric.label,
    dots: models.map((m) => ({
      model: m,
      value: current.results[m]?.metrics?.[metric.key] ?? null,
    })),
    median: current.median?.metrics?.[metric.key] ?? null,
  }));
  dotProfileView(svg, rows, { reference: 1 });
}

function streamflowChartView(model, current) {
  const svg = document.getElementById("simulation__streamflow-svg");
  const signature = chartSignature(current, svg);
  if (svg.dataset.signature === signature) {
    return;
  }
  svg.dataset.signature = signature;

  const dates = current.dates;
  const withSims = (model.config.hydroModels ?? []).filter(
    (m) => current.results[m]?.simulation != null,
  );
  const series = simulationSeries(
    withSims,
    (m) =>
      dates.map((d, i) => ({
        x: d,
        y: current.results[m].simulation[i] ?? null,
      })),
    () =>
      dates.map((d, i) => ({
        x: d,
        y: current.median?.simulation?.[i] ?? null,
      })),
  );
  series.push({
    key: "observations",
    kind: "observations",
    // green, the simulation station's colour; purple stays calibration's
    colour: "green",
    points: dates.map((d, i) => ({ x: d, y: current.observations[i] })),
  });
  // the series carries the warmup lead ahead of the period, so the band runs
  // from its start to the period start rather than a row count into it
  const period = model.config.simulationPeriod;
  const warmupEnd =
    model.simulation.settings.warmupYears > 0 && dates.length && period
      ? new Date(period.start)
      : null;
  multiSeriesView(svg, series, {
    xType: "time",
    label: "Streamflow (mm)",
    warmupEnd,
    reference: null,
  });
}

// same ensemble shape as calibration: one faint line per model plus the
// median on top; a lone model has no ensemble to summarise, so it *is* the
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

// everything that should force a redraw; matching it preserves the brush
// zoom. the key already carries the ensemble, params and warmup
function chartSignature(current, svg) {
  return [current.key, `${svg.clientWidth}x${svg.clientHeight}`].join("|");
}

// cross-highlight the hovered model across both charts without redrawing:
// dim the others while a hover is active, clear both classes when none is
function hoverHighlightView(hover) {
  for (const id of [
    "simulation__metrics-svg",
    "simulation__streamflow-svg",
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
  // the dot chart has no content group: restore the median dots on top, then
  // raise the hovered model's dots above them
  const dots = document.getElementById("simulation__metrics-svg");
  dots
    .querySelectorAll("circle.series-point--median")
    .forEach((c) => dots.appendChild(c));
  if (hover) {
    dots
      .querySelectorAll(`circle[data-model="${hover}"]`)
      .forEach((c) => dots.appendChild(c));
  }
}

// SVG paints in document order, so the hovered model is moved to the end of
// its group to read over the median and the observations; clearing the hover
// restores the order the draw recorded
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
}

function exportResults(model) {
  const p = requestParams(model.config, model.simulation.settings);
  const current = currentResult(model);
  if (!p || !current) {
    return;
  }
  const models = model.config.hydroModels ?? [];
  const base = `simulation_${p.station}_${p.start}_${p.end}`;
  downloadBlob(
    `${base}.json`,
    "application/json",
    JSON.stringify(exportJson(model, p, current, models), null, 2),
  );
  downloadBlob(`${base}.csv`, "text/csv", exportCsv(current, models));
}

function exportJson(model, p, current, models) {
  const out = {};
  for (const m of models) {
    out[m] = {
      hydro: model.config.params.models?.[m]?.hydro ?? null,
      snow: model.config.params.models?.[m]?.snow ?? null,
      metrics: current.results[m]?.metrics ?? null,
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
      warmupYears: model.simulation.settings.warmupYears,
    },
    models: out,
    // a lone model *is* the median (the charts merge them too), so the field
    // would only duplicate it
    ...(models.length > 1
      ? { median: { metrics: current.median?.metrics ?? null } }
      : {}),
  };
}

function exportCsv(current, models) {
  const withMedian = models.length > 1;
  const header = [
    "datetime",
    "observations",
    ...models,
    ...(withMedian ? ["median"] : []),
  ];
  const rows = current.dates.map((d, i) => {
    const cells = [d, current.observations[i]];
    for (const m of models) {
      cells.push(current.results[m]?.simulation?.[i] ?? null);
    }
    if (withMedian) {
      cells.push(current.median?.simulation?.[i] ?? null);
    }
    return cells;
  });
  return toCsv(header, rows);
}

/**********/
/* shared */
/**********/

// the stored result, but only while it still describes the current upstream
// context; a stale one keeps the panel in its loading state instead
function currentResult(model) {
  const sim = model.simulation;
  const key = requestKey(model.config, sim.settings);
  return sim.result?.key === key ? sim.result : null;
}

// ~3 significant figures, or an em dash for a degenerate (null) score
function formatObjective(v) {
  if (v === null || v === undefined || !Number.isFinite(v)) {
    return "—";
  }
  return parseFloat(v.toPrecision(3)).toString();
}
