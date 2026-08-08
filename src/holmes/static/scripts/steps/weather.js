import {
  clear,
  create,
  createIcon,
  createLoading,
  createSlider,
} from "../utils/elements.js";
import { downloadBlob, toCsv } from "../utils/export.js";
import { hydrographView } from "../utils/plot.js";
import { t } from "../utils/text.js";
import { complete } from "../pipeline.js";
import { sharedMapView } from "./stations.js";

// ids match the backend WeatherMethod literal (src/holmes/data/weather.py)
const methods = [
  {
    id: "nearest_stations",
    label: t("Nearest stations", "Stations les plus proches"),
    icon: "share-2",
  },
  { id: "era5", label: "ERA5", icon: "globe" },
  {
    id: "ministry_grid",
    label: t("Ministry grid", "Grille du ministère"),
    icon: "grid",
  },
];

// chart grid rows: precipitation bars above temperature lines
const variables = [
  {
    id: "precipitation",
    label: t("Precipitation (mm)", "Précipitations (mm)"),
    mark: "bar",
  },
  {
    id: "temperature",
    label: t("Temperature (°C)", "Température (°C)"),
    mark: "line",
  },
];
const roles = ["calibration", "simulation"];
const roleLabels = {
  calibration: t("Calibration", "Calage"),
  simulation: t("Simulation", "Simulation"),
};

/**********/
/* update */
/**********/

export function update(model, msg) {
  switch (msg.type) {
    case "weather/GetWeather": {
      const key = requestKey(model);
      if (!model.config.weatherMethod) {
        return model;
      }
      if (model.weather?.key === key) {
        // the data already covers this request; a period change (absent from
        // the key, since the whole record is loaded) still staled the step's
        // snapshot, so re-complete rather than leave it stale until a click
        return model.weather.data !== null
          ? complete(model, "weather")
          : model;
      }
      if (model.ws?.readyState === WebSocket.OPEN) {
        model.ws.send(
          JSON.stringify({
            type: "weather",
            method: model.config.weatherMethod,
            n_stations: model.config.weatherNStations,
            stations: roles
              .map((role) => model.config[`${role}Station`])
              .filter(Boolean),
          }),
        );
      }
      // the key is recorded even when the send is skipped: the view
      // re-dispatches until it changes, so leaving it would spin the queue
      // forever while disconnected; Connected clears it to retry
      // data: null marks the request pending
      return { ...model, weather: { key: key, data: null, grid: null } };
    }
    case "weather/GotWeather": {
      // the backend echoes the request fields so a late reply for a
      // superseded pick is identifiable
      if (
        msg.data.method !== model.config.weatherMethod ||
        msg.data.n_stations !== model.config.weatherNStations
      ) {
        return model;
      }
      // group by station and convert dates once on arrival
      const data = {};
      for (const d of msg.data.data) {
        (data[d.id] ??= []).push({
          // epoch seconds, like streamflow
          date: new Date(d.datetime * 1000),
          precipitation: d.precipitation,
          temperature: d.temperature,
        });
      }
      const next = {
        ...model,
        weather: { ...model.weather, data: data, grid: msg.data.grid ?? [] },
      };
      // the step is only done once the data for the *current* stations is in;
      // a superseded reply leaves it stale until its own reply lands
      return model.weather?.key === requestKey(model)
        ? complete(next, "weather")
        : next;
    }
    case "weather/Export":
      exportWeather(model);
      return model;
    default:
      return model;
  }
}

// the whole loaded record, not the selected period, and one file per role
// since both roles may point at the same station
function exportWeather(model) {
  const data = freshWeather(model);
  for (const role of roles) {
    const id = model.config[`${role}Station`];
    const series = data?.[id];
    if (!series) {
      continue;
    }
    downloadBlob(
      `weather_${model.config.weatherMethod}_${role}_${id}.csv`,
      "text/csv",
      toCsv(
        ["datetime", "precipitation", "temperature"],
        series.map((d) => [d.date, d.precipitation, d.temperature]),
      ),
    );
  }
}

// the cached data only describes the current config while its key matches;
// a superseded or pending load has nothing exportable
function freshWeather(model) {
  return model.weather?.key === requestKey(model) ? model.weather.data : null;
}

// one weather load covers both roles, so the cache is a single entry keyed
// by everything that invalidates it
function requestKey(model) {
  return [
    model.config.weatherMethod,
    model.config.weatherNStations,
    model.config.calibrationStation,
    model.config.simulationStation,
  ].join("|");
}

/********/
/* view */
/********/

export function controlsView(model, dispatch) {
  const controls = document.getElementById("controls");
  // structure is built once per step entry, then reconciled in place:
  // rebuilding under a click swallows it
  if (controls.dataset.step !== "weather") {
    controls.dataset.step = "weather";
    clear(controls);
    controls.append(
      create("h2", {}, t("Weather", "Météo")),
      create(
        "div",
        { class: "controls__methods" },
        methods.map((method) => methodButton(method, dispatch)),
      ),
      nStationsField(model, dispatch),
      create("div", { class: "weather__actions" }, [
        create(
          "button",
          { id: "weather__export", type: "button" },
          t("Export", "Exporter"),
          [
            { event: "click", fct: () => dispatch({ type: "weather/Export" }) },
          ],
        ),
      ]),
    );
  }
  syncControls(model);
}

// only meaningful for nearest_stations, so syncControls hides it otherwise
function nStationsField(model, dispatch) {
  return create(
    "label",
    { id: "controls__n-stations-field", class: "controls__field", hidden: "" },
    [
      create("span", {}, "Stations"),
      createSlider(
        "controls__n-stations",
        1,
        5,
        true,
        // change rather than input, so dragging does not spam refetches
        [{ event: "change", fct: (event) => setNStations(event, dispatch) }],
        model.config.weatherNStations,
      ),
    ],
  );
}

function setNStations(event, dispatch) {
  const value = Math.min(
    Math.max(Math.round(Number(event.target.value)), 1),
    5,
  );
  dispatch({
    type: "SetConfig",
    data: { key: "weatherNStations", value: value },
  });
  // the serial queue processes SetConfig first
  dispatch({ type: "weather/GetWeather" });
}

function methodButton(method, dispatch) {
  return create(
    "button",
    { id: `controls__method-${method.id}`, class: "controls__method" },
    [
      // the circle chrome lives on the div: bordering the svg directly
      // renders unevenly in Chrome
      create("div", { class: "controls__method-icon" }, [
        createIcon(method.icon),
      ]),
      create("span", {}, method.label),
    ],
    [
      {
        event: "click",
        fct: () => {
          dispatch({
            type: "SetConfig",
            data: { key: "weatherMethod", value: method.id },
          });
          // the serial queue processes SetConfig first
          dispatch({ type: "weather/GetWeather" });
        },
      },
    ],
  );
}

function syncControls(model) {
  methods.forEach((method) => {
    document
      .getElementById(`controls__method-${method.id}`)
      .classList.toggle(
        "controls__method--selected",
        model.config.weatherMethod === method.id,
      );
  });
  document.getElementById("controls__n-stations-field").hidden =
    model.config.weatherMethod !== "nearest_stations";
  document.getElementById("weather__export").disabled =
    freshWeather(model) === null;
}

export function canvasView(model, dispatch) {
  const canvas = document.getElementById("canvas");
  if (canvas.dataset.step !== "weather") {
    canvas.dataset.step = "weather";
    clear(canvas);
    // inside #canvas so other steps' clearing removes the panel for free
    canvas.append(
      create(
        "div",
        { id: "weather-charts", hidden: "" },
        variables.flatMap((variable) =>
          roles.map((role) => chartFigure(variable, role)),
        ),
      ),
    );
    observePanelResize(dispatch);
  }

  // showGrid draws the source cells; the stations step omits it, which also
  // clears the layer when navigating back
  sharedMapView(model, dispatch, { selectedOnly: true, showGrid: true });
  fetchWeather(model, dispatch);
  chartsView(model);
}

function chartFigure(variable, role) {
  return create("figure", { id: `weather__${variable.id}-${role}` }, [
    create("figcaption", {}),
    create("div", { class: "hydrographs__loading" }, [createLoading()]),
    create("svg", {
      class: "plot",
      id: `weather__${variable.id}-${role}-svg`,
    }),
  ]);
}

// charts must re-read their box on resize, so a debounced no-op message
// re-runs the view and the size signature forces the redraw
function observePanelResize(dispatch) {
  let timeout;
  const observer = new ResizeObserver(() => {
    clearTimeout(timeout);
    timeout = setTimeout(() => dispatch({ type: "weather/Rerender" }), 100);
  });
  observer.observe(document.getElementById("weather-charts"));
}

// fetch-on-view (like sharedMapView's CreateMap): covers a reload landing on
// this step with a persisted method and station changes invalidating the
// cache; GetWeather sets the key, stopping re-dispatch on later renders
function fetchWeather(model, dispatch) {
  if (
    model.config.weatherMethod &&
    roles.some((role) => model.config[`${role}Station`]) &&
    model.weather?.key !== requestKey(model)
  ) {
    dispatch({ type: "weather/GetWeather" });
  }
}

function chartsView(model) {
  const cells = variables.flatMap((variable) =>
    roles.map((role) => ({
      variable: variable,
      role: role,
      series: cellSeries(model, variable.id, role),
    })),
  );
  // a role with nothing to show drops out of the grid entirely, so the
  // survivor spans the panel rather than leaving a blank column
  const activeRoles = roles.filter((role) =>
    cells.some((cell) => cell.role === role && cell.series !== null),
  );
  // visibility first: chart boxes must be final before anything is drawn
  const panel = document.getElementById("weather-charts");
  panel.hidden = activeRoles.length === 0;
  panel.classList.toggle("weather-charts--single", activeRoles.length === 1);
  for (const cell of cells) {
    const figure = document.getElementById(
      `weather__${cell.variable.id}-${cell.role}`,
    );
    const active = activeRoles.includes(cell.role);
    figure.classList.toggle("hydrographs__figure--absent", !active);
    // a lone missing chart inside a live column keeps its slot instead, so
    // the column below it stays put
    figure.classList.toggle(
      "hydrographs__figure--empty",
      active && cell.series === null,
    );
    figure.classList.toggle(
      "hydrographs__figure--loading",
      cell.series === "loading",
    );
    // captions sit on the top row only; the axis titles name the rows
    if (cell.variable.id === "precipitation" && cell.series !== null) {
      captionView(model, cell.role);
    }
  }
  // the leftmost column on show carries each row's axis title
  for (const cell of cells) {
    if (cell.series !== null && cell.series !== "loading") {
      cellChartView(model, cell, cell.role === activeRoles[0]);
    }
  }
}

// null when the cell has no method, station or data in its window,
// "loading" while the weather data hasn't arrived yet
function cellSeries(model, field, role) {
  const id = model.config[`${role}Station`];
  const period = model.config[`${role}Period`];
  if (!id || !period || !model.config.weatherMethod) {
    return null;
  }
  if (!model.weather || model.weather.data === null) {
    return "loading";
  }
  const data = model.weather.data[id];
  if (!data) {
    return null;
  }
  const start = new Date(period.start);
  const end = new Date(period.end);
  const filtered = data.filter((d) => d.date >= start && d.date <= end);
  return filtered.some((d) => d[field] !== null) ? filtered : null;
}

function captionView(model, role) {
  const id = model.config[`${role}Station`];
  const station = model.stations?.find((s) => s.id === id);
  const label = roleLabels[role];
  document
    .getElementById(`weather__precipitation-${role}`)
    .querySelector("figcaption").textContent = station
    ? `${label} — ${station.name} (${id})`
    : label;
}

function cellChartView(model, cell, showTitle) {
  const id = model.config[`${cell.role}Station`];
  const period = model.config[`${cell.role}Period`];
  const svg = document.getElementById(
    `weather__${cell.variable.id}-${cell.role}-svg`,
  );
  // redrawing on every dispatch would wipe the brush zoom, so redraw only
  // when the plotted data, window, box or title changes
  const signature =
    `${model.weather.key}|${id}|${period.start}|${period.end}` +
    `|${showTitle}|${svg.clientWidth}x${svg.clientHeight}`;
  if (svg.dataset.signature !== signature) {
    svg.dataset.signature = signature;
    hydrographView(
      svg,
      cell.series,
      cell.role === "calibration" ? "purple" : "green",
      {
        field: cell.variable.id,
        label: showTitle ? cell.variable.label : null,
        mark: cell.variable.mark,
        // both rows share the period, so only the bottom one dates it
        xLabels: cell.variable.id === "temperature",
      },
    );
  }
}
