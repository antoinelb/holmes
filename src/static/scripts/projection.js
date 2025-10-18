import { clear, round, equals } from "./utils.js";
import { addNotification } from "./header.js";
import "/static/assets/plotly-3.1.0.min.js";

/*********/
/* model */
/*********/

let model = {
  config: [],
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

  let configs = await readConfigFiles(event.target.files);

  const uniqueCatchments = new Set([...model.config.map(c => c.catchment), ...configs.map(c => c.catchment)]);
  if (uniqueCatchments.size > 1) {
    addNotification("All calibration configurations must be for the same catchment.", true);
    return;
  }

  configs = configs.filter(config => !model.config.some(c => equals(config, c)));

  const table = document.getElementById("projection__calibration-table");

  configs.forEach(configData => {
    model.config.push(configData);

    const div = document.createElement("div");
    const h4 = document.createElement("h4");
    h4.textContent = `Projection ${model.config.length}`;
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
  });

  table.style.setProperty("--n-columns", model.config.length + 1);

  await updateCatchment(model.config[0].catchment);
}

async function readConfigFiles(files) {
  const filePromises = [...files].map(file => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(JSON.parse(e.target.result));
      reader.onerror = reject;
      reader.readAsText(file);
    });
  });
  return await Promise.all(filePromises);
}

async function updateCatchment(catchment) {
  const resp = await fetch(`/projection/config?catchment=${catchment}`);
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

  const fig = document.querySelector("#projection .results__fig");

  const config = model.config.map(
    config => ({
      hydrological_model: config["hydrological model"],
      catchment: config.catchment,
      snow_model: config["snow model"],
      params: config.parameters,
      date_start: config["date start"],
      date_end: config["date end"],
    })
  )

  const resp = await fetch("/projection/run", {
    method: "POST",
    body: JSON.stringify({
      configs: config,
      climate_model: document.getElementById("projection__model").value,
      climate_scenario: document.getElementById("projection__scenario").value,
      horizon: document.getElementById("projection__horizon").value,
      multimodel: document.getElementById("projection__multimodel").checked
    }),
    headers: {
      "Content-type": "application/json",
    },
  });
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
