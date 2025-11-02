import { clear, createSlider, createLoading } from "./utils.js";
import { toggleLoading, addNotification } from "./header.js";
import "/static/assets/plotly-3.1.0.min.js";

/*********/
/* model */
/*********/

let model = {
  runAllowed: false,
  config: {
    hydrologicalModel: {},
    catchments: [],
    snowModel: {},
    objectiveCriteria: [],
    streamflowTransformation: [],
    algorithm: [],
  },
  results: null,
};

/********/
/* init */
/********/

export async function init() {
  addEventListeners();
  await initView();
}

async function initView() {
  await initAvailableConfig();
}

function addEventListeners() {
  document
    .getElementById("calibration__general-config")
    .addEventListener("submit", (event) => {
      event.preventDefault();
    });
  document
    .getElementById("calibration__catchment")
    .addEventListener("change", (event) => {
      updateCatchment(event.target.value);
    });
  document
    .querySelector("label[for='calibration__period-start'] button")
    .addEventListener("click", updateToPeriodStart);
  document
    .querySelector("label[for='calibration__period-end'] button")
    .addEventListener("click", updateToPeriodEnd);
  document
    .getElementById("calibration__algorithm")
    .addEventListener("change", (event) =>
      updateShownConfig(event.target.value),
    );
  document
    .querySelector(".results__export")
    .addEventListener("click", exportCalibrationResults);
}

async function initAvailableConfig() {
  const resp = await fetch("/calibration/config");
  const config = await resp.json();
  model.config = {
    hydrologicalModel: config.hydrological_model,
    catchments: config.catchment.map((catchment) => ({
      name: catchment[0],
      snowAvailable: catchment[1],
      periodMin: catchment[2][0],
      periodMax: catchment[2][1],
    })),
    snowModel: config.snow_model,
    objectiveCriteria: config.objective_criteria,
    streamflowTransformation: config.streamflow_transformation,
    algorithm: config.algorithm,
  };

  addOptions(
    "calibration__hydrological-model",
    Object.keys(model.config.hydrologicalModel),
  );
  addOptions(
    "calibration__catchment",
    model.config.catchments.map((catchment) => catchment.name),
  );
  addOptions("calibration__snow-model", Object.keys(model.config.snowModel));
  addOptions("calibration__objective-criteria", model.config.objectiveCriteria);
  addOptions(
    "calibration__streamflow-transformation",
    model.config.streamflowTransformation,
  );
  addOptions("calibration__algorithm", model.config.algorithm);

  updateCatchment(model.config.catchments[0].name);

  document
    .getElementById("calibration__hydrological-model")
    .addEventListener("change", (event) =>
      updateManualCalibrationSettings(event.target.value),
    );
  updateManualCalibrationSettings(
    Object.keys(model.config.hydrologicalModel)[0],
  );

  document
    .getElementById("calibration__manual-config")
    .addEventListener("submit", runManual);
  document
    .getElementById("calibration__automatic-config")
    .addEventListener("submit", runAutomatic);
}

function addOptions(selectId, values) {
  const select = document.getElementById(selectId);
  values.forEach((val, i) => {
    const option = document.createElement("option");
    option.value = val;
    option.textContent = val;
    select.appendChild(option);
    if (i == 0) {
      select.value = val;
    }
  });
}


/**********/
/* update */
/**********/

function updateCatchment(catchment) {
  const info = model.config.catchments.filter((c) => c.name == catchment)[0];
  if (info === undefined) {
    addNotification(`There is no catchment named '${catchment}'.`, true)
  }

  if (info.snowAvailable) {
    document
      .querySelector("label[for='calibration__snow-model']")
      .classList.remove("label-disabled");
    document
      .getElementById("calibration__snow-model")
      .removeAttribute("disabled");
  } else {
    document
      .querySelector("label[for='calibration__snow-model']")
      .classList.add("label-disabled");
    document
      .getElementById("calibration__snow-model")
      .setAttribute("disabled", true);
  }

  const periodStart = document.getElementById("calibration__period-start");
  const periodEnd = document.getElementById("calibration__period-end");
  periodStart.setAttribute("min", info.periodMin);
  periodEnd.setAttribute("max", info.periodMax);
  if (periodStart.value == "" || periodStart.value < info.periodMin) { periodStart.value = info.periodMin; } if
    (periodEnd.value == "" || periodEnd.value > info.periodMax) {
    periodEnd.value = info.periodMax;
  }
}

function updateToPeriodStart() {
  const input = document.getElementById("calibration__period-start");
  input.value = input.min;
}

function updateToPeriodEnd() {
  const input = document.getElementById("calibration__period-end");
  input.value = input.max;
}

function updateManualCalibrationSettings(hydroModel) {
  const form = document.getElementById("calibration__manual-config");
  clear(form);

  const h3 = document.createElement("h3");
  h3.textContent = "Manual calibration settings";
  form.appendChild(h3);

  Object.entries(model.config.hydrologicalModel[hydroModel].parameters).forEach(
    ([param, config]) => {
      const label = document.createElement("label");
      label.setAttribute("for", `calibration__parameter-${param}`);
      label.textContent = `Parameter ${param}`;
      form.appendChild(label);

      const slider = createSlider(
        `calibration__parameter-${param}`,
        param,
        config.min,
        config.max,
        config.is_integer,
      );
      form.appendChild(slider);
    },
  );

  const loader = createLoading();
  loader.setAttribute("hidden", true);
  form.appendChild(loader);

  const run = document.createElement("input");
  run.setAttribute("type", "submit");
  run.value = "Run";
  form.appendChild(run);
}

function updateShownConfig(algorithm) {
  const manual = document.getElementById("calibration__manual-config");
  const automatic = document.getElementById("calibration__automatic-config");

  if (algorithm.toLowerCase() == "manual") {
    manual.removeAttribute("hidden");
    automatic.setAttribute("hidden", true);
  } else {
    manual.setAttribute("hidden", true);
    automatic.removeAttribute("hidden");
  }
}

async function runManual(event) {
  event.preventDefault();

  const loader = document.querySelector("#calibration__manual-config .loading");
  const submit = document.querySelector("#calibration__manual-config input[type='submit']");

  toggleLoading(true);
  loader.removeAttribute("hidden");
  submit.setAttribute("hidden", true);

  const fig = document.querySelector("#calibration .results__fig");

  const config = {
    hydrological_model: document.getElementById(
      "calibration__hydrological-model",
    ).value,
    catchment: document.getElementById("calibration__catchment").value,
    snow_model: document.getElementById("calibration__snow-model").value,
    objective_criteria: document.getElementById(
      "calibration__objective-criteria",
    ).value,
    streamflow_transformation: document.getElementById(
      "calibration__streamflow-transformation",
    ).value,
    calibration_start: document.getElementById("calibration__period-start")
      .value,
    calibration_end: document.getElementById("calibration__period-end").value,
    params: Object.fromEntries(
      [
        ...document.querySelectorAll(
          "#calibration__manual-config input[type='range']",
        ),
      ].map((input) => [input.name, parseFloat(input.value)]),
    ),
    prev_results: model.results,
  };
  const resp = await fetch("/calibration/run_manual", {
    method: "POST",
    body: JSON.stringify(config),
    headers: {
      "Content-type": "application/json",
    },
  });
  const data = await resp.json();
  const figData = JSON.parse(data.fig);
  model.results = data.results;

  clear(fig);
  Plotly.newPlot(fig, figData.data, figData.layout, {
    displayLogo: false,
    modeBarButtonsToRemove: [
      "zoom",
      "pan",
      "select",
      "lasso",
      "zoomIn",
      "zoomOut",
      "autoScale",
      "resetScale",
    ],
  });

  loader.setAttribute("hidden", true);
  submit.removeAttribute("hidden");
  document.querySelector(".results__export").removeAttribute("hidden");
  toggleLoading(false);

  fig.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function runAutomatic(event) {
  event.preventDefault();

  const fig = document.querySelector("#calibration .results__fig");
  const runButton = document.querySelector("#calibration__automatic-config input[type='submit']");
  const loadingSpinner = document.querySelector("#calibration__automatic-config .loading");

  runButton.setAttribute("hidden", true);
  loadingSpinner.removeAttribute("hidden");
  toggleLoading(true);

  const config = {
    hydrological_model: document.getElementById(
      "calibration__hydrological-model",
    ).value,
    catchment: document.getElementById("calibration__catchment").value,
    snow_model: document.getElementById("calibration__snow-model").value,
    objective_criteria: document.getElementById(
      "calibration__objective-criteria",
    ).value,
    streamflow_transformation: document.getElementById(
      "calibration__streamflow-transformation",
    ).value,
    calibration_start: document.getElementById("calibration__period-start")
      .value,
    calibration_end: document.getElementById("calibration__period-end").value,
    ngs: document.getElementById("calibration__ngs").value,
    npg: document.getElementById("calibration__npg").value,
    mings: document.getElementById("calibration__mings").value,
    nspl: document.getElementById("calibration__nspl").value,
    maxn: document.getElementById("calibration__maxn").value,
    kstop: document.getElementById("calibration__kstop").value,
    pcento: document.getElementById("calibration__pcento").value,
    peps: document.getElementById("calibration__peps").value,
  };

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(
    `${protocol}//${window.location.host}/calibration/run_automatic`,
  );

  ws.onopen = () => {
    ws.send(JSON.stringify(config));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "progress") {
      const figData = JSON.parse(data.fig);
      model.results = data.results;

      clear(fig);
      Plotly.newPlot(fig, figData.data, figData.layout, {
        displayLogo: false,
        modeBarButtonsToRemove: [
          "zoom",
          "pan",
          "select",
          "lasso",
          "zoomIn",
          "zoomOut",
          "autoScale",
          "resetScale",
        ],
      });

      if (data.iteration === 1) {
        fig.scrollIntoView({ behavior: "smooth", block: "end" });
      }

    } else if (data.type === "complete") {
      const figData = JSON.parse(data.fig);
      model.results = data.results;

      clear(fig);
      Plotly.newPlot(fig, figData.data, figData.layout, {
        displayLogo: false,
        modeBarButtonsToRemove: [
          "zoom",
          "pan",
          "select",
          "lasso",
          "zoomIn",
          "zoomOut",
          "autoScale",
          "resetScale",
        ],
      });

      loadingSpinner.setAttribute("hidden", true);
      runButton.removeAttribute("hidden");
      toggleLoading(false);

      document.querySelector(".results__export").removeAttribute("hidden");

      ws.close();
    } else if (data.type === "error") {
      addNotification(`Calibration error: ${data.message}`);

      loadingSpinner.setAttribute("hidden", true);
      runButton.removeAttribute("hidden");
      toggleLoading(false);

      ws.close();
    }
  };

  ws.onerror = (error) => {
    addNotification(`WebSocket error: ${error}`);

    loadingSpinner.setAttribute("hidden", true);
    runButton.removeAttribute("hidden");
    toggleLoading(false);
  };

}

function exportCalibrationResults() {
  if (!model.results) {
    alert("No calibration results to export. Please run a calibration first.");
    return;
  }

  // Gather all calibration settings and results
  const hydroModel = document.getElementById("calibration__hydrological-model").value;
  const catchment = document.getElementById("calibration__catchment").value;
  const snowModel = document.getElementById("calibration__snow-model").value;
  const criteria = document.getElementById("calibration__objective-criteria").value;
  const streamflowTransform = document.getElementById("calibration__streamflow-transformation").value;
  const algorithm = document.getElementById("calibration__algorithm").value;
  const dateStart = document.getElementById("calibration__period-start").value;
  const dateEnd = document.getElementById("calibration__period-end").value;
  const params = Object.entries(model.results.params).map(([key, vals]) => ({
    name: key,
    value: vals[vals.length - 1]
  }));


  // Create export data matching the format from the screenshot
  const exportData = {
    "hydrological model": hydroModel,
    "catchment": catchment,
    "criteria": criteria,
    "streamflow transformation": streamflowTransform,
    "algorithm": algorithm,
    "date start": dateStart,
    "date end": dateEnd,
    "warmup": true, // Default warm-up period
    "snow model": snowModel || "",
    "data type": "Observations",
    "parameters": params,
  };

  // Convert to JSON and download
  const jsonStr = JSON.stringify(exportData, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `calibration_${catchment}_${hydroModel}_${new Date().toISOString().split('T')[0]}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
