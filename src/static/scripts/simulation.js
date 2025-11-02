import { formatDate, clear, round } from "./utils.js";
import { addNotification } from "./header.js";
import "/static/assets/plotly-3.1.0.min.js";

/*********/
/* model */
/*********/

let model = {
  config: [],
  periodMin: null,
  periodMax: null,
};

/********/
/* init */
/********/

export async function init() {
  addEventListeners();
  await initView();
}

async function initView() {
}

function addEventListeners() {
  document.getElementById("simulation__import").addEventListener(
    "change", importCalibratedConfig
  )
  document
    .querySelector("label[for='simulation__period-start'] button")
    .addEventListener("click", updateToPeriodStart);
  document
    .querySelector("label[for='simulation__period-end'] button")
    .addEventListener("click", updateToPeriodEnd);
  document.getElementById("simulation__period").addEventListener("submit", runSimulation);
}


/**********/
/* update */
/**********/


function importCalibratedConfig(event) {
  const SIMULATION_KEYS = [
    "hydrological model",
    "catchment",
    "criteria",
    "streamflow transformation",
    "algorithm",
    "date start",
    "date end",
    "warmup",
    "snow model",
    "data type",
    "parameters",
  ];

  function updateConfig(event) {
    const table = document.getElementById("simulation__calibration-table");
    const configData = JSON.parse(event.target.result);
    model.config.push(configData);

    const div = document.createElement("div");
    const h4 = document.createElement("h4");
    h4.textContent = `Simulation ${model.config.length}`;
    div.appendChild(h4);

    SIMULATION_KEYS.forEach(key => {
      const val = configData[key];
      const span = document.createElement("span");
      if (typeof val === "object" && val !== null) {
        span.innerHTML = val.map(v => `${v.name}: ${round(v.value, 2)}`).join("<br />");
      } else {
        span.textContent = val ?? "";
      }
      div.appendChild(span);
    });

    table.appendChild(div);
    table.style.setProperty("--n-columns", model.config.length + 1);

    updateSimulationPeriodDefaults();
  }
  [...event.target.files].forEach(file => {
    const reader = new FileReader();
    reader.onload = updateConfig;
    reader.readAsText(file);
  });
  document.getElementById("simulation__period").removeAttribute("hidden");

}

async function updateSimulationPeriodDefaults() {
  const resp = await fetch("/calibration/config");
  if (!resp.ok) {
    addNotification(await resp.text(), true);
    return;
  }
  const config = await resp.json();
  const catchment = config.catchment.filter(catchment => catchment[0] ==
    model.config[model.config.length - 1].catchment).map(catchment =>
      ({ periodMin: new Date(catchment[2][0]), periodMax: new Date(catchment[2][1]) }))[0];
  model.periodMin = model.periodMin ? new Date(Math.max(catchment.periodMin, model.periodMin)) : catchment.periodMin;
  model.periodMax = model.periodMax ? new Date(Math.min(catchment.periodMax, model.periodMax)) : catchment.periodMax;

  const periodStart = document.getElementById("simulation__period-start");
  const periodEnd = document.getElementById("simulation__period-end");
  periodStart.setAttribute("min", model.periodMin);
  periodEnd.setAttribute("max", model.periodMax);

  if (periodStart.value == "" || periodStart.value < model.periodMin) {
    periodStart.value = formatDate(new
      Date(model.periodMax.getFullYear(), 0, 1));
  } if (periodEnd.value == "" || periodEnd.value >
    model.periodMax) {
    periodEnd.value = formatDate(model.periodMax);
  }
}

function updateToPeriodStart(event) {
  event.preventDefault();
  const input = document.getElementById("simulation__period-start");
  input.value = input.min;
}

function updateToPeriodEnd(event) {
  event.preventDefault();
  const input = document.getElementById("simulation__period-end");
  input.value = input.max;
}

async function runSimulation(event) {
  event.preventDefault();

  const theme = document.querySelector("body").classList.contains("light") ? "light" : "dark";

  const fig = document.querySelector("#simulation .results__fig");

  const config = model.config.map(
    config => ({
      hydrological_model: config["hydrological model"],
      catchment: config.catchment,
      snow_model: config["snow model"],
      params: config.parameters,
      simulation_start: document.getElementById("simulation__period-start").value,
      simulation_end: document.getElementById("simulation__period-end").value,
    })
  )
  const resp = await fetch("/simulation/run", {
    method: "POST",
    body: JSON.stringify({
      configs: config, multimodel: document.getElementById("simulation__multimodel").checked, theme:
        theme
    }),
    headers: {
      "Content-type": "application/json",
    },
  });
  if (!resp.ok) {
    addNotification(await resp.text(), true);
    return;
  }
  const data = await resp.json();
  const figData = JSON.parse(data.fig);

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
