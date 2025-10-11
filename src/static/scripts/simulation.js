import { formatDate, range } from "./utils.js";
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
  function updateConfig(event) {
    const table = document.getElementById("simulation__calibration-table");
    model.config.push(JSON.parse(event.target.result));
    const div = document.createElement("div");
    div.style.setProperty("--column", model.config.length + 1);
    table.appendChild(div);

    function addSpan(key) {
      const val = model.config[model.config.length - 1][key];
      const span = document.createElement("span");
      if (typeof val === "object") {
        span.innerHTML = val.map(v => `${v.name}: ${v.value}`).join("<br />");
      } else {
        span.textContent = val;
      }
      div.appendChild(span);
    }

    table.style.setProperty("--n-columns", model.config.length + 1);

    [...table.querySelectorAll("div:first-of-type span")].forEach(span => { addSpan(span.textContent) });

    updateSimulationPeriodDefaults();
  }
  [...event.target.files].forEach(file => {
    const reader = new FileReader();
    reader.onload = updateConfig;
    reader.readAsText(file);
  });

}

async function updateSimulationPeriodDefaults() {
  const resp = await fetch("/calibration/config");
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
}
