import { create, clear, createIcon, createCheckbox } from "./utils/elements.js";
import {
  connect,
  incrementReconnectAttempt,
  isCircuitBreakerOpen,
} from "./utils/ws.js";
import { formatNumber, colours, round, setEqual } from "./utils/misc.js";

const WS_URL = "simulation/";

/*********/
/* model */
/*********/

function parseLocalStorageCalibration() {
  const stored = window.localStorage.getItem("holmes--simulation--calibration");
  if (stored === null) return [];
  try {
    return JSON.parse(stored) ?? [];
  } catch (e) {
    console.error("Failed to parse localStorage calibrations:", e);
    return [];
  }
}

export function initModel() {
  return {
    loading: false,
    ws: null,
    availableConfig: null,
    calibration: parseLocalStorageCalibration(),
    config: {
      start: window.localStorage.getItem("holmes--simulation--start"),
      end: window.localStorage.getItem("holmes--simulation--end"),
      multimodel:
        window.localStorage.getItem("holmes--simulation--multimodel") ===
        "true",
    },
    observations: null,
    simulation: null,
    results: null,
  };
}

export const initialMsg = {
  type: "SimulationMsg",
  data: { type: "Connect" },
};

function verifyCalibration(model, calibration) {
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
  } else if (model.calibration.length === 0) {
    return [true, ""];
  } else {
    if (model.calibration[0].catchment != calibration.catchment) {
      return [false, "The calibrations need to be on the same catchment."];
    } else {
      return [
        model.calibration.every((c) =>
          Object.entries(c).some(([field, value]) =>
            field === "id"
              ? false
              : field !== "hydroParams"
                ? value !== calibration[field]
                : Object.values(value).some(
                    (p, i) => p !== Object.values(calibration.hydroParams)[i],
                  ),
          ),
        ),
        "This calibration is already imported.",
      ];
    }
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
      connect(WS_URL, handleMessage, dispatch, createNotification);
      return { ...model, loading: true };
    case "Connected":
      if (model.availableConfig === null) {
        dispatch({ type: "GetAvailableConfig" });
      }
      return { ...model, loading: false, ws: msg.data };
    case "Disconnected":
      if (isCircuitBreakerOpen(WS_URL)) {
        createNotification(
          "Connection lost. Please refresh the page to reconnect.",
          true,
        );
        return { ...model, ws: null };
      }
      const simulationReconnectState = incrementReconnectAttempt(WS_URL);
      setTimeout(
        () => dispatch({ type: "Connect" }),
        simulationReconnectState.delay,
      );
      return { ...model, ws: null };
    case "GetAvailableConfig":
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        model.calibration.length > 0
      ) {
        model.ws.send(
          JSON.stringify({
            type: "config",
            data: model.calibration[0].catchment,
          }),
        );
        return { ...model, loading: true };
      } else {
        return model;
      }
    case "GotAvailableConfig":
      if (model.config.start === null) {
        const end = new Date(msg.data.end);
        end.setMonth(0);
        end.setDate(1);
        dispatch({
          type: "UpdateConfigField",
          data: {
            field: "start",
            value: end.toISOString().slice(0, 10),
          },
        });
      }
      if (model.config.end === null) {
        dispatch({
          type: "UpdateConfigField",
          data: { field: "end", value: msg.data.end },
        });
      }
      dispatch({ type: "GetObservations" });
      return { ...model, availableConfig: msg.data, loading: false };
    case "Import":
      [...msg.data.target.files].forEach((file) => {
        const reader = new FileReader();
        reader.onload = (event) =>
          dispatch({ type: "ImportCalibration", data: event });
        reader.onerror = () => {
          console.error("Failed to read file:", file.name);
          createNotification(`Failed to read file: ${file.name}`, true);
        };
        reader.readAsText(file);
      });
      return model;
    case "ImportCalibration":
      try {
        calibration = JSON.parse(msg.data.target.result);
      } catch (e) {
        console.error("Failed to parse calibration file:", e);
        createNotification("Invalid JSON in calibration file", true);
        return model;
      }
      const [valid, error] = verifyCalibration(model, calibration);
      if (valid) {
        const calibrations = [
          ...model.calibration,
          {
            ...calibration,
            id:
              model.calibration.length === 0
                ? 0
                : Math.max(...model.calibration.map((c) => c.id)) + 1,
          },
        ];
        window.localStorage.setItem(
          "holmes--simulation--calibration",
          JSON.stringify(calibrations),
        );
        if (model.calibration.length === 0) {
          dispatch({ type: "GetAvailableConfig" });
        } else if (model.availableConfig !== null) {
          dispatch({ type: "GetObservations" });
          if (model.config.start === null) {
            const end = new Date(model.availableConfig.end);
            end.setMonth(0);
            end.setDate(1);
            dispatch({
              type: "UpdateConfigField",
              data: {
                field: "start",
                value: end.toISOString().slice(0, 10),
              },
            });
          }
          if (model.config.end === null) {
            dispatch({
              type: "UpdateConfigField",
              data: { field: "end", value: model.availableConfig.end },
            });
          }
        }
        return {
          ...model,
          calibration: calibrations,
        };
      } else {
        createNotification(error, true);
        return model;
      }
    case "RemoveCalibration":
      calibration = model.calibration.filter((c) => c.id !== msg.data);
      window.localStorage.setItem(
        "holmes--simulation--calibration",
        JSON.stringify(calibration),
      );
      if (calibration.length === 0) {
        dispatch({
          type: "UpdateConfigField",
          data: { field: "start", value: null },
        });
        dispatch({
          type: "UpdateConfigField",
          data: { field: "end", value: null },
        });
      }
      return {
        ...model,
        calibration: calibration,
        observations: calibration.length === 0 ? null : model.observations,
        simulation: null,
        results: null,
      };
    case "UpdateConfigField":
      if (msg.data.field === "multimodel") {
        msg.data.value = !model.config.multimodel;
      }
      if (msg.data.value === "" || msg.data.value === null) {
        window.localStorage.removeItem(`holmes--simulation--${msg.data.field}`);
      } else {
        window.localStorage.setItem(
          `holmes--simulation--${msg.data.field}`,
          msg.data.value,
        );
      }
      return {
        ...model,
        config: {
          ...model.config,
          [msg.data.field]: msg.data.value === "" ? null : msg.data.value,
        },
        simulation: null,
        results: null,
      };
    case "ResetDate":
      if (model.availableConfig !== null) {
        if (msg.data === "start") {
          dispatch({
            type: "UpdateConfigField",
            data: { field: "start", value: model.availableConfig.start },
          });
        } else if (msg.data === "end") {
          dispatch({
            type: "UpdateConfigField",
            data: { field: "end", value: model.availableConfig.start },
          });
        } else {
          console.error(
            `Wrong msg data: got ${msg.data}, allowed start and end`,
          );
        }
      }
      return model;
    case "GetObservations":
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        model.calibration.length > 0 &&
        model.config.start !== null &&
        model.config.end !== null
      ) {
        model.ws.send(
          JSON.stringify({
            type: "observations",
            data: {
              catchment: model.calibration[0].catchment,
              start: model.config.start,
              end: model.config.end,
            },
          }),
        );
      } else {
        setTimeout(() => dispatch(msg), 1000);
      }
      return { ...model, loading: true };
    case "GotObservations":
      return {
        ...model,
        loading: false,
        observations: msg.data,
      };
    case "Run":
      if (
        model.ws?.readyState === WebSocket.OPEN &&
        model.calibration.length > 0 &&
        model.config.start !== null &&
        model.config.end !== null
      ) {
        model.ws.send(
          JSON.stringify({
            type: "simulation",
            data: {
              calibration: model.calibration,
              config: model.config,
            },
          }),
        );
      }
      return { ...model, loading: true };
    case "GotSimulation":
      return {
        ...model,
        simulation: msg.data.simulation,
        results: msg.data.results,
        loading: false,
      };
    case "Export":
      downloadData(model);
      return model;
    default:
      return model;
  }
}

function createDispatch(dispatch) {
  return (msg) => dispatch({ type: "SimulationMsg", data: msg });
}

function handleMessage(event, dispatch, createNotification) {
  let msg;
  try {
    msg = JSON.parse(event.data);
  } catch (e) {
    console.error("Failed to parse WebSocket message:", e);
    createNotification("Received invalid message from server", true);
    return;
  }
  switch (msg.type) {
    case "error":
      createNotification(msg.data, true);
      break;
    case "config":
      dispatch({ type: "GotAvailableConfig", data: msg.data });
      break;
    case "observations":
      dispatch({ type: "GotObservations", data: msg.data });
      break;
    case "simulation":
      dispatch({ type: "GotSimulation", data: msg.data });
      break;
    default:
      createNotification("Unknown websocket message", true);
      break;
  }
}

function downloadData(model) {
  if (
    model.calibration.length > 0 &&
    model.results !== null &&
    model.observations !== null &&
    model.simulation !== null
  ) {
    const resultsData = {
      calibrationConfig: model.calibration.map((c, i) => ({
        name: `simulation_${i + 1}`,
        ...c,
      })),
      config: model.config,
      results: model.results,
    };

    let blob = new Blob([JSON.stringify(resultsData, null, 2)], {
      type: "application/json",
    });
    let url = URL.createObjectURL(blob);
    let a = document.createElement("a");
    a.href = url;
    a.download = `${model.calibration[0].catchment.toLowerCase().replace(" ", "_")}_simulation_results.json`;
    a.click();
    URL.revokeObjectURL(url);

    const streamflowData = [
      [...Object.keys(model.simulation[0]), "observation"].join(","),
      ...model.simulation.map(
        (s, i) =>
          Object.values(s).join(",") + `,${model.observations[i].streamflow}`,
      ),
    ].join("\n");

    blob = new Blob([streamflowData], {
      type: "text/csv",
    });
    url = URL.createObjectURL(blob);
    a = document.createElement("a");
    a.href = url;
    a.download = `${model.calibration[0].catchment.toLowerCase().replace(" ", "_")}_simulation_data.csv`;
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
  return create("section", { id: "simulation" }, [
    create("h2", {}, ["Simulation"]),
    initConfigView(dispatch),
    results,
  ]);
}

export function view(model, dispatch) {
  dispatch = createDispatch(dispatch);
  calibrationView(model, dispatch);
  configView(model, dispatch);
  resultsView(model);
}

function initConfigView(dispatch) {
  return create("div", { class: "config" }, [
    create("div", { id: "simulation__calibration" }, [
      create("h3", {}, ["Calibration results"]),
      create("div", { class: "file-upload" }, [
        create("label", { for: "simulation__upload" }, [
          "Import model(s) parameters",
        ]),
        create(
          "input",
          {
            id: "simulation__upload",
            type: "file",
            accept: "application/json",
            multiple: true,
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
      create("div", { id: "simulation__calibrations-table", hidden: true }, [
        create("div", {}, [
          create("span"),
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
      { id: "simulation__config", hidden: true },
      [
        create("h3", {}, ["Simulation period"]),
        create("label", { for: "simulation__start" }, [
          create(
            "button",
            { type: "button", title: "Set to possible start" },
            ["Reset"],
            [
              {
                event: "click",
                fct: () => dispatch({ type: "ResetDate", data: "start" }),
              },
            ],
          ),
          create("span", {}, ["Start"]),
        ]),
        create(
          "input",
          { id: "simulation__start", type: "date" },
          [],
          [
            {
              event: "input",
              fct: (event) => {
                dispatch({
                  type: "UpdateConfigField",
                  data: { field: "start", value: event.target.value },
                });
              },
            },
          ],
        ),
        create("label", { for: "simulation__end" }, [
          create(
            "button",
            { type: "button", title: "Set to possible end" },
            ["Reset"],
            [
              {
                event: "click",
                fct: () => dispatch({ type: "ResetDate", data: "end" }),
              },
            ],
          ),
          create("span", {}, ["End"]),
        ]),
        create(
          "input",
          { id: "simulation__end", type: "date" },
          [],
          [
            {
              event: "input",
              fct: (event) => {
                dispatch({
                  type: "UpdateConfigField",
                  data: { field: "end", value: event.target.value },
                });
              },
            },
          ],
        ),
        create("label", { for: "simulation__multimodel", disabled: true }, [
          "Multimodel simulation",
        ]),
        createCheckbox({ id: "simulation__multimodel" }, [
          {
            event: "click",
            fct: () => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "multimodel" },
              });
            },
          },
        ]),
        create(
          "input",
          {
            id: "simulation__export",
            type: "button",
            value: "Export data",
            hidden: true,
          },
          [],
          [{ event: "click", fct: () => dispatch({ type: "Export" }) }],
        ),
        create("input", { type: "submit", value: "Run" }),
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
  return create("div", { id: "simulation__results" }, [
    create("svg", { id: "simulation__results__nse-none", class: "plot" }),
    create("svg", { id: "simulation__results__nse-sqrt", class: "plot" }),
    create("svg", { id: "simulation__results__nse-log", class: "plot" }),
    create("svg", { id: "simulation__results__mean-bias", class: "plot" }),
    create("svg", { id: "simulation__results__deviation-bias", class: "plot" }),
    create("svg", { id: "simulation__results__correlation", class: "plot" }),
    create("svg", { id: "simulation__results__streamflow", class: "plot" }),
    create("div", { id: "simulation__results__legend", class: "plot" }),
  ]);
}

function calibrationView(model, dispatch) {
  const div = document.getElementById("simulation__calibrations-table");
  [...div.querySelectorAll("div")]
    .slice(1)
    .forEach((d) => d.parentNode.removeChild(d));
  if (model.calibration.length > 0) {
    div.removeAttribute("hidden");
    model.calibration.forEach((calibration, i) => {
      div.appendChild(
        create("div", {}, [
          create("h4", {}, [
            create(
              "button",
              {},
              [createIcon("x")],
              [
                {
                  event: "click",
                  fct: () =>
                    dispatch({
                      type: "RemoveCalibration",
                      data: calibration.id,
                    }),
                },
              ],
            ),
            create("span", {}, [`Simulation ${i + 1}`]),
          ]),
          create("span", {}, [calibration.hydroModel]),
          create("span", {}, [calibration.catchment]),
          create("span", {}, [calibration.objective]),
          create("span", {}, [calibration.transformation]),
          create("span", {}, [calibration.algorithm]),
          create("span", {}, [calibration.start]),
          create("span", {}, [calibration.end]),
          create("span", {}, [
            calibration.snowModel === null ? "none" : calibration.snowModel,
          ]),
          create(
            "div",
            {},
            Object.entries(calibration.hydroParams)
              .map(([name, value]) => [name, round(value, 2)])
              .flat()
              .map((x) => create("span", {}, [x])),
          ),
        ]),
      );
    });
  } else {
    div.setAttribute("hidden", true);
  }
}

function configView(model, dispatch) {
  if (model.calibration.length === 0) {
    document.getElementById("simulation__config").setAttribute("hidden", true);
  } else {
    document.getElementById("simulation__config").removeAttribute("hidden");
  }
  const start = document.getElementById("simulation__start");
  const end = document.getElementById("simulation__end");
  const multimodel = document.getElementById("simulation__multimodel");
  if (model.config.start !== null && model.config.start !== start.value) {
    start.value = model.config.start;
  } else if (model.config.start === null) {
    start.value = "";
  }
  if (model.config.end !== null && model.config.end !== start.end) {
    end.value = model.config.end;
  } else if (model.config.end === null) {
    end.value = "";
  }
  if (
    model.config.multimodel !== null &&
    model.config.multimodel !== multimodel.value
  ) {
    multimodel.checked = model.config.multimodel;
  }
  if (model.calibration.length > 1) {
    document
      .querySelector("label[for='simulation__multimodel']")
      .removeAttribute("disabled");
    multimodel.removeAttribute("disabled");
    multimodel.parentNode.removeAttribute("disabled");
  } else {
    document
      .querySelector("label[for='simulation__multimodel']")
      .setAttribute("disabled", true);
    multimodel.setAttribute("disabled", true);
    multimodel.parentNode.setAttribute("disabled", true);
  }
  if (model.simulation === null) {
    document.getElementById("simulation__export").setAttribute("hidden", true);
  } else {
    document.getElementById("simulation__export").removeAttribute("hidden");
  }
}

function resultsView(model) {
  [
    "nse_none",
    "nse_sqrt",
    "nse_log",
    "mean_bias",
    "deviation_bias",
    "correlation",
  ].forEach((metric) => {
    metricView(model, metric);
  });
  streamflowView(model);
  legendView(model);
}

function metricView(model, metric) {
  const metrics = {
    nse_none: ["High flows", "(NSE)"],
    nse_sqrt: ["Medium flows", "(NSE-sqrt)"],
    nse_log: ["Low flows", "(NSE-log)"],
    mean_bias: ["Water balance", "(Mean bias)"],
    deviation_bias: ["Flow variability", "(Deviation bias)"],
    correlation: ["Correlation"],
  };
  const _svg = document.getElementById(
    `simulation__results__${metric.replace("_", "-")}`,
  );
  clear(_svg);
  if (model.results !== null) {
    const width = _svg.clientWidth;
    const height = _svg.clientHeight;
    _svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const boundaries = {
      l: 50,
      r: width - 25,
      t: 20,
      b: height - 20,
    };

    const svg = d3.select(_svg);

    const data = model.results.map((r) => ({
      name: r.name,
      value: r[metric],
    }));

    const xScale = d3
      .scaleBand()
      .domain(data.map((d) => d.name))
      .range([boundaries.l, boundaries.r])
      .padding(0.05);
    const yScale = d3
      .scaleLinear()
      .domain([
        Math.min(
          0,
          d3.min(data, (d) => d.value),
        ),
        Math.max(
          1,
          d3.max(data, (d) => d.value),
        ),
      ])
      .range([boundaries.b, boundaries.t])
      .nice();

    // grid
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
      .call(d3.axisBottom(xScale).ticks(5).tickSize(0))
      .call((g) => g.select(".domain").remove());
    // y axis
    svg
      .append("g")
      .attr("class", "y-axis")
      .attr("transform", `translate(${boundaries.l}, 0)`)
      .call(
        d3
          .axisLeft(yScale)
          .ticks(3)
          .tickSize(0)
          .tickFormat((x) => formatNumber(x)),
      )
      .call((g) => g.select(".domain").remove());
    const metricText = metrics[metric];
    const text = svg
      .append("text")
      .attr("x", 15)
      .attr("y", (boundaries.t + boundaries.b) / 2)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "auto")
      .attr(
        "transform",
        `rotate(-90, 15, ${(boundaries.t + boundaries.b) / 2})`,
      )
      .attr("font-size", "0.7rem");
    if (metricText.length === 1) {
      text.text(metricText[0]);
    } else {
      text
        .selectAll("tspan")
        .data(metricText)
        .join("tspan")
        .attr("x", 15)
        .attr("dy", (_, i) => (i === 0 ? 0 : "1em"))
        .attr("font-size", "0.7rem")
        .text((d) => d);
    }

    // values
    svg
      .selectAll("rect")
      .data(data)
      .join("rect")
      .attr("class", (_, i) => colours[i + 2])
      .attr("x", (d) => xScale(d.name))
      .attr("y", (d) => yScale(d.value))
      .attr("width", xScale.bandwidth())
      .attr("height", (d) => yScale.range()[0] - yScale(d.value));

    // optimal
    svg
      .append("line")
      .attr("class", colours[1])
      .attr("stroke-width", "1px")
      .attr("y1", yScale(1))
      .attr("y2", yScale(1))
      .attr("x1", xScale.range()[0])
      .attr("x2", xScale.range()[1]);
    svg
      .append("text")
      .attr("class", `${colours[1]} optimal`)
      .attr("font-size", "0.5rem")
      .attr("text-anchor", "middle")
      .attr("x", (xScale.range()[0] + xScale.range()[1]) / 2)
      .attr("y", yScale(1))
      .attr("dy", -3)
      .text("Optimal");
  }
}

function streamflowView(model) {
  const _svg = document.getElementById("simulation__results__streamflow");
  clear(_svg);
  if (model.observations !== null) {
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

    const observations = model.observations;
    const [yMin, yMax] =
      model.simulation === null
        ? [
            d3.min(observations, (d) => d.streamflow),
            d3.max(observations, (d) => d.streamflow),
          ]
        : [
            Math.min(
              d3.min(observations, (d) => d.streamflow),
              ...Object.keys(model.simulation[0])
                .slice(1)
                .map((s) => d3.min(model.simulation, (d) => d[s])),
            ),
            Math.max(
              d3.max(observations, (d) => d.streamflow),
              ...Object.keys(model.simulation[0])
                .slice(1)
                .map((s) => d3.max(model.simulation, (d) => d[s])),
            ),
          ];

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(observations, (d) => new Date(d.date)))
      .range([boundaries.l, boundaries.r]);
    const yScale = d3
      .scaleLinear()
      .domain([yMin, yMax])
      .range([boundaries.b, boundaries.t]);

    // grid
    svg
      .selectAll(".grid-vertical")
      .data(xScale.ticks(5))
      .join("line")
      .attr("class", "grid-vertical")
      .attr("x1", (d) => xScale(d))
      .attr("x2", (d) => xScale(d))
      .attr("y1", yScale.range()[0])
      .attr("y2", yScale.range()[1]);
    svg
      .selectAll(".grid-horizontal")
      .data(yScale.ticks(5))
      .join("line")
      .attr("class", "grid-horizontal")
      .attr("y1", (d) => yScale(d))
      .attr("y2", (d) => yScale(d))
      .attr("x1", xScale.range()[0])
      .attr("x2", xScale.range()[1]);

    // x axis
    svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${boundaries.b})`)
      .call(d3.axisBottom(xScale).ticks(5).tickSize(0))
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

    // observations
    svg
      .append("path")
      .attr("class", colours[0])
      .datum(observations)
      .attr(
        "d",
        d3
          .line()
          .x((d) => xScale(new Date(d.date)))
          .y((d) => yScale(d.streamflow)),
      );

    // simulation
    if (model.simulation !== null) {
      Object.keys(model.simulation[0])
        .slice(1)
        .forEach((s, i) => {
          svg
            .append("path")
            .attr("class", colours[i + 2])
            .datum(model.simulation)
            .attr(
              "d",
              d3
                .line()
                .x((d) => xScale(new Date(d.date)))
                .y((d) => yScale(d[s])),
            );
        });
    }
  }
}

function legendView(model) {
  const legend = document.getElementById("simulation__results__legend");
  clear(legend);

  if (model.observations !== null) {
    legend.appendChild(
      create("div", {}, [
        create("span", {}, ["observations"]),
        create("span", { class: colours[0] }),
      ]),
    );
  }

  if (model.simulation !== null) {
    Object.keys(model.simulation[0])
      .slice(1)
      .forEach((s, i) => {
        legend.appendChild(
          create("div", {}, [
            create("span", {}, [s.replace("_", " ")]),
            create("span", { class: colours[i + 2] }),
          ]),
        );
      });
  }
}
