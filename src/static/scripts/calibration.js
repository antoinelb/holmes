import { clear, createSlider, createLoading } from "./utils.js";
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

export function allowRunning() {
  model.runAllowed = true;
  [...document.querySelectorAll(".loading")].forEach(elem => elem.setAttribute("hidden", true));

  document.querySelector("#calibration__manual-config input[type='submit']").removeAttribute("hidden");
  document.querySelector("#calibration__automatic-config input[type='submit']").removeAttribute("hidden");
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
    console.error(`There is no catchment named '${catchment}'.`);
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

  form.appendChild(createLoading());

  const run = document.createElement("input");
  run.setAttribute("type", "submit");
  run.setAttribute("hidden", true);
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
  const start = performance.now();
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

  document.querySelector("#calibration .results__time span:last-child").textContent = `${(performance.now() - start) /
    1000}
  s`;

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

  fig.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function runAutomatic(event) {
  event.preventDefault();

  const fig = document.querySelector("#calibration .results__fig");
  const runButton = document.querySelector("#calibration__automatic-config input[type='submit']");
  const loadingSpinner = document.querySelector("#calibration__automatic-config .loading");
  const statusMessage = document.querySelector("#calibration__automatic-config .status-message");

  // Hide Run button, show loading and status
  runButton.setAttribute("hidden", true);
  loadingSpinner.removeAttribute("hidden");
  statusMessage.removeAttribute("hidden");
  statusMessage.textContent = "Calibration started...";

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

  // Create WebSocket connection
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(
    `${protocol}//${window.location.host}/calibration/run_automatic_ws`,
  );

  const start = performance.now();

  ws.onopen = () => {
    // Send configuration
    ws.send(JSON.stringify(config));
    statusMessage.textContent = "Calibration in progress...";
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "progress") {
      // Update progress display
      updateProgress(data);

      // Render plot with current progress
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
      fig.scrollIntoView({ behavior: "smooth", block: "end" });

    } else if (data.type === "complete") {
      // Render final plot
      const figData = JSON.parse(data.fig);
      model.results = data.results;

      const duration = (performance.now() - start) / 1000;
      document.querySelector("#calibration .results__time span:last-child").textContent = `${duration} s`;

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

      // Update UI state - calibration completed
      loadingSpinner.setAttribute("hidden", true);
      statusMessage.textContent = `Calibration completed in ${duration.toFixed(1)} s`;
      runButton.removeAttribute("hidden");

      fig.scrollIntoView({ behavior: "smooth", block: "end" });
      ws.close();
    } else if (data.type === "error") {
      console.error("Calibration error:", data.message);

      // Update UI state - error occurred
      loadingSpinner.setAttribute("hidden", true);
      statusMessage.textContent = `Error: ${data.message}`;
      runButton.removeAttribute("hidden");

      ws.close();
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);

    // Update UI state - connection error
    loadingSpinner.setAttribute("hidden", true);
    statusMessage.textContent = "Connection error occurred";
    runButton.removeAttribute("hidden");
  };

  ws.onclose = () => {
    console.log("WebSocket connection closed");
  };
}

function updateProgress(data) {
  // Display progress in console (could be updated to show in UI)
  console.log(
    `Iteration ${data.iteration}: evaluations=${data.evaluations}, ` +
    `best_objective=${data.best_objective.toFixed(4)}, ` +
    `gnrng=${data.gnrng.toFixed(6)}, ` +
    `percent_change=${data.percent_change.toFixed(6)}`,
  );
}
