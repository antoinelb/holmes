import { create, clear, createSlider } from "./utils/elements.js";
import {
  connect,
  incrementReconnectAttempt,
  isCircuitBreakerOpen,
} from "./utils/ws.js";
import { colours, toTitle, formatNumber } from "./utils/misc.js";

const WS_URL = "calibration/";

/*********/
/* model */
/*********/

export function initModel(canSave) {
  return {
    loading: false,
    ws: null,
    running: false,
    availableConfig: null,
    config: {
      hydroModel: canSave
        ? window.localStorage.getItem("holmes--calibration--hydroModel")
        : null,
      catchment: canSave
        ? window.localStorage.getItem("holmes--calibration--catchment")
        : null,
      snowModel: canSave
        ? window.localStorage.getItem("holmes--calibration--snowModel") ===
          "none"
          ? null
          : window.localStorage.getItem("holmes--calibration--snowModel")
        : null,
      objective: canSave
        ? window.localStorage.getItem("holmes--calibration--objective")
        : null,
      transformation: canSave
        ? window.localStorage.getItem("holmes--calibration--transformation")
        : null,
      start: canSave
        ? window.localStorage.getItem("holmes--calibration--start")
        : null,
      end: canSave
        ? window.localStorage.getItem("holmes--calibration--end")
        : null,
      algorithm: canSave
        ? window.localStorage.getItem("holmes--calibration--algorithm")
        : null,
    },
    params: null,
    algorithmParams: null,
    observations: null,
    simulation: null,
    results: null,
  };
}

export const initialMsg = [
  {
    type: "CalibrationMsg",
    data: { type: "Connect" },
  },
];

/**********/
/* update */
/**********/

export async function update(model, msg, dispatch, createNotification) {
  dispatch = createDispatch(dispatch);
  let config;
  let configValid;
  switch (msg.type) {
    case "Connect":
      connect(WS_URL, handleMessage, dispatch, createNotification);
      return { ...model, loading: true };
    case "Connected":
      if (model.availableConfig === null) {
        dispatch({ type: "GetAvailableConfig" });
      }
      if (model.observations === null) {
        dispatch({ type: "GetObservations" });
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
      const calibrationReconnectState = incrementReconnectAttempt(WS_URL);
      setTimeout(
        () => dispatch({ type: "Connect" }),
        calibrationReconnectState.delay,
      );
      return { ...model, ws: null };
    case "GetAvailableConfig":
      if (model.ws?.readyState === WebSocket.OPEN) {
        model.ws.send(JSON.stringify({ type: "config" }));
      }
      return { ...model, loading: true };
    case "GotAvailableConfig":
      config = Object.fromEntries(
        Object.entries(msg.data).map(([key, value]) => [
          key.split("_")[0] + key.split("_").slice(1).map(toTitle).join(""),
          value,
        ]),
      );
      Object.entries(config).forEach(([field, values]) => {
        if (model.config[field] === null) {
          dispatch({
            type: "UpdateConfigField",
            data: {
              field: field,
              value:
                typeof values[0] !== "object"
                  ? values[0]
                  : field === "catchment" ||
                      field === "hydroModel" ||
                      field === "algorithm"
                    ? values[0].name
                    : null,
            },
          });
        }
      });
      model = {
        ...model,
        loading: false,
        availableConfig: config,
      };
      if (model.config.catchment !== null) {
        updateCatchment(model, model.config.catchment, dispatch);
      }
      return model;
    case "UpdateConfigField":
      window.localStorage.setItem(
        `holmes--calibration--${msg.data.field}`,
        msg.data.value === null ? "none" : msg.data.value,
      );
      if (msg.data.field === "catchment") {
        updateCatchment(model, msg.data.value, dispatch);
      }
      if (msg.data.field === "start" || msg.data.field === "end") {
        dispatch({ type: "GetObservations" });
      }
      return {
        ...model,
        config: {
          ...model.config,
          [msg.data.field]: msg.data.value === "none" ? null : msg.data.value,
        },
        simulation: null,
        results: null,
      };
    case "ResetDate":
      if (model.availableConfig !== null && model.config.catchment !== null) {
        const catchment = model.availableConfig.catchment.filter(
          (c) => c.name == model.config.catchment,
        )[0];
        if (msg.data === "start") {
          dispatch({
            type: "UpdateConfigField",
            data: { field: "start", value: catchment.start },
          });
        } else if (msg.data === "end") {
          dispatch({
            type: "UpdateConfigField",
            data: { field: "end", value: catchment.end },
          });
        } else {
          console.error(
            `Wrong msg data: got ${msg.data}, allowed start and end`,
          );
        }
      }
      return model;
    case "GetObservations":
      configValid =
        model.config.catchment !== null &&
        model.config.catchment.start !== null &&
        model.config.catchment.end !== null;
      if (model.ws?.readyState === WebSocket.OPEN && configValid) {
        model.ws.send(
          JSON.stringify({
            type: "observations",
            data: {
              catchment: model.config.catchment,
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
    case "RunManual":
      config = model.config;
      config.hydroParams = [
        ...document.querySelectorAll(
          "#calibration__manual-config input[type='number']",
        ),
      ].map((input) => parseFloat(input.value));
      configValid = Object.entries(config).every(
        ([field, value]) => field === "snowModel" || value !== null,
      );
      if (model.ws?.readyState === WebSocket.OPEN && configValid) {
        model.ws.send(
          JSON.stringify({
            type: "manual",
            data: config,
          }),
        );
      } else {
        setTimeout(() => dispatch(msg), 1000);
      }
      return { ...model, loading: true };
    case "StartCalibration":
      config = model.config;
      config.algorithmParams = Object.fromEntries(
        [
          ...document.querySelectorAll("#calibration__automatic-config input"),
        ].map((input) => [
          input.id.split("__").reverse()[0],
          parseFloat(input.value),
        ]),
      );
      configValid = Object.entries(config).every(
        ([field, value]) => field === "snowModel" || value !== null,
      );
      if (model.ws?.readyState === WebSocket.OPEN && configValid) {
        model.ws.send(
          JSON.stringify({
            type: "calibration_start",
            data: config,
          }),
        );
      } else {
        setTimeout(() => dispatch(msg), 1000);
      }
      return { ...model, loading: true, running: true, results: null };
    case "StopCalibration":
      if (model.ws?.readyState === WebSocket.OPEN && model.running) {
        model.ws.send(
          JSON.stringify({
            type: "calibration_stop",
          }),
        );
      }
      return { ...model, loading: false, running: false };
    case "GotResults":
      return {
        ...model,
        loading: !msg.data.done,
        running: model.running && !msg.data.done,
        simulation: msg.data.simulation,
        results:
          model.results === null
            ? [{ params: msg.data.params, objective: msg.data.objective }]
            : [
                ...model.results,
                { params: msg.data.params, objective: msg.data.objective },
              ],
      };
    case "ExportParams":
      downloadParams(model, createNotification);
      return model;
    case "ExportData":
      downloadData(model, createNotification);
      return model;
    default:
      return model;
  }
}

function createDispatch(dispatch) {
  return (msg) => dispatch({ type: "CalibrationMsg", data: msg });
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
    case "result":
      dispatch({ type: "GotResults", data: msg.data });
      break;
    default:
      createNotification("Unknown websocket message", true);
      break;
  }
}

function updateCatchment(model, catchment, dispatch) {
  const _catchment = model.availableConfig.catchment.filter(
    (c) => c.name == catchment,
  )[0];
  if (!_catchment.snow && model.config.snowModel !== null) {
    dispatch({
      type: "UpdateConfigField",
      data: { field: "snowModel", value: "none" },
    });
  }
  if (model.config.start === null || model.config.start < _catchment.start) {
    dispatch({
      type: "UpdateConfigField",
      data: { field: "start", value: _catchment.start },
    });
  }
  if (model.config.end === null || model.config.end > _catchment.end) {
    dispatch({
      type: "UpdateConfigField",
      data: { field: "end", value: _catchment.end },
    });
  }
  dispatch({ type: "GetObservations" });
}

function downloadParams(model, createNotification) {
  if (
    model.availableConfig !== null &&
    model.config.catchment !== null &&
    model.config.hydroModel !== null &&
    model.results !== null
  ) {
    const paramNames = model.availableConfig.hydroModel
      .filter((h) => h.name == model.config.hydroModel)[0]
      .params.map((p) => p.name);
    const data = {
      ...model.config,
      hydroParams: Object.fromEntries(
        paramNames.map((p, i) => [
          p,
          model.results[model.results.length - 1].params[i],
        ]),
      ),
    };

    const filename = `${model.config.catchment.toLowerCase().replace(" ", "_")}_${model.config.hydroModel}_params.json`;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    createNotification(`Downloaded calibration parameters to ${filename}.`);
  }
}

function downloadData(model, createNotification) {
  if (
    model.availableConfig !== null &&
    model.config.catchment !== null &&
    model.config.hydroModel !== null &&
    model.config.objective !== null &&
    model.results !== null &&
    model.observations !== null &&
    model.simulation !== null
  ) {
    const paramNames = model.availableConfig.hydroModel
      .filter((h) => h.name == model.config.hydroModel)[0]
      .params.map((p) => p.name);
    const paramData = model.results.map((r) =>
      Object.fromEntries(paramNames.map((p, i) => [p, r.params[i]])),
    );
    const objectiveData = model.results.map((r) => r.objective);
    const data = {
      parameters: paramData,
      [model.config.objective]: objectiveData,
    };

    let filename = `${model.config.catchment.toLowerCase().replace(" ", "_")}_${model.config.hydroModel}_calibration_results.json`;
    let blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    let url = URL.createObjectURL(blob);
    let a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    createNotification(`Downloaded calibration results to ${filename}.`);

    const streamflowData = [
      ["date", "observation", "simulation"].join(","),
      ...model.observations.map(
        (o, i) => `${o.date},${o.streamflow},${model.simulation[i].streamflow}`,
      ),
    ].join("\n");

    filename = `${model.config.catchment.toLowerCase().replace(" ", "_")}_${model.config.hydroModel}_calibration_data.csv`;
    blob = new Blob([streamflowData], {
      type: "text/csv",
    });
    url = URL.createObjectURL(blob);
    a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    createNotification(`Downloaded calibration timeseries to ${filename}.`);
  }
}

/********/
/* view */
/********/

export function initView(dispatch) {
  dispatch = createDispatch(dispatch);

  const calibrationResults = create("div", { id: "calibration__results" });

  let resizeTimeout;
  const resizeObserver = new ResizeObserver(() => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => dispatch({ type: "Noop" }), 100);
  });
  resizeObserver.observe(calibrationResults);

  return create("section", { id: "calibration" }, [
    create("h2", {}, ["Calibration"]),
    create("div", { class: "config" }, [
      initGeneralSettingsView(dispatch),
      initCalibrationSettingsView(dispatch),
    ]),
    calibrationResults,
  ]);
}

export function view(model, dispatch) {
  dispatch = createDispatch(dispatch);
  generalSettingsView(model);
  calibrationSettingsView(model);
  resultsView(model);
}

function initGeneralSettingsView(dispatch) {
  return create(
    "form",
    { id: "calibration__general-config" },
    [
      create("h3", {}, ["General settings"]),
      create("label", { for: "calibration__hydro-model" }, [
        "Hydrological model",
      ]),
      create(
        "select",
        { id: "calibration__hydro-model" },
        [],
        [
          {
            event: "input",
            fct: (event) => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "hydroModel", value: event.target.value },
              });
            },
          },
        ],
      ),
      create("label", { for: "calibration__catchment" }, ["Catchment"]),
      create(
        "select",
        { id: "calibration__catchment" },
        [],
        [
          {
            event: "input",
            fct: (event) => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "catchment", value: event.target.value },
              });
            },
          },
        ],
      ),
      create("label", { for: "calibration__snow-model" }, [
        "Snow model (optional)",
      ]),
      create(
        "select",
        { id: "calibration__snow-model" },
        [],
        [
          {
            event: "input",
            fct: (event) => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "snowModel", value: event.target.value },
              });
            },
          },
        ],
      ),
      create("label", { for: "calibration__objective" }, [
        "Objective criteria",
      ]),
      create(
        "select",
        { id: "calibration__objective" },
        [],
        [
          {
            event: "input",
            fct: (event) => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "objective", value: event.target.value },
              });
            },
          },
        ],
      ),
      create("label", { for: "calibration__transformation" }, [
        "Streamflow transformation",
      ]),
      create(
        "select",
        { id: "calibration__transformation" },
        [],
        [
          {
            event: "input",
            fct: (event) => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "transformation", value: event.target.value },
              });
            },
          },
        ],
      ),
      create("label", { for: "calibration__start" }, [
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
        create("span", {}, ["Calibration start"]),
      ]),
      create(
        "input",
        { id: "calibration__start", type: "date" },
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
      create("label", { for: "calibration__end" }, [
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
        create("span", {}, ["Calibration end"]),
      ]),
      create(
        "input",
        { id: "calibration__end", type: "date" },
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
      create("label", { for: "calibration__algorithm" }, [
        "Calibration algorithm",
      ]),
      create(
        "select",
        { id: "calibration__algorithm" },
        [],
        [
          {
            event: "input",
            fct: (event) => {
              dispatch({
                type: "UpdateConfigField",
                data: { field: "algorithm", value: event.target.value },
              });
            },
          },
        ],
      ),
    ],
    [
      {
        event: "submit",
        fct: (event) => {
          event.preventDefault();
        },
      },
    ],
  );
}

function initCalibrationSettingsView(dispatch) {
  return create("div", { id: "calibration__calibration-config" }, [
    initManualCalibrationSettingsView(dispatch),
    initAutomaticCalibrationSettingsView(dispatch),
  ]);
}

function initManualCalibrationSettingsView(dispatch) {
  return create(
    "form",
    { id: "calibration__manual-config" },
    [
      create("h3", {}, ["Manual calibration settings"]),
      create("div"),
      create("input", { type: "submit", value: "Run" }),
      create(
        "input",
        {
          class: "calibration__export-params",
          type: "button",
          value: "Export parameters",
          disabled: true,
        },
        [],
        [{ event: "click", fct: () => dispatch({ type: "ExportParams" }) }],
      ),
      create(
        "input",
        {
          class: "calibration__export-data",
          type: "button",
          value: "Export data",
          disabled: true,
        },
        [],
        [{ event: "click", fct: () => dispatch({ type: "ExportData" }) }],
      ),
    ],
    [
      {
        event: "submit",
        fct: (event) => {
          event.preventDefault();
          dispatch({ type: "RunManual" });
        },
      },
    ],
  );
}

function initAutomaticCalibrationSettingsView(dispatch) {
  return create(
    "form",
    { id: "calibration__automatic-config", hidden: true },
    [
      create("h3", {}, []),
      create("div"),
      create(
        "input",
        {
          id: "calibration__automatic__start",
          type: "submit",
          value: "Start calibration",
        },
        [],
        [
          {
            event: "click",
            fct: () => {
              dispatch({ type: "StartCalibration" });
            },
          },
        ],
      ),
      create(
        "input",
        {
          id: "calibration__automatic__stop",
          type: "button",
          value: "Stop calibration",
          hidden: true,
        },
        [],
        [
          {
            event: "click",
            fct: () => {
              dispatch({ type: "StopCalibration" });
            },
          },
        ],
      ),
      create(
        "input",
        {
          class: "calibration__export-params",
          type: "button",
          value: "Export parameters",
          disabled: true,
        },
        [],
        [{ event: "click", fct: () => dispatch({ type: "ExportParams" }) }],
      ),
      create(
        "input",
        {
          class: "calibration__export-data",
          type: "button",
          value: "Export data",
          disabled: true,
        },
        [],
        [{ event: "click", fct: () => dispatch({ type: "ExportData" }) }],
      ),
    ],
    [
      {
        event: "submit",
        fct: (event) => {
          event.preventDefault();
        },
      },
    ],
  );
}

function generalSettingsView(model) {
  const hydroSelect = document.getElementById("calibration__hydro-model");
  if (hydroSelect.children.length === 0 && model.availableConfig !== null) {
    model.availableConfig.hydroModel.forEach((o) => {
      hydroSelect.appendChild(create("option", { value: o.name }, [o.name]));
    });
  }
  if (model.config.hydroModel !== null) {
    hydroSelect.value = model.config.hydroModel;
  }

  const catchmentSelect = document.getElementById("calibration__catchment");
  if (catchmentSelect.children.length === 0 && model.availableConfig !== null) {
    model.availableConfig.catchment.forEach((o) => {
      catchmentSelect.appendChild(
        create(
          "option",
          {
            value: o.name,
          },
          [o.name],
        ),
      );
    });
  }
  if (model.config.catchment !== null) {
    catchmentSelect.value = model.config.catchment;
  }

  const snowSelect = document.getElementById("calibration__snow-model");
  if (snowSelect.children.length === 0 && model.availableConfig !== null) {
    model.availableConfig.snowModel.forEach((o) => {
      snowSelect.appendChild(
        create(
          "option",
          {
            value: o === null ? "none" : o,
          },
          [o === null ? "none" : o],
        ),
      );
    });
  }
  if (model.config.snowModel !== null) {
    snowSelect.value = model.config.snowModel;
  } else {
    snowSelect.value = "none";
  }

  const objectiveSelect = document.getElementById("calibration__objective");
  if (objectiveSelect.children.length === 0 && model.availableConfig !== null) {
    model.availableConfig.objective.forEach((o) => {
      objectiveSelect.appendChild(create("option", { value: o }, [o]));
    });
  }
  if (model.config.objective !== null) {
    objectiveSelect.value = model.config.objective;
  }

  const transformationSelect = document.getElementById(
    "calibration__transformation",
  );
  if (
    transformationSelect.children.length === 0 &&
    model.availableConfig !== null
  ) {
    model.availableConfig.transformation.forEach((o) => {
      transformationSelect.appendChild(
        create("option", { value: o }, [
          {
            log: "Low flows: log",
            sqrt: "Medium flows: sqrt",
            none: "High flows: none",
          }[o],
        ]),
      );
    });
  }
  if (model.config.transformation !== null) {
    transformationSelect.value = model.config.transformation;
  }

  const algorithmSelect = document.getElementById("calibration__algorithm");
  if (algorithmSelect.children.length === 0 && model.availableConfig !== null) {
    model.availableConfig.algorithm.forEach((o) => {
      algorithmSelect.appendChild(
        create("option", { value: o.name }, [
          {
            manual: "Manual",
            sce: "Automatic - SCE",
          }[o.name],
        ]),
      );
    });
  }
  if (model.config.algorithm !== null) {
    algorithmSelect.value = model.config.algorithm;
  }

  datesView(model);
  snowConfigView(model);
}

function datesView(model) {
  if (model.availableConfig !== null && model.config.catchment !== null) {
    const start = document.getElementById("calibration__start");
    const end = document.getElementById("calibration__end");
    const catchment = model.availableConfig.catchment.filter(
      (c) => c.name == model.config.catchment,
    )[0];
    if (start.min === "" || start.min !== catchment.min) {
      start.min = catchment.start;
    }
    if (start.max === "" || start.max !== catchment.max) {
      start.max = catchment.end;
    }
    if (start.value === "") {
      start.value =
        model.config.start === null ? catchment.start : model.config.start;
    }
    if (end.min === "" || end.min !== catchment.min) {
      end.min = catchment.start;
    }
    if (end.max === "" || end.max !== catchment.max) {
      end.max = catchment.end;
    }
    if (end.value === "") {
      end.value = model.config.end === null ? catchment.end : model.config.end;
    }
    if (model.config.start !== null && start.value !== model.config.start) {
      start.value = model.config.start;
    }
    if (model.config.end !== null && start.end !== model.config.end) {
      end.value = model.config.end;
    }
  }
}

function snowConfigView(model) {
  if (model.availableConfig !== null && model.config.catchment !== null) {
    const label = document.querySelector(
      "label[for='calibration__snow-model']",
    );
    const select = document.getElementById("calibration__snow-model");
    const catchment = model.availableConfig.catchment.filter(
      (c) => c.name == model.config.catchment,
    )[0];
    if (catchment.snow) {
      label.removeAttribute("disabled");
      select.removeAttribute("disabled");
    } else {
      label.setAttribute("disabled", true);
      select.setAttribute("disabled", true);
    }
  }
}

function calibrationSettingsView(model) {
  const manualConfig = document.getElementById("calibration__manual-config");
  const automaticConfig = document.getElementById(
    "calibration__automatic-config",
  );

  if (model.config.algorithm === null || model.config.algorithm === "manual") {
    manualConfig.removeAttribute("hidden");
    automaticConfig.setAttribute("hidden", true);
  } else {
    manualConfig.setAttribute("hidden", true);
    automaticConfig.removeAttribute("hidden");
  }

  manualCalibrationSettingsView(model);
  automaticCalibrationSettingsView(model);
}

function manualCalibrationSettingsView(model) {
  if (model.availableConfig !== null && model.config.hydroModel !== null) {
    const hydro = model.availableConfig.hydroModel.filter(
      (h) => h.name == model.config.hydroModel,
    )[0];
    const div = document.querySelector("#calibration__manual-config > div");
    if (
      hydro.params.some(
        (param) =>
          document.getElementById(
            `calibration__manual-config__${param.name}`,
          ) === null,
      )
    ) {
      clear(div);
      hydro.params.forEach((param) => {
        div.appendChild(
          create(
            "label",
            { for: `calibration__manual-config__${param.name}` },
            [param.name],
          ),
        );
        div.appendChild(
          createSlider(
            `calibration__manual-config__${param.name}`,
            param.min,
            param.max,
            false,
            [],
            param.default,
          ),
        );
      });
    }
  }
}

function automaticCalibrationSettingsView(model) {
  if (
    model.availableConfig !== null &&
    model.config.hydroModel !== null &&
    model.config.algorithm !== null &&
    model.config.algorithm !== "manual"
  ) {
    const algo = model.availableConfig.algorithm.filter(
      (a) => a.name == model.config.algorithm,
    )[0];
    const automaticConfig = document.getElementById(
      "calibration__automatic-config",
    );
    automaticConfig.querySelector("h3").textContent =
      `Automatic - ${algo.name.toUpperCase()} calibration settings`;
    const div = document.querySelector("#calibration__automatic-config > div");
    if (
      algo.params.some(
        (param) =>
          document.getElementById(
            `calibration__automatic-config__${param.name}`,
          ) === null,
      )
    ) {
      clear(div);
      algo.params.forEach((param) => {
        div.appendChild(
          create(
            "label",
            { for: `calibration__automatic-config__${param.name}` },
            [param.name],
          ),
        );
        div.appendChild(
          create("input", {
            id: `calibration__automatic-config__${param.name}`,
            type: "number",
            value: param.default,
            step: param.integer ? 1 : 0.001,
            ...(param.min === null ? {} : { min: param.min }),
            ...(param.max === null ? {} : { max: param.max }),
          }),
        );
      });
    }

    if (model.running) {
      document
        .getElementById("calibration__automatic__start")
        .setAttribute("hidden", true);
      document
        .getElementById("calibration__automatic__stop")
        .removeAttribute("hidden");
    } else {
      document
        .getElementById("calibration__automatic__start")
        .removeAttribute("hidden");
      document
        .getElementById("calibration__automatic__stop")
        .setAttribute("hidden", true);
    }
  }
}

function resultsView(model) {
  if (model.availableConfig !== null && model.config.hydroModel !== null) {
    let div = document.getElementById("calibration__results");
    const hydro = model.availableConfig.hydroModel.filter(
      (h) => h.name == model.config.hydroModel,
    )[0];
    if (
      hydro.params.some(
        (param) =>
          document.getElementById(
            `calibration__results__${param.name}-plot`,
          ) === null,
      ) ||
      [...div.querySelectorAll("[id$='-plot']")].some(
        (el) =>
          !hydro.params.some(
            (p) => `calibration__results__${p.name}-plot` === el.id,
          ),
      )
    ) {
      clear(div);
      hydro.params.forEach((param) => {
        div.appendChild(
          create("svg", {
            id: `calibration__results__${param.name}-plot`,
            class: "plot",
          }),
        );
      });
      div.appendChild(
        create("svg", { id: "calibration__results__objective", class: "plot" }),
      );
      div.appendChild(
        create("svg", {
          id: "calibration__results__streamflow",
          class: "plot",
        }),
      );
      div.appendChild(
        create("div", { id: "calibration__results__legend", class: "plot" }),
      );
    }

    streamflowView(model);
    legendView(model);
    objectiveView(model);
    hydro.params.forEach((param, i) => {
      metricView(model, param.name, i);
    });

    if (model.results === null) {
      [...document.querySelectorAll(".calibration__export-params")].forEach(
        (e) => e.setAttribute("disabled", true),
      );
      [...document.querySelectorAll(".calibration__export-data")].forEach((e) =>
        e.setAttribute("disabled", true),
      );
    } else {
      [...document.querySelectorAll(".calibration__export-params")].forEach(
        (e) => e.removeAttribute("disabled"),
      );
      [...document.querySelectorAll(".calibration__export-data")].forEach((e) =>
        e.removeAttribute("disabled"),
      );
    }
  }
}

function streamflowView(model) {
  const _svg = document.getElementById("calibration__results__streamflow");
  clear(_svg);
  if (model.observations === null) {
    _svg.setAttribute("hidden", true);
  } else {
    _svg.removeAttribute("hidden");
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

    // Clip path to prevent lines from extending beyond plot boundaries
    const clipId = "streamflow-clip";
    svg
      .append("defs")
      .append("clipPath")
      .attr("id", clipId)
      .append("rect")
      .attr("x", boundaries.l)
      .attr("y", boundaries.t)
      .attr("width", boundaries.r - boundaries.l)
      .attr("height", boundaries.b - boundaries.t);

    const observations = model.observations;

    const xDomain = d3.extent(observations, (d) => new Date(d.date));

    const xScale = d3
      .scaleTime()
      .domain(xDomain)
      .range([boundaries.l, boundaries.r]);
    const yScale = d3
      .scaleLinear()
      .domain([
        d3.min(observations, (d) => d.streamflow),
        d3.max(observations, (d) => d.streamflow),
      ])
      .range([boundaries.b, boundaries.t]);

    // grid
    svg
      .selectAll(".grid-vertical")
      .data(xScale.ticks())
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

    // Create clipped group for chart content (warmup, lines)
    const chartGroup = svg
      .append("g")
      .attr("class", "chart-content")
      .attr("clip-path", `url(#${clipId})`);

    // warmup
    if (observations[0].date !== model.config.start) {
      chartGroup
        .append("rect")
        .attr("class", "warmup-rect")
        .attr("x", xScale(new Date(observations[0].date)))
        .attr("y", yScale.range()[1])
        .attr(
          "width",
          xScale(new Date(model.config.start)) -
            xScale(new Date(observations[0].date)),
        )
        .attr("height", yScale.range()[0] - yScale.range()[1])
        .attr("fill", "currentColor")
        .attr("class", `warmup-rect ${colours[0]}`);
      chartGroup
        .append("text")
        .attr("class", `warmup warmup-text ${colours[0]}`)
        .attr("text-anchor", "start")
        .attr("dominant-baseline", "hanging")
        .attr("x", xScale.range()[0])
        .attr("y", yScale.range()[1])
        .attr("dx", 5)
        .attr("dy", 1)
        .text("Warmup");
    }

    // observations
    chartGroup
      .append("path")
      .attr("class", `observation-line ${colours[0]}`)
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
      chartGroup
        .append("path")
        .attr("class", `simulation-line ${colours[2]}`)
        .datum(model.simulation)
        .attr(
          "d",
          d3
            .line()
            .x((d) => xScale(new Date(d.date)))
            .y((d) => yScale(d.streamflow)),
        );
    }

    // zoom
    const brush = d3
      .brushX()
      .extent([
        [boundaries.l, boundaries.t],
        [boundaries.r, boundaries.b],
      ])
      .on("end", brushed);

    const brushGroup = svg.append("g").attr("class", "brush").call(brush);

    svg.on("dblclick", resetZoom);

    function brushed(event) {
      const selection = event.selection;
      if (!selection) return;

      const [x0, x1] = selection.map(xScale.invert);
      xScale.domain([x0, x1]);

      brushGroup.call(brush.move, null);

      updateChart();
    }

    function resetZoom() {
      xScale.domain(xDomain);
      updateChart();
    }

    function updateChart() {
      const t = svg.transition().duration(750);

      svg
        .select(".x-axis")
        .transition(t)
        .call(d3.axisBottom(xScale).ticks(5).tickSize(0))
        .call((g) => g.select(".domain").remove());

      const gridData = xScale.ticks();
      svg
        .selectAll(".grid-vertical")
        .data(gridData)
        .join(
          (enter) =>
            enter
              .append("line")
              .attr("class", "grid-vertical")
              .attr("x1", (d) => xScale(d))
              .attr("x2", (d) => xScale(d))
              .attr("y1", yScale.range()[0])
              .attr("y2", yScale.range()[1]),
          (update) =>
            update
              .transition(t)
              .attr("x1", (d) => xScale(d))
              .attr("x2", (d) => xScale(d)),
          (exit) => exit.remove(),
        );

      const line = d3
        .line()
        .x((d) => xScale(new Date(d.date)))
        .y((d) => yScale(d.streamflow));

      svg.select(".observation-line").transition(t).attr("d", line);

      svg.select(".simulation-line").transition(t).attr("d", line);

      const warmupEndDate = new Date(model.config.start);
      const currentXMin = xScale.domain()[0];
      const warmupVisible = currentXMin < warmupEndDate;

      svg
        .select(".warmup-rect")
        .transition(t)
        .attr("x", xScale(new Date(observations[0].date)))
        .attr(
          "width",
          Math.max(
            0,
            xScale(warmupEndDate) - xScale(new Date(observations[0].date)),
          ),
        );

      // Only show warmup text if warmup period is visible
      // Position text at the left edge of visible area or start of warmup rect
      const warmupTextX = Math.max(
        xScale.range()[0],
        xScale(new Date(observations[0].date)),
      );
      svg
        .select(".warmup-text")
        .transition(t)
        .attr("x", warmupTextX)
        .style("opacity", warmupVisible ? 1 : 0);
    }
  }
}

function legendView(model) {
  const legend = document.getElementById("calibration__results__legend");
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
    legend.appendChild(
      create("div", {}, [
        create("span", {}, ["simulation"]),
        create("span", { class: colours[2] }),
      ]),
    );
  }
}

function metricView(model, param, i) {
  const _svg = document.getElementById(`calibration__results__${param}-plot`);
  clear(_svg);
  if (model.results === null) {
    _svg.setAttribute("hidden", true);
  } else {
    _svg.removeAttribute("hidden");
    const width = _svg.clientWidth;
    const height = _svg.clientHeight;
    _svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const boundaries = {
      l: 60,
      r: width - 25,
      t: 5,
      b: height - 20,
    };

    const svg = d3.select(_svg);

    const values = model.results.map((r) => r.params[i]);

    const xScale = d3
      .scalePoint()
      .domain(d3.range(1, values.length + 1))
      .range([boundaries.l, boundaries.r])
      .padding(0.25);
    const yScale = d3
      .scaleLinear()
      .domain([d3.min(values) - 1, d3.max(values) + 1])
      .range([boundaries.b, boundaries.t])
      .nice();
    const yTicks = yScale.ticks(5);

    // grid
    svg
      .selectAll(".grid-vertical")
      .data(d3.range(1, values.length + 1))
      .join("line")
      .attr("class", "grid-vertical")
      .attr("x1", (d) => xScale(d))
      .attr("x2", (d) => xScale(d))
      .attr("y1", yScale.range()[0])
      .attr("y2", yScale.range()[1]);
    svg
      .selectAll(".grid-horizontal")
      .data(yTicks.slice(1, yTicks.length - 1))
      .join("line")
      .attr("class", "grid-horizontal")
      .attr("y1", (d) => yScale(d))
      .attr("y2", (d) => yScale(d))
      .attr("x1", xScale.range()[0])
      .attr("x2", xScale.range()[1]);

    // x axis
    const xAxis = svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${boundaries.b})`)
      .call(
        d3
          .axisBottom(xScale)
          .tickSize(0)
          .tickValues(
            xScale.domain().length <= 10
              ? xScale.domain()
              : xScale
                  .domain()
                  .filter((_, i, arr) => i % Math.ceil(arr.length / 10) === 0),
          ),
      )
      .call((g) => g.select(".domain").remove());
    xAxis.selectAll("text").attr("dy", 10);
    // y axis
    const yAxis = svg
      .append("g")
      .attr("class", "y-axis")
      .attr("transform", `translate(${boundaries.l}, 0)`)
      .call(d3.axisLeft(yScale).tickSize(0).ticks(5))
      .call((g) => g.select(".domain").remove());
    yAxis.selectAll("text").attr("dx", -5);
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
      .text(param);

    // markers
    svg
      .selectAll("circle")
      .data(values)
      .join("circle")
      .attr("class", colours[2])
      .attr("cx", (_, i) => xScale(i + 1))
      .attr("cy", (d) => yScale(d))
      .attr("r", 2);
    // line
    svg
      .append("path")
      .attr("class", colours[2])
      .datum(values)
      .attr(
        "d",
        d3
          .line()
          .x((_, i) => xScale(i + 1))
          .y((d) => yScale(d)),
      );
  }
}

function objectiveView(model) {
  const _svg = document.getElementById("calibration__results__objective");
  clear(_svg);
  if (model.results === null) {
    _svg.setAttribute("hidden", true);
  } else {
    _svg.removeAttribute("hidden");
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

    const objective = model.results.map((r) => r.objective);
    const optimal = model.config.objective == "rmse" ? 0 : 1;

    const xScale = d3
      .scalePoint()
      .domain(d3.range(1, objective.length + 1))
      .range([boundaries.l, boundaries.r])
      .padding(0.25);
    const yScale = d3
      .scaleLinear()
      .domain([
        Math.min(0, Math.floor(d3.min(objective))),
        Math.max(1, Math.ceil(d3.max(objective))),
      ])
      .range([boundaries.b, boundaries.t])
      .nice();
    const yTicks = yScale.ticks(5);

    // grid
    svg
      .selectAll(".grid-vertical")
      .data(d3.range(1, objective.length + 1))
      .join("line")
      .attr("class", "grid-vertical")
      .attr("x1", (d) => xScale(d))
      .attr("x2", (d) => xScale(d))
      .attr("y1", yScale.range()[0])
      .attr("y2", yScale.range()[1]);
    svg
      .selectAll(".grid-horizontal")
      .data(yTicks.slice(1, yTicks.length - 1))
      .join("line")
      .attr("class", "grid-horizontal")
      .attr("y1", (d) => yScale(d))
      .attr("y2", (d) => yScale(d))
      .attr("x1", xScale.range()[0])
      .attr("x2", xScale.range()[1]);

    // x axis
    const xAxis = svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${boundaries.b})`)
      .call(
        d3
          .axisBottom(xScale)
          .tickSize(0)
          .tickValues(
            xScale.domain().length <= 10
              ? xScale.domain()
              : xScale
                  .domain()
                  .filter((_, i, arr) => i % Math.ceil(arr.length / 10) === 0),
          ),
      )
      .call((g) => g.select(".domain").remove());
    xAxis.selectAll("text").attr("dy", 10);
    // y axis
    const yAxis = svg
      .append("g")
      .attr("class", "y-axis")
      .attr("transform", `translate(${boundaries.l}, 0)`)
      .call(d3.axisLeft(yScale).tickSize(0).ticks(5))
      .call((g) => g.select(".domain").remove());
    yAxis.selectAll("text").attr("dx", -5);
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
      .text(model.config.objective);

    // markers
    svg
      .selectAll("circle")
      .data(objective)
      .join("circle")
      .attr("class", colours[2])
      .attr("cx", (_, i) => xScale(i + 1))
      .attr("cy", (d) => yScale(d))
      .attr("r", 2);
    // line
    svg
      .append("path")
      .attr("class", colours[2])
      .datum(objective)
      .attr(
        "d",
        d3
          .line()
          .x((_, i) => xScale(i + 1))
          .y((d) => yScale(d)),
      );

    // optimal
    svg
      .append("line")
      .attr("class", `optimal ${colours[1]}`)
      .attr("y1", yScale(optimal))
      .attr("y2", yScale(optimal))
      .attr("x1", xScale.range()[0])
      .attr("x2", xScale.range()[1]);
    svg
      .append("text")
      .attr("class", `optimal ${colours[1]}`)
      .attr("text-anchor", "end")
      .attr(
        "dominant-baseline",
        model.config.objective == "rmse" ? "auto" : "hanging",
      )
      .attr("x", xScale.range()[1])
      .attr("y", yScale(optimal))
      .attr("dy", model.config.objective == "rmse" ? -3 : 3)
      .text("Optimal");
  }
}
