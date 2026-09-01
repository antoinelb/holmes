import { clear, create, createLoading } from "../utils/elements.js";
import { downloadBlob, toCsv } from "../utils/export.js";
import { formatNumber } from "../utils/misc.js";
import { hydrographView } from "../utils/plot.js";
import { t } from "../utils/text.js";

// role and edge ids double as config keys, so their labels are looked up
// rather than derived from the ids
const roleLabels = {
  calibration: t("Calibration", "Calage"),
  simulation: t("Simulation", "Simulation"),
};
const stationLabels = {
  calibration: t("Calibration station", "Station de calage"),
  simulation: t("Simulation station", "Station de simulation"),
};
const edgeLabels = {
  start: t("Start", "Début"),
  end: t("End", "Fin"),
};
const edgeResetTitles = {
  start: t("Set to possible start", "Ramener au début possible"),
  end: t("Set to possible end", "Ramener à la fin possible"),
};

/**********/
/* update */
/**********/

export function update(model, msg, dispatch) {
  switch (msg.type) {
    case "stations/GetStations":
      if (model.ws?.readyState === WebSocket.OPEN) {
        model.ws.send(JSON.stringify({ type: "stations" }));
      }
      return { ...model, loading: true };
    case "stations/GotStations":
      // restore hydrographs for persisted selections; re-fires on every
      // reconnect, retrying anything lost while disconnected
      for (const role of ["calibration", "simulation"]) {
        const id = model.config[`${role}Station`];
        if (id) {
          dispatch({ type: "stations/GetStreamflow", data: id });
        }
      }
      return { ...model, loading: false, stations: msg.data };
    case "stations/GetStreamflow":
      if (
        msg.data in model.streamflow ||
        model.ws?.readyState !== WebSocket.OPEN
      ) {
        return model;
      }
      model.ws.send(JSON.stringify({ type: "streamflow", station: msg.data }));
      // null marks the request pending so re-triggers dedupe
      return {
        ...model,
        streamflow: { ...model.streamflow, [msg.data]: null },
      };
    case "stations/GotStreamflow":
      return {
        ...model,
        streamflow: {
          ...model.streamflow,
          // convert epoch seconds to Date once on arrival
          [msg.data.station]: msg.data.data.map((d) => ({
            date: new Date(d.datetime * 1000),
            streamflow: d.streamflow,
          })),
        },
      };
    case "stations/CreateMap":
      if (model.map === null) {
        createMap(dispatch);
      }
      return { ...model, loading: true };
    case "stations/CreatedMap":
      return { ...model, loading: false, map: msg.data };
    case "stations/SelectStation":
      selectStation(model, msg.data.role, msg.data.id, dispatch);
      return model;
    case "stations/ResetDate":
      resetDate(model, msg.data.role, msg.data.edge, dispatch);
      return model;
    case "stations/OpenDialog":
      return { ...model, activeDialogStation: msg.data };
    case "stations/CloseDialog":
      return { ...model, activeDialogStation: null };
    case "stations/ToggleVisibility":
      return {
        ...model,
        visibility: {
          ...model.visibility,
          [msg.data]: !model.visibility[msg.data],
        },
      };
    case "stations/Export":
      exportStreamflow(model);
      return model;
    default:
      return model;
  }
}

function createMap(dispatch) {
  const mapDiv = document.getElementById("map");
  const map = L.map(mapDiv);
  const resizeObserver = new ResizeObserver(() =>
    setTimeout(() => map.invalidateSize(), 300),
  );
  resizeObserver.observe(mapDiv);
  dispatch({ type: "stations/CreatedMap", data: map });
}

// selecting a station snaps the period to its record before the station is
// set, so autoComplete never snapshots an invalid state
function selectStation(model, role, id, dispatch) {
  const station = model.stations?.find((s) => s.id === id);
  if (station) {
    dispatch({
      type: "SetConfig",
      data: {
        key: `${role}Period`,
        value: clampPeriod(
          model.config[`${role}Period`],
          periodBounds(role, station),
        ),
      },
    });
  }
  dispatch({ type: "SetConfig", data: { key: `${role}Station`, value: id } });
  if (id) {
    dispatch({ type: "stations/GetStreamflow", data: id });
    // the weather product is per watershed, so a new station invalidates it;
    // fetching here rather than waiting for the weather step's fetch-on-view
    // means the load overlaps the rest of the pipeline. the serial queue runs
    // the SetConfigs first, and GetWeather no-ops before a method is chosen
    dispatch({ type: "weather/GetWeather" });
  }
}

// an empty period pre-fills to the full record, an out-of-bounds edge clamps
// to it, and a period entirely outside the record resets to the full record
function clampPeriod(period, bounds) {
  if (!bounds.min) {
    return period;
  }
  if (period === null) {
    return { start: bounds.min, end: bounds.max };
  }
  const start = period.start < bounds.min ? bounds.min : period.start;
  const end = period.end > bounds.max ? bounds.max : period.end;
  return start <= end ? { start, end } : { start: bounds.min, end: bounds.max };
}

function resetDate(model, role, edge, dispatch) {
  const station = model.stations?.find(
    (s) => s.id === model.config[`${role}Station`],
  );
  if (!station) {
    return;
  }
  const bounds = stationBounds(station);
  const input = document.getElementById(`controls__${role}-${edge}`);
  input.value = edge === "start" ? bounds.min : bounds.max;
  setPeriod(role, dispatch);
}

// simulation may reconstruct periods outside the observed record (the reset
// buttons still snap to it via stationBounds); weather, which every method
// provides from 1940, is the only real forcing limit there
const weatherStart = "1940-01-01";
function periodBounds(role, station) {
  return role === "simulation"
    ? { min: weatherStart, max: today() }
    : stationBounds(station);
}

// station start/end are years (metadata granularity); an open station's
// record runs to the present
function stationBounds(station) {
  return {
    min: station.start ? `${station.start}-01-01` : "",
    max: station.end ? `${station.end}-12-31` : today(),
  };
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

// the whole loaded record, not the selected period, and one file per role
// since both roles may point at the same station
function exportStreamflow(model) {
  for (const { role, id, series } of exportableSeries(model)) {
    downloadBlob(
      `streamflow_${role}_${id}.csv`,
      "text/csv",
      toCsv(
        ["datetime", "streamflow"],
        series.map((d) => [d.date, d.streamflow]),
      ),
    );
  }
}

// a selected station whose streamflow is still pending holds null, not an
// array, so it has nothing to write yet
function exportableSeries(model) {
  return ["calibration", "simulation"]
    .map((role) => ({
      role: role,
      id: model.config[`${role}Station`],
      series: model.streamflow[model.config[`${role}Station`]],
    }))
    .filter((entry) => Array.isArray(entry.series));
}

/********/
/* view */
/********/

export function controlsView(model, dispatch) {
  const controls = document.getElementById("controls");
  // structure is built once per step entry, then reconciled in place:
  // rebuilding under a click swallows it
  if (controls.dataset.step !== "stations") {
    controls.dataset.step = "stations";
    clear(controls);
    controls.append(
      create("h2", {}, "Stations"),
      roleFields("calibration", dispatch),
      roleFields("simulation", dispatch),
      create("div", { id: "stations__actions", class: "stations__actions" }, [
        create(
          "button",
          { id: "stations__export", type: "button" },
          t("Export", "Exporter"),
          [
            {
              event: "click",
              fct: () => dispatch({ type: "stations/Export" }),
            },
          ],
        ),
      ]),
    );
  }
  syncControls(model);
}

function roleFields(role, dispatch) {
  return create("section", { class: "controls__role" }, [
    create("label", { class: "controls__field" }, [
      create("span", {}, stationLabels[role]),
      create(
        "select",
        { id: `controls__${role}-station` },
        [create("option", { value: "" }, "—")],
        [
          {
            event: "change",
            fct: (event) =>
              dispatch({
                type: "stations/SelectStation",
                data: { role: role, id: event.target.value || null },
              }),
          },
        ],
      ),
    ]),
    create("div", { class: "controls__period" }, [
      dateField(role, "start", dispatch),
      dateField(role, "end", dispatch),
    ]),
  ]);
}

function dateField(role, edge, dispatch) {
  return create("label", { class: "controls__field" }, [
    create("div", { class: "controls__field-header" }, [
      create("span", {}, edgeLabels[edge]),
      create(
        "button",
        {
          type: "button",
          class: "controls__reset",
          id: `controls__${role}-${edge}-reset`,
          title: edgeResetTitles[edge],
        },
        t("Reset", "Réinitialiser"),
        [
          {
            event: "click",
            fct: (event) => {
              // inside a wrapping label the click would forward to the input
              event.preventDefault();
              dispatch({
                type: "stations/ResetDate",
                data: { role: role, edge: edge },
              });
            },
          },
        ],
      ),
    ]),
    create(
      "input",
      { type: "date", id: `controls__${role}-${edge}` },
      [],
      [{ event: "change", fct: () => setPeriod(role, dispatch) }],
    ),
  ]);
}

// the period is only valid as a whole: both dates set and ordered
function setPeriod(role, dispatch) {
  const start = document.getElementById(`controls__${role}-start`).value;
  const end = document.getElementById(`controls__${role}-end`).value;
  dispatch({
    type: "SetConfig",
    data: {
      key: `${role}Period`,
      value: start && end && start <= end ? { start, end } : null,
    },
  });
  // mirrors selectStation: with a weather method already chosen, the weather
  // step re-completes itself instead of staying stale until a method click
  dispatch({ type: "weather/GetWeather" });
}

function syncControls(model) {
  for (const role of ["calibration", "simulation"]) {
    const select = document.getElementById(`controls__${role}-station`);
    const start = document.getElementById(`controls__${role}-start`);
    const end = document.getElementById(`controls__${role}-end`);

    if (model.stations && select.options.length === 1) {
      model.stations.forEach((s) =>
        select.appendChild(
          create("option", { value: s.id }, `${s.name} (${s.id})`),
        ),
      );
    }

    const stationId = model.config[`${role}Station`];
    select.value = stationId ?? "";

    const station = model.stations?.find((s) => s.id === stationId);
    const bounds = station
      ? periodBounds(role, station)
      : { min: "", max: today() };

    const period = model.config[`${role}Period`];
    if (period !== null) {
      start.value = period.start;
      end.value = period.end;
    } else if (start.value && end.value) {
      // both filled but the config is null: the period was cleared or invalid
      start.value = "";
      end.value = "";
    }

    start.disabled = end.disabled = stationId === null;
    for (const edge of ["start", "end"]) {
      document.getElementById(`controls__${role}-${edge}-reset`).disabled =
        stationId === null;
    }
    start.min = bounds.min;
    start.max = end.value || bounds.max;
    end.min = start.value || bounds.min;
    end.max = bounds.max;
  }

  // nothing to export before a station is picked, and nothing to write while
  // one of the picked stations is still loading
  const selected = ["calibration", "simulation"].filter(
    (role) => model.config[`${role}Station`],
  );
  document.getElementById("stations__actions").hidden = selected.length === 0;
  document.getElementById("stations__export").disabled =
    exportableSeries(model).length !== selected.length;
}

export function canvasView(model, dispatch) {
  const canvas = document.getElementById("canvas");
  if (canvas.dataset.step !== "stations") {
    canvas.dataset.step = "stations";
    clear(canvas);
    // inside #canvas so other steps' clearing removes the panel for free
    canvas.append(
      create("div", { id: "hydrographs", hidden: "" }, [
        hydrographFigure("calibration"),
        hydrographFigure("simulation"),
      ]),
    );
    observePanelResize(dispatch);
  }

  sharedMapView(model, dispatch);
  hydrographsView(model);
}

function hydrographFigure(role) {
  return create("figure", { id: `hydrographs__${role}` }, [
    create("figcaption", {}),
    create("div", { class: "hydrographs__loading" }, [createLoading()]),
    create("svg", { class: "plot", id: `hydrographs__${role}-svg` }),
  ]);
}

// charts must re-read their box on resize, so a debounced no-op message
// re-runs the view and the size signature forces the redraw
function observePanelResize(dispatch) {
  let timeout;
  const observer = new ResizeObserver(() => {
    clearTimeout(timeout);
    timeout = setTimeout(() => dispatch({ type: "stations/Rerender" }), 100);
  });
  observer.observe(document.getElementById("hydrographs"));
}

function hydrographsView(model) {
  const roles = ["calibration", "simulation"];
  const series = Object.fromEntries(
    roles.map((role) => [role, roleSeries(model, role)]),
  );
  // visibility first: chart boxes must be final before anything is drawn
  document.getElementById("hydrographs").hidden = roles.every(
    (role) => series[role] === null,
  );
  for (const role of roles) {
    const figure = document.getElementById(`hydrographs__${role}`);
    // an empty role leaves the row so the other chart spans the full width
    figure.classList.toggle(
      "hydrographs__figure--absent",
      series[role] === null,
    );
    figure.classList.toggle(
      "hydrographs__figure--loading",
      series[role] === "loading",
    );
    if (series[role] !== null) {
      captionView(model, role);
    }
  }
  // the leftmost chart on show carries the shared axis title
  const titleRole = roles.find((role) => series[role] !== null);
  for (const role of roles) {
    if (series[role] !== null && series[role] !== "loading") {
      roleHydrographView(model, role, series[role], role === titleRole);
    }
  }
}

// null when the role has no station or its period holds no observations,
// "loading" while the station's data hasn't arrived yet
function roleSeries(model, role) {
  const id = model.config[`${role}Station`];
  const period = model.config[`${role}Period`];
  if (!id || !period) {
    return null;
  }
  const data = model.streamflow[id];
  if (!data) {
    return "loading";
  }
  const start = new Date(period.start);
  const end = new Date(period.end);
  const filtered = data.filter((d) => d.date >= start && d.date <= end);
  return filtered.some((d) => d.streamflow !== null) ? filtered : null;
}

function captionView(model, role) {
  const id = model.config[`${role}Station`];
  const station = model.stations?.find((s) => s.id === id);
  const label = roleLabels[role];
  document
    .getElementById(`hydrographs__${role}`)
    .querySelector("figcaption").textContent = station
    ? `${label} — ${station.name} (${id})`
    : label;
}

function roleHydrographView(model, role, series, showTitle) {
  const id = model.config[`${role}Station`];
  const period = model.config[`${role}Period`];
  const svg = document.getElementById(`hydrographs__${role}-svg`);
  // redrawing on every dispatch would wipe the brush zoom, so redraw only
  // when the plotted window, the box or the title changes
  const signature =
    `${id}|${period.start}|${period.end}|${showTitle}` +
    `|${svg.clientWidth}x${svg.clientHeight}`;
  if (svg.dataset.signature !== signature) {
    svg.dataset.signature = signature;
    hydrographView(
      svg,
      series,
      role === "calibration" ? "purple" : "green",
      showTitle ? {} : { label: null },
    );
  }
}

// the persistent map is shared with other map: true steps (weather), which
// call this so the map bootstraps even when a reload lands on their step;
// selectedOnly restricts markers and legend to the chosen stations, and
// showGrid draws the weather source cells
export function sharedMapView(
  model,
  dispatch,
  { selectedOnly = false, showGrid = false } = {},
) {
  const mapDiv = document.getElementById("map");
  if (model.map === null) {
    if (!mapDiv.dataset.requested) {
      mapDiv.dataset.requested = "true";
      dispatch({ type: "stations/CreateMap" });
    }
    return;
  }

  initMapView(model.map);
  legendView(
    dispatch,
    selectedOnly,
    showGrid && model.config.weatherMethod === "nearest_stations",
  );
  weatherGridView(model, showGrid);
  if (model.stations) {
    const stations = selectedOnly
      ? model.stations.filter((s) =>
          [
            model.config.calibrationStation,
            model.config.simulationStation,
          ].includes(s.id),
        )
      : model.stations;
    mapView(model, stations, dispatch, selectedOnly);
  }

  mapDiv.classList.toggle("map__open-hidden", !model.visibility.open);
  mapDiv.classList.toggle("map__closed-hidden", !model.visibility.closed);
}

// the weather source layer: era5/ministry cells as grey outlines,
// nearest_stations as fg dots linked to the hydro stations they feed
function weatherGridView(model, showGrid) {
  const map = model.map;
  const grid = showGrid ? (model.weather?.grid ?? null) : null;
  // rebuilding the layer on every dispatch would flicker the outlines; the
  // weather key already carries the method and station count, the stations
  // flag covers the link anchors arriving after the grid
  const signature = grid
    ? `${model.weather.key}|${grid.length}|${model.stations ? 1 : 0}`
    : "none";
  if (map._weatherGridSignature === signature) {
    return;
  }
  map._weatherGridSignature = signature;

  if (map._weatherGrid) {
    map.removeLayer(map._weatherGrid);
    map._weatherGrid = null;
  }
  // a rebuild mid-hover never gets the mouseout, so the highlight would
  // stick to the next layer
  setLinkHover("calibration", false);
  setLinkHover("simulation", false);
  if (!grid || grid.length === 0) {
    return;
  }

  const layers =
    model.config.weatherMethod === "nearest_stations"
      ? weatherStationLayers(grid)
      : weatherCellLayers(grid);
  if (layers.length === 0) {
    return;
  }
  map._weatherGrid = L.layerGroup([
    ...layers,
    ...weatherCentroidLayers(model, grid),
  ]).addTo(map);
}

// one dot per station, with a native tooltip naming it like the hydro
// markers' title; neighbouring watersheds share stations, so each is drawn
// once
function weatherStationLayers(grid) {
  const seen = new Set();
  const layers = [];
  for (const row of grid) {
    if (seen.has(row.climate_id)) {
      continue;
    }
    seen.add(row.climate_id);
    // the class restyles the dots as fg in css so they track the theme like
    // the hydro station markers
    const marker = L.circleMarker([row.latitude, row.longitude], {
      radius: 5,
      className: "map__weather-station",
    });
    // svg ignores the title *attribute*: the native tooltip needs a <title>
    // child, which can only be appended once the path element exists
    marker.on("add", () => {
      const title = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "title",
      );
      title.textContent = `${row.name} (${row.climate_id})`;
      marker.getElement().append(title);
    });
    layers.push(marker);
  }
  return layers;
}

// era5/ministry cells as grey outlines; neighbouring watersheds share cells,
// so the same shape would otherwise be drawn several times over
function weatherCellLayers(grid) {
  const seen = new Set();
  const shapes = [];
  for (const cell of grid) {
    const key = `${cell.latitude}|${cell.longitude}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    try {
      shapes.push(JSON.parse(cell.geometry));
    } catch (e) {
      console.error(`Failed to parse weather grid cell ${key}:`, e);
    }
  }
  if (shapes.length === 0) {
    return [];
  }
  return [
    L.geoJSON(shapes, {
      style: { color: "grey", weight: 1, dashArray: "4 3", fill: false },
      interactive: false,
    }),
  ];
}

// each watershed's centroid — the point the nearest-stations selection
// measures distances to, not the gauge, which can sit tens of km downstream —
// plus one line from it to each weather station actually feeding the mean:
// the grid carries the whole nearby pool, the config says how many count, and
// sorting by weight (1/d2) recovers the backend's selection order
function weatherCentroidLayers(model, grid) {
  if (model.config.weatherMethod !== "nearest_stations" || !model.stations) {
    return [];
  }
  const byWatershed = {};
  for (const row of grid) {
    (byWatershed[row.id] ??= []).push(row);
  }
  const layers = [];
  for (const [id, rows] of Object.entries(byWatershed)) {
    const station = model.stations.find((s) => s.id === id);
    if (!station || station.centroid_lat == null) {
      continue;
    }
    const centroid = [station.centroid_lat, station.centroid_lon];
    const role =
      id === model.config.calibrationStation ? "calibration" : "simulation";
    // interactive so hovering the centroid highlights its links, like
    // hovering the hydro marker does
    const marker = L.circleMarker(centroid, {
      radius: 6,
      className: `map__centroid map__centroid--${role}`,
    });
    marker.on("mouseover", () => setLinkHover(role, true));
    marker.on("mouseout", () => setLinkHover(role, false));
    layers.push(marker);
    for (const row of rows
      .toSorted((a, b) => b.weight - a.weight)
      .slice(0, model.config.weatherNStations)) {
      layers.push(
        L.polyline([centroid, [row.latitude, row.longitude]], {
          className: `map__weather-link map__weather-link--${role}`,
          weight: 1,
          interactive: false,
        }),
      );
    }
  }
  return layers;
}

// imperative like the rest of the map: the highlight is transient hover
// state, so it lives in a container class the css rules key on rather than
// in the model
function setLinkHover(role, on) {
  if (role) {
    document
      .getElementById("map")
      .classList.toggle(`map__weather-hover-${role}`, on);
  }
}

// derived from the marker's classes at event time, because the enter
// handlers close over the model from when the marker was created while the
// update pass keeps the classes current
function hoverRole(element) {
  return element.classList.contains("map__marker--calibration")
    ? "calibration"
    : element.classList.contains("map__marker--simulation")
      ? "simulation"
      : null;
}

function initMapView(map) {
  if (Object.keys(map._layers).length == 0) {
    map.setView([48.25, -71.35], 9);
    // mirrors the pre-downloaded tile rectangle in download/tiles.py:
    // the tiles ship in the data archive, so panning past them would
    // only show blank tiles
    map.setMaxBounds([
      [46.558, -74.531],
      [48.922, -68.906],
    ]);
    L.tileLayer("/map/{z}/{x}/{y}.png", {
      minZoom: 9,
      maxZoom: 12,
    }).addTo(map);

    // topleft, recentred by CSS: the corners are taken by the wordmark,
    // settings button and controls card; content is filled by legendView
    const legend = L.control({ position: "topleft" });
    legend.onAdd = () => create("div", { id: "map__legend" });
    legend.addTo(map);
  }
}

// the legend adapts to the step: all stations (with visibility toggles) on
// the stations step, only the selected roles elsewhere, plus the weather
// station dot when the nearest-stations method draws one
function legendView(dispatch, selectedOnly, showWeatherStations = false) {
  const legend = document.getElementById("map__legend");
  const variant = selectedOnly
    ? showWeatherStations
      ? "selected-weather"
      : "selected"
    : "all";
  if (legend.dataset.variant === variant) {
    return;
  }
  legend.dataset.variant = variant;
  clear(legend);
  if (selectedOnly) {
    legend.append(
      legendItem(stationLabels.calibration, "calibration"),
      legendItem(stationLabels.simulation, "simulation"),
      ...(showWeatherStations
        ? [
            legendItem(
              t("Calibration centroid", "Centroïde de calage"),
              "calibration-centroid",
            ),
            legendItem(
              t("Simulation centroid", "Centroïde de simulation"),
              "simulation-centroid",
            ),
            legendItem(t("Weather station", "Station météo"), "weather"),
          ]
        : []),
    );
  } else {
    legend.append(
      legendItem(t("Open station", "Station ouverte"), "open", dispatch),
      legendItem(t("Closed station", "Station fermée"), "closed", dispatch),
    );
  }
}

// without a dispatch the item is a static swatch instead of a toggle
function legendItem(label, key, dispatch) {
  return create(
    "div",
    {
      id: `map__legend-${key}`,
      class: dispatch
        ? "map__legend-item"
        : "map__legend-item map__legend-item--static",
    },
    [
      create("div", { class: `map__legend-color map__legend-color--${key}` }),
      create("span", {}, [label]),
    ],
    dispatch
      ? [
          {
            event: "click",
            fct: () =>
              dispatch({ type: "stations/ToggleVisibility", data: key }),
          },
        ]
      : [],
  );
}

function mapView(model, stations, dispatch, selectedOnly) {
  if (model.map._dialogWatershedId !== model.activeDialogStation) {
    if (model.map._dialogWatershed) {
      model.map.removeLayer(model.map._dialogWatershed);
      model.map._dialogWatershed = null;
    }
    model.map._dialogWatershedId = model.activeDialogStation;
    if (model.activeDialogStation) {
      const activeStation = model.stations.find(
        (s) => s.id === model.activeDialogStation,
      );
      if (activeStation && activeStation.geometry) {
        try {
          const geom = JSON.parse(activeStation.geometry);
          model.map._dialogWatershed = L.geoJSON(geom, {
            style: {
              color: "grey",
              weight: 1,
              fillColor: "grey",
              fillOpacity: 0.2,
            },
            interactive: false,
          }).addTo(model.map);
        } catch (e) {
          console.error(
            `Failed to parse watershed for station ${activeStation.id}:`,
            e,
          );
        }
      }
    }
  }

  const updateLocation = (selection) => {
    const zoom = model.map.getZoom();
    const getSize = () => `${5 + (zoom - 6) * 2}px`;

    return selection
      .style(
        "transform",
        (d) =>
          `translate(${model.map.latLngToLayerPoint([d.lat, d.lon]).x}px, ${model.map.latLngToLayerPoint([d.lat, d.lon]).y}px)`,
      )
      .style("width", getSize)
      .style("height", getSize);
  };

  const getClass = (d) =>
    d.id === model.config.calibrationStation
      ? "map__marker map__marker--calibration"
      : d.id === model.config.simulationStation
        ? "map__marker map__marker--simulation"
        : d.end !== null
          ? "map__marker map__marker--closed"
          : "map__marker";

  const createDialog = (d) =>
    create(
      "div",
      { id: "map__dialog" },
      [
        create("div", {}, [
          d.id === model.config.calibrationStation
            ? create(
                "span",
                { id: "map__dialog__calibration" },
                t("calibration", "calage"),
              )
            : "",
          create("strong", {}, d.name),
          d.id === model.config.simulationStation
            ? create("span", { id: "map__dialog__simulation" }, "simulation")
            : "",
        ]),
        create("p", {}, t(`Id: ${d.id}`, `Id : ${d.id}`)),
        create(
          "p",
          {},
          t(
            `Watershed area: ${formatNumber(d.area)} km²`,
            `Superficie du bassin : ${formatNumber(d.area)} km²`,
          ),
        ),
        create("p", {}, t(`Start: ${d.start}`, `Début : ${d.start}`)),
        ...(d.end === null
          ? []
          : [create("p", {}, t(`End: ${d.end}`, `Fin : ${d.end}`))]),
        // role selection only belongs to the stations step
        ...(selectedOnly
          ? []
          : [
              create(
                "button",
                { id: "map__dialog__calibration-btn" },
                t("Use as calibration", "Utiliser pour le calage"),
                [
                  {
                    event: "click",
                    fct: () =>
                      dispatch({
                        type: "stations/SelectStation",
                        data: { role: "calibration", id: d.id },
                      }),
                  },
                ],
              ),
              create(
                "button",
                { id: "map__dialog__simulation-btn" },
                t("Use as simulation", "Utiliser pour la simulation"),
                [
                  {
                    event: "click",
                    fct: () =>
                      dispatch({
                        type: "stations/SelectStation",
                        data: { role: "simulation", id: d.id },
                      }),
                  },
                ],
              ),
            ]),
      ],
      [{ event: "click", fct: (event) => event.stopPropagation() }],
    );

  const markers = d3
    .select(model.map.getPanes().markerPane)
    .selectAll(".map__marker")
    .data(stations, (d) => d.id)
    .join(
      (enter) =>
        enter
          .append("div")
          .attr("class", getClass)
          .attr("title", (d) => d.name)
          .on("click", (event, d) => {
            event.stopPropagation();
            dispatch({ type: "stations/OpenDialog", data: d.id });
          })
          .on("mouseenter", (event, d) => {
            setLinkHover(hoverRole(event.currentTarget), true);
            if (d.geometry && d.id !== model.activeDialogStation) {
              try {
                const geom = JSON.parse(d.geometry);
                model.map._hoverWatershed = L.geoJSON(geom, {
                  style: {
                    color: "grey",
                    weight: 1,
                    fillColor: "grey",
                    fillOpacity: 0.2,
                  },
                  interactive: false,
                }).addTo(model.map);
              } catch (e) {
                console.error(
                  `Failed to parse watershed for station ${d.id}:`,
                  e,
                );
              }
            }
          })
          .on("mouseleave", (event) => {
            setLinkHover(hoverRole(event.currentTarget), false);
            if (model.map._hoverWatershed) {
              model.map.removeLayer(model.map._hoverWatershed);
              model.map._hoverWatershed = null;
            }
          })
          .call(updateLocation),
      (update) => update.attr("class", getClass).call(updateLocation),
    );

  markers.select("#map__dialog").remove();
  const activeMarker = markers.filter(
    (d) => d.id === model.activeDialogStation,
  );
  activeMarker
    .attr("class", (d) => getClass(d) + " map__marker--active")
    .append(createDialog);

  if (!model.map._moveListener) {
    model.map.on("move", () => updateLocation(d3.selectAll(".map__marker")));
    model.map.on("click", () => dispatch({ type: "stations/CloseDialog" }));
    model.map._moveListener = true;
  }
}
