import { create, clear, createLoading } from "./utils/elements.js";
import { connect } from "./utils/ws.js";
import { round, colours, formatNumber, setEqual } from "./utils/misc.js";

/*********/
/* model */
/*********/

export function initModel() {
  return {
    loading: false,
    ws: null,
    running: false,
    availableConfig: null,
    calibration:
      window.localStorage.getItem("holmes--projection--calibration") === null
        ? null
        : JSON.parse(
            window.localStorage.getItem("holmes--projection--calibration"),
          ),
    config: {
      model: window.localStorage.getItem("holmes--projection--model"),
      scenario: window.localStorage.getItem("holmes--projection--scenario"),
      horizon: window.localStorage.getItem("holmes--projection--horizon"),
    },
    projection: null,
  };
}

export const initialMsg = {
  type: "ProjectionMsg",
  data: { type: "Connect" },
};

function verifyCalibration(calibration) {
  const keys = [
    "hydroModel",
    "catchment",
    "objective",
    "transformation",
    "algorithm",
    "algorithmParams",
    "start",
    "end",
    "snowModel",
    "hydroParams",
  ];
  if (!setEqual(new Set(Object.keys(calibration)), new Set(keys))) {
    return [false, "This isn't a valid calibrated parameter file."];
  } else {
    return [true, ""];
  }
}

/**********/
/* update */
/**********/

export async function update(model, msg, dispatch, createNotification) {
  dispatch = createDispatch(dispatch);
  let calibration;
  switch (msg.type) {
    case "Connect":
      connect("projection/", handleMessage, dispatch, createNotification);
      return { ...model, loading: true };
    case "Connected":
      if (model.availableConfig === null) {
        dispatch({ type: "GetAvailableConfig" });
      }
      return { ...model, loading: false, ws: msg.data };
    case "Disconnected":
      setTimeout(() => dispatch({ type: "Connect" }), 3000);
      return { ...model, ws: null };
    case "GetAvailableConfig":
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        model.calibration !== null
      ) {
        model.ws.send(
          JSON.stringify({
            type: "config",
            data: model.calibration.catchment,
          }),
        );
      }
      return { ...model, loading: true };
    case "GotAvailableConfig":
      dispatch({ type: "UpdateConfigFields" });
      return { ...model, availableConfig: msg.data, loading: false };
    case "Import":
      [...msg.data.target.files].forEach((file) => {
        const reader = new FileReader();
        reader.onload = (event) =>
          dispatch({ type: "ImportCalibration", data: event });
        reader.readAsText(file);
      });
      return model;
    case "ImportCalibration":
      calibration = JSON.parse(msg.data.target.result);
      const [valid, error] = verifyCalibration(calibration);
      if (valid) {
        window.localStorage.setItem(
          "holmes--projection--calibration",
          JSON.stringify(calibration),
        );
        dispatch({ type: "GetAvailableConfig" });
        return {
          ...model,
          calibration: calibration,
          availableConfig: null,
        };
      } else {
        createNotification(error, true);
        return model;
      }
    case "UpdateConfigFields":
      if (model.availableConfig !== null) {
        if (
          model.config.model === null ||
          model.availableConfig.every((c) => c.model !== model.config.model)
        ) {
          dispatch({
            type: "UpdateConfigField",
            data: { field: "model", value: model.availableConfig[0].model },
          });
        } else {
          dispatch({
            type: "UpdateConfigField",
            data: { field: "model", value: model.config.model },
          });
        }
      }
      return model;
    case "UpdateConfigField":
      model = {
        ...model,
        config: {
          ...model.config,
          [msg.data.field]: msg.data.value,
        },
        projection: null,
      };
      window.localStorage.setItem(
        `holmes--projection--${msg.data.field}`,
        msg.data.value,
      );
      if (model.availableConfig !== null) {
        if (msg.data.field === "model") {
          if (
            model.config.horizon === null ||
            model.availableConfig.every(
              (c) =>
                c.model !== model.config.model ||
                c.horizon !== model.config.horizon,
            )
          ) {
            dispatch({
              type: "UpdateConfigField",
              data: {
                field: "horizon",
                value: model.availableConfig.filter(
                  (c) => c.model === model.config.model,
                )[0].horizon,
              },
            });
          } else {
            dispatch({
              type: "UpdateConfigField",
              data: {
                field: "horizon",
                value: model.config.horizon,
              },
            });
          }
        } else if (msg.data.field === "horizon") {
          if (
            model.config.scenario === null ||
            model.availableConfig.every(
              (c) =>
                c.model !== model.config.model ||
                c.horizon !== model.config.horizon ||
                c.scenario !== model.config.scenario,
            )
          ) {
            dispatch({
              type: "UpdateConfigField",
              data: {
                field: "scenario",
                value: model.availableConfig.filter(
                  (c) =>
                    c.model === model.config.model &&
                    c.horizon === model.config.horizon,
                )[0].scenario,
              },
            });
          }
        }
      }
      return model;
    case "Run":
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        model.calibration !== null &&
        model.config.model !== null &&
        model.config.horizon !== null &&
        model.config.scenario !== null
      ) {
        model.ws.send(
          JSON.stringify({
            type: "projection",
            data: {
              calibration: model.calibration,
              config: model.config,
            },
          }),
        );
      }
      return { ...model, loading: true, running: true };
    case "GotProjection":
      console.log(msg.data);
      return {
        ...model,
        projection: msg.data,
        loading: false,
        running: false,
      };
    case "Export":
      downloadData(model);
      return model;
    default:
      return model;
  }
}

function createDispatch(dispatch) {
  return (msg) => dispatch({ type: "ProjectionMsg", data: msg });
}

function handleMessage(event, dispatch, createNotification) {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "error":
      createNotification(msg.data, true);
      break;
    case "config":
      dispatch({ type: "GotAvailableConfig", data: msg.data });
      break;
    case "projection":
      dispatch({ type: "GotProjection", data: msg.data });
      break;
    default:
      createNotification("Unknown websocket message", true);
      break;
  }
}

function downloadData(model) {
  if (model.calibration !== null && model.projection !== null) {
    const _data = model.projection.map((p) => ({
      ...p,
      model: model.config.model,
      horizon: model.config.horizon,
      scenario: model.config.scenario,
    }));
    const data = [
      Object.keys(_data[0]).join(","),
      ..._data.map((p) => Object.values(p).join(",")),
    ].join("\n");

    const blob = new Blob([data], {
      type: "text/csv",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${model.calibration.catchment.toLowerCase().replace(" ", "_")}_projection_data.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
}

/********/
/* view */
/********/

export function initView(dispatch) {
  dispatch = createDispatch(dispatch);
  const results = initResultsView(dispatch);
  let resizeTimeout;
  const resizeObserver = new ResizeObserver(() => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => dispatch({ type: "Noop" }), 100);
  });
  resizeObserver.observe(results);
  return create("section", { id: "projection" }, [
    create("h2", {}, ["Projection"]),
    initConfigView(dispatch),
    results,
  ]);
}

export function view(model, dispatch) {
  dispatch = createDispatch(dispatch);
  calibrationView(model);
  configView(model);
  projectionView(model);
}

function initConfigView(dispatch) {
  return create("div", { class: "config" }, [
    create("div", { id: "projection__calibration" }, [
      create("h3", {}, ["Calibration result"]),
      create("div", { class: "file-upload" }, [
        create("label", { for: "projection__upload" }, [
          "Import model parameters",
        ]),
        create(
          "input",
          {
            id: "projection__upload",
            type: "file",
            accept: "application/json",
          },
          [],
          [
            {
              event: "change",
              fct: (event) => dispatch({ type: "Import", data: event }),
            },
          ],
        ),
      ]),
      create("div", { id: "projection__calibrations-table", hidden: true }, [
        create("div", {}, [
          create("span", {}, ["hydrological model"]),
          create("span", {}, ["catchment"]),
          create("span", {}, ["objective"]),
          create("span", {}, ["transformation"]),
          create("span", {}, ["algorithm"]),
          create("span", {}, ["date start"]),
          create("span", {}, ["date end"]),
          create("span", {}, ["snow model"]),
          create("span", {}, ["parameters"]),
        ]),
      ]),
    ]),
    create(
      "form",
      { id: "projection__config" },
      [
        create("h3", {}, ["Projection settings"]),
        create("label", { for: "projection__model" }, ["Climate model"]),
        create(
          "select",
          { id: "projection__model" },
          [],
          [
            {
              event: "input",
              fct: (event) => {
                dispatch({
                  type: "UpdateConfigField",
                  data: { field: "model", value: event.target.value },
                });
              },
            },
          ],
        ),
        create("label", { for: "projection__horizon" }, ["Horizon"]),
        create(
          "select",
          { id: "projection__horizon" },
          [],
          [
            {
              event: "input",
              fct: (event) => {
                dispatch({
                  type: "UpdateConfigField",
                  data: { field: "horizon", value: event.target.value },
                });
              },
            },
          ],
        ),
        create("label", { for: "projection__scenario" }, ["Climate scenario"]),
        create(
          "select",
          { id: "projection__scenario" },
          [],
          [
            {
              event: "input",
              fct: (event) => {
                dispatch({
                  type: "UpdateConfigField",
                  data: { field: "scenario", value: event.target.value },
                });
              },
            },
          ],
        ),
        create(
          "input",
          {
            id: "projection__export",
            type: "button",
            value: "Export data",
            hidden: true,
          },
          [],
          [{ event: "click", fct: () => dispatch({ type: "Export" }) }],
        ),
        create("input", { type: "submit", value: "Run" }),
        createLoading(),
      ],
      [
        {
          event: "submit",
          fct: () => dispatch({ type: "Run" }),
        },
      ],
    ),
  ]);
}

function initResultsView(dispatch) {
  return create("div", { id: "projection__results" }, [
    create("svg", { id: "projection__results__projection", class: "plot" }),
  ]);
}

function calibrationView(model, dispatch) {
  const div = document.getElementById("projection__calibrations-table");
  [...div.querySelectorAll("div")]
    .slice(1)
    .forEach((d) => d.parentNode.removeChild(d));
  if (model.calibration !== null) {
    div.removeAttribute("hidden");
    div.appendChild(
      create("div", {}, [
        create("span", {}, [model.calibration.hydroModel]),
        create("span", {}, [model.calibration.catchment]),
        create("span", {}, [model.calibration.objective]),
        create("span", {}, [model.calibration.transformation]),
        create("span", {}, [model.calibration.algorithm]),
        create("span", {}, [model.calibration.start]),
        create("span", {}, [model.calibration.end]),
        create("span", {}, [model.calibration.snowModel ?? "none"]),
        create(
          "div",
          {},
          Object.entries(model.calibration.hydroParams)
            .map(([name, value]) => [name, round(value, 2)])
            .flat()
            .map((x) => create("span", {}, [x])),
        ),
      ]),
    );
  } else {
    div.setAttribute("hidden", true);
  }
}

function configView(model, dispatch) {
  const config = document.getElementById("projection__config");
  if (
    model.calibration === null ||
    model.config.model === null ||
    model.config.horizon === null ||
    model.config.scnario === null
  ) {
    config.setAttribute("hidden", true);
  } else {
    config.removeAttribute("hidden");
  }

  const model_ = document.getElementById("projection__model");
  const horizon = document.getElementById("projection__horizon");
  const scenario = document.getElementById("projection__scenario");

  clear(model_);
  clear(horizon);
  clear(scenario);

  if (model.availableConfig !== null) {
    const models = [...new Set(model.availableConfig.map((c) => c.model))];
    models.forEach((m) => {
      model_.appendChild(create("option", { value: m }, [m]));
    });
    if (model.config.model !== null) {
      model_.value = model.config.model;
    }
  }
  if (model.availableConfig !== null && model.config.model !== null) {
    const horizons = [
      ...new Set(
        model.availableConfig
          .filter((c) => c.model === model.config.model)
          .map((c) => c.horizon),
      ),
    ];
    horizons.forEach((h) => {
      horizon.appendChild(create("option", { value: h }, [h]));
    });
    if (model.config.horizon !== null) {
      horizon.value = model.config.horizon;
    }
  }
  if (
    model.availableConfig !== null &&
    model.config.model !== null &&
    model.config.horizon !== null
  ) {
    const scenarios = [
      ...new Set(
        model.availableConfig
          .filter(
            (c) =>
              c.model === model.config.model &&
              c.horizon === model.config.horizon,
          )
          .map((c) => c.scenario),
      ),
    ];
    scenarios.forEach((s) => {
      scenario.appendChild(create("option", { value: s }, [s]));
    });
    if (model.config.scenario !== null) {
      scenario.value = model.config.scenario;
    }
  }

  if (model.running) {
    config.querySelector(".loading").removeAttribute("hidden");
    config.querySelector("input[type='submit']").setAttribute("hidden", true);
  } else {
    config.querySelector(".loading").setAttribute("hidden", true);
    config.querySelector("input[type='submit']").removeAttribute("hidden");
  }

  if (model.projection === null) {
    document.getElementById("projection__export").setAttribute("hidden", true);
  } else {
    document.getElementById("projection__export").removeAttribute("hidden");
  }
}

function projectionView(model) {
  const _svg = document.getElementById("projection__results__projection");
  clear(_svg);
  if (model.projection !== null) {
    const width = _svg.clientWidth;
    const height = _svg.clientHeight;
    _svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const boundaries = {
      l: 50,
      r: width - 25,
      t: 5,
      b: height - 20,
    };

    const svg = d3.select(_svg);

    const projection = model.projection;
    const fields = Object.keys(model.projection[0]).filter((f) =>
      f.startsWith("member"),
    );
    const yMin = d3.min(projection, (d) =>
      Math.min(d.median, ...fields.map((f) => d[f])),
    );
    const yMax = d3.max(projection, (d) =>
      Math.max(d.median, ...fields.map((f) => d[f])),
    );

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(projection, (d) => new Date(d.date)))
      .range([boundaries.l, boundaries.r]);
    const yScale = d3
      .scaleLinear()
      .domain([yMin, yMax])
      .range([boundaries.b, boundaries.t]);

    // grid
    svg
      .append("g")
      .attr("class", "grid-vertical")
      .selectAll("line")
      .data(xScale.ticks(12))
      .join("line")
      .attr("x1", (d) => xScale(d))
      .attr("x2", (d) => xScale(d))
      .attr("y1", yScale.range()[0])
      .attr("y2", yScale.range()[1]);
    svg
      .append("g")
      .attr("class", "grid-horizontal")
      .selectAll("line")
      .data(yScale.ticks(5))
      .join("line")
      .attr("y1", (d) => yScale(d))
      .attr("y2", (d) => yScale(d))
      .attr("x1", xScale.range()[0])
      .attr("x2", xScale.range()[1]);

    // x axis
    svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${boundaries.b})`)
      .call(
        d3
          .axisBottom(xScale)
          .ticks(12)
          .tickSize(0)
          .tickFormat(d3.timeFormat("%B")),
      )
      .call((g) => g.select(".domain").remove());
    // y axis
    svg
      .append("g")
      .attr("class", "y-axis")
      .attr("transform", `translate(${boundaries.l}, 0)`)
      .call(
        d3
          .axisLeft(yScale)
          .ticks(5)
          .tickSize(0)
          .tickFormat((x) => formatNumber(x)),
      )
      .call((g) => g.select(".domain").remove());
    svg
      .append("text")
      .attr("x", 15)
      .attr("y", (boundaries.t + boundaries.b) / 2)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr(
        "transform",
        `rotate(-90, 15, ${(boundaries.t + boundaries.b) / 2})`,
      )
      .attr("font-size", "0.9rem")
      .text("Streamflow");

    // projections
    fields.forEach((f) => {
      svg
        .append("path")
        .attr("class", colours[2])
        .datum(projection)
        .attr(
          "d",
          d3
            .line()
            .x((d) => xScale(new Date(d.date)))
            .y((d) => yScale(d[f])),
        );
    });

    // median
    svg
      .append("path")
      .attr("class", `${colours[2]} projection__results__projection__median`)
      .datum(projection)
      .attr(
        "d",
        d3
          .line()
          .x((d) => xScale(new Date(d.date)))
          .y((d) => yScale(d.median)),
      );

    // legend
    const legendData = [
      {
        label: "Median",
        class: `${colours[2]} projection__results__projection__median`,
      },
      { label: "Members", class: colours[2] },
    ];
    const legend = svg
      .append("g")
      .attr("class", "legend")
      .attr("transform", `translate(${boundaries.r - 5}, ${boundaries.t + 5})`);
    const legendItems = legend
      .selectAll(".legend-item")
      .data(legendData)
      .join("g")
      .attr("class", "legend-item")
      .attr("transform", (_, i) => `translate(0, ${i * 20})`);
    legendItems
      .append("line")
      .attr("class", (d) => d.class)
      .attr("x1", -100)
      .attr("x2", -70)
      .attr("y1", 7)
      .attr("y2", 7);
    legendItems
      .append("text")
      .attr("x", 0)
      .attr("y", 12)
      .attr("text-anchor", "end")
      .attr("font-size", "0.9rem")
      .text((d) => d.label);
  }
}
