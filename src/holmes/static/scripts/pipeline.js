import { create, createIcon } from "./utils/elements.js";
import { t } from "./utils/text.js";

import * as stations from "./steps/stations.js";
import * as weather from "./steps/weather.js";
import * as model_ from "./steps/model.js";
import * as calibration from "./steps/calibration.js";
import * as simulation from "./steps/simulation.js";
import * as projection from "./steps/projection.js";

/*********/
/* steps */
/*********/

// each step declares which config keys it consumes (uses) and sets (provides);
// unlocking and staleness are derived from these, never hand-written per step
export const steps = [
  {
    id: "stations",
    label: t("Stations", "Stations"),
    icon: "map-pin",
    map: true,
    uses: [],
    provides: [
      "calibrationStation",
      "simulationStation",
      "calibrationPeriod",
      "simulationPeriod",
    ],
    module: stations,
  },
  {
    id: "weather",
    label: t("Weather", "Météo"),
    icon: "cloud-rain",
    map: true,
    uses: [
      "calibrationStation",
      "simulationStation",
      "calibrationPeriod",
      "simulationPeriod",
    ],
    provides: ["weatherMethod", "weatherNStations"],
    module: weather,
  },
  {
    id: "model",
    label: t("Model", "Modèle"),
    icon: "box",
    uses: [],
    provides: ["hydroModels", "snowModel"],
    module: model_,
  },
  {
    id: "calibration",
    label: t("Calibration", "Calage"),
    icon: "sliders",
    uses: [
      "calibrationStation",
      "calibrationPeriod",
      "weatherMethod",
      "weatherNStations",
      "hydroModels",
      "snowModel",
    ],
    provides: ["params"],
    module: calibration,
  },
  {
    id: "simulation",
    label: t("Simulation", "Simulation"),
    icon: "activity",
    uses: [
      "simulationStation",
      "simulationPeriod",
      "weatherMethod",
      "weatherNStations",
      "hydroModels",
      "snowModel",
      "params",
    ],
    provides: [],
    module: simulation,
  },
  {
    id: "projection",
    label: t("Projection", "Projection"),
    icon: "trending-up",
    uses: [
      "simulationStation",
      // the historical reference simulates the observed weather over the
      // simulation period, so the step goes stale when the period moves
      "simulationPeriod",
      "weatherMethod",
      "weatherNStations",
      "hydroModels",
      "snowModel",
      "params",
    ],
    provides: [],
    module: projection,
  },
];

export const stepById = Object.fromEntries(
  steps.map((step) => [step.id, step]),
);

/**********/
/* engine */
/**********/

export function status(model, stepId) {
  const step = stepById[stepId];
  if (step.uses.some((key) => !isFilled(model.config[key]))) {
    return "locked";
  }
  const snapshot = model.snapshots[stepId];
  if (snapshot === undefined) {
    return "available";
  }
  const provided = step.provides.every((key) => isFilled(model.config[key]));
  if (provided && sameSnapshot(snapshot, pick(model.config, step.uses))) {
    return "done";
  }
  return "stale";
}

// a step completes itself the moment every config key it provides is filled;
// per-field validation happens in the step views before SetConfig is sent
export function autoComplete(model) {
  const step = stepById[model.step];
  if (
    step.provides.length === 0 ||
    step.provides.some((key) => !isFilled(model.config[key]))
  ) {
    return model;
  }
  return {
    ...model,
    snapshots: {
      ...model.snapshots,
      [step.id]: pick(model.config, step.uses),
    },
  };
}

// for steps whose work finishes asynchronously: autoComplete only fires on
// SetConfig, so a step made stale by an upstream change stays stale until its
// data comes back
export function complete(model, stepId) {
  return {
    ...model,
    snapshots: {
      ...model.snapshots,
      [stepId]: pick(model.config, stepById[stepId].uses),
    },
  };
}

function sameSnapshot(snapshot, current) {
  return JSON.stringify(snapshot) === JSON.stringify(current);
}

// a config key counts as filled when it holds a value; array-valued keys
// (e.g. hydroModels) are empty, not filled, when they hold no entries, so an
// empty selection never reads as provided or unlocks a downstream step
function isFilled(value) {
  return Array.isArray(value) ? value.length > 0 : value !== null;
}

function pick(config, keys) {
  return Object.fromEntries(keys.map((key) => [key, config[key]]));
}

/********/
/* view */
/********/

export function sidebarView(model, dispatch) {
  const sidebar = document.getElementById("sidebar");
  // entries are built once and reconciled in place: replacing them under a
  // click (e.g. the blur -> SetConfig -> status change sequence) swallows it
  if (sidebar.children.length === 0) {
    steps.forEach((step) => {
      sidebar.appendChild(
        create(
          "button",
          { class: "pipeline__step", title: step.label, "data-step": step.id },
          [createIcon(step.icon)],
          [
            {
              event: "click",
              fct: () => dispatch({ type: "SelectStep", data: step.id }),
            },
          ],
        ),
      );
    });
  }
  steps.forEach((step, i) => {
    const stepStatus = status(model, step.id);
    sidebar.children[i].className = [
      "pipeline__step",
      `pipeline__step--${stepStatus}`,
      ...(step.id === model.step ? ["pipeline__step--current"] : []),
    ].join(" ");
  });
}
