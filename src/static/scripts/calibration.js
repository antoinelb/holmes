/*********/
/* model */
/*********/

let model = {
  hydrologicalModel: [],
  catchments: [],
  snowModel: [],
  objectiveCriteria: [],
  objectiveStreamflow: [],
  algorithm: [],
}


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
  document.getElementById("calibration__general-config").addEventListener("submit", event => { event.preventDefault(); })
  document.getElementById("calibration__catchment").addEventListener("change", event => {
    updateCatchment(event.target.value);
  });
  document.querySelector("label[for='calibration__period-start'] button").addEventListener(
    "click", updateToPeriodStart
  );
  document.querySelector("label[for='calibration__period-end'] button").addEventListener(
    "click", updateToPeriodEnd
  );
}

async function initAvailableConfig() {
  const resp = await fetch("/calibration/config");
  const config = await resp.json();
  model = {
    hydrologicalModel: config.hydrological_model,
    catchments: config.catchment.map(catchment => ({
      name: catchment[0],
      snowAvailable: catchment[1],
      periodMin: catchment[2][0],
      periodMax: catchment[2][1],
    })),
    snowModel: config.snow_model,
    objectiveCriteria: config.objective_criteria,
    objectiveStreamflow: config.objective_streamflow,
    algorithm: config.algorithm,
  }

  addOptions("calibration__hydrological-model", model.hydrologicalModel);
  addOptions("calibration__catchment", model.catchments.map(catchment => catchment.name));
  addOptions("calibration__snow-model", model.snowModel);
  addOptions("calibration__objective-criteria", model.objectiveCriteria);
  addOptions("calibration__objective-streamflow", model.objectiveStreamflow);
  addOptions("calibration__algorithm", model.algorithm);

  // updateCatchment("Au Saumon");
  updateCatchment(model.catchments[0].name);

}

function addOptions(selectId, values) {
  const select = document.getElementById(selectId);
  values.forEach(
    (val, i) => {
      const option = document.createElement("option");
      option.value = val;
      option.textContent = val;
      select.appendChild(option);
      if (i == 0) {
        select.value = val;
      }
    }
  )

}

/**********/
/* update */
/**********/

function updateCatchment(catchment) {
  const info = model.catchments.filter(c => c.name == catchment)[0];
  if (info === undefined) {
    console.error(`There is no catchment named '${catchment}'.`)
  }

  if (info.snowAvailable) {
    document.querySelector("label[for='calibration__snow-model']").classList.remove("label-disabled");
    document.getElementById("calibration__snow-model").removeAttribute("disabled");
  } else {
    document.querySelector("label[for='calibration__snow-model']").classList.add("label-disabled");
    document.getElementById("calibration__snow-model").setAttribute("disabled", true);
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
