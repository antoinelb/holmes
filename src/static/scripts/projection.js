import { clear, round } from "./utils.js";
import { toggleLoading, addNotification } from "./header.js";
import "/static/assets/plotly-3.1.0.min.js";

/*********/
/* model */
/*********/

let model = {
  config: null,
  settings: {},
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
  document.getElementById("projection__import").addEventListener(
    "change", importCalibratedConfig
  )
  document.getElementById("projection__config").addEventListener("submit", runProjection);
}


/**********/
/* update */
/**********/


async function importCalibratedConfig(event) {
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

  const config = await readConfigFile(event.target.files[0])
  const catchmentOk = await updateCatchment(config.catchment);
  if (!catchmentOk) {
    return;
  }
  model.config = config;

  const table = document.getElementById("projection__calibration-table");

  const div = table.children.length == 1 ? document.createElement("div") : table.getElementsByTagName("div")[1];
  clear(div);

  SIMULATION_KEYS.forEach(key => {
    const val = model.config[key];
    const span = document.createElement("span");
    if (typeof val === "object" && val !== null) {
      span.innerHTML = val.map(v => `${v.name}: ${round(v.value, 2)}`).join("<br />");
    } else {
      span.textContent = val ?? "";
    }
    div.appendChild(span);
  });

  table.appendChild(div);

  table.style.setProperty("--n-columns", 2);

  document.getElementById("projection__config").removeAttribute("hidden");
}

async function readConfigFile(file) {
  const promise = new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(JSON.parse(e.target.result));
    reader.onerror = reject;
    reader.readAsText(file);
  });
  return await promise
}

async function updateCatchment(catchment) {
  const resp = await fetch(`/projection/config?catchment=${catchment}`);
  if (!resp.ok) {
    addNotification(await resp.text(), true);
    return false;
  }
  model.settings = await resp.json();

  const climateModels = [...Object.keys(model.settings)].sort((a, b) => a > b)

  const select = document.getElementById("projection__model");
  clear(select);

  climateModels.forEach(
    (m, i) => {
      const option = document.createElement("option");
      option.value = m;
      option.textContent = m;
      option.selected = i === 0;
      select.appendChild(option);
    }
  );

  select.addEventListener("change", event => updateHorizons(event.target.value));

  updateHorizons(climateModels[0]);

  return true;
}

function updateHorizons(climateModel) {
  const horizons = model.settings[climateModel];
  const select = document.getElementById("projection__horizon");
  clear(select);
  horizons.forEach((h, i) => {
    const option = document.createElement("option");
    option.value = h;
    option.textContent = h;
    option.selected = i === 0;
    select.appendChild(option);
  })


}

async function runProjection(event) {
  event.preventDefault();

  const theme = document.querySelector("body").classList.contains("light") ? "light" : "dark";

  const loader = document.querySelector("#projection__config .loading");
  const submit = document.querySelector("#projection__config input[type='submit']");

  toggleLoading(true);
  loader.removeAttribute("hidden");
  submit.setAttribute("hidden", true);

  const fig = document.querySelector("#projection .results__fig");

  const resp = await fetch("/projection/run", {
    method: "POST",
    body: JSON.stringify({
      hydrological_model: model.config["hydrological model"],
      catchment: model.config.catchment,
      snow_model: model.config["snow model"],
      params: model.config.parameters,
      climate_model: document.getElementById("projection__model").value,
      climate_scenario: document.getElementById("projection__scenario").value,
      horizon: document.getElementById("projection__horizon").value,
      theme: theme,
    }),
    headers: {
      "Content-type": "application/json",
    },
  });
  if (!resp.ok) {
    addNotification(await resp.text(), true);
    loader.setAttribute("hidden", true);
    submit.removeAttribute("hidden");
    toggleLoading(false);
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

  loader.setAttribute("hidden", true);
  submit.removeAttribute("hidden");
  toggleLoading(false);
}
