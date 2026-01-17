import { create } from "./utils/elements.js";
import { checkEscape } from "./utils/listeners.js";

import * as notifications from "./notifications.js";
import * as settings from "./settings.js";
import * as nav from "./nav.js";
import * as calibration from "./calibration.js";
import * as simulation from "./simulation.js";
import * as projection from "./projection.js";

// Global error handlers
window.onerror = (message, source, lineno, colno, error) => {
  console.error("Uncaught error:", { message, source, lineno, colno, error });
  return false; // Let default handler also run
};

window.onunhandledrejection = (event) => {
  console.error("Unhandled promise rejection:", event.reason);
};

/*********/
/* model */
/*********/

function initModel() {
  const canSave =
    (window.localStorage.getItem("holmes--can-save") ?? "true") === "true";
  return {
    preventEscape: false,
    loading: false,
    canSave: canSave,
    page: canSave
      ? (window.localStorage.getItem("holmes--page") ?? "calibration")
      : "calibration",
    notifications: notifications.initModel(),
    settings: settings.initModel(canSave),
    nav: nav.initModel(),
    calibration: calibration.initModel(canSave),
    simulation: simulation.initModel(canSave),
    projection: projection.initModel(canSave),
  };
}

const initialMsg = null;

/**********/
/* update */
/**********/

async function update(model, msg, dispatch) {
  const createNotification = (text, isError) => {
    dispatch({
      type: "NotificationsMsg",
      data: { type: "AddNotification", data: { text: text, isError: isError } },
    });
  };
  switch (msg.type) {
    case "CheckEscape":
      dispathCheckEscape(model, msg.data, dispatch);
      return model;
    case "SetPreventEscape":
      setTimeout(() => {
        dispatch({ type: "UnsetPreventEscape" });
      });
      return { ...model, preventEscape: true };
    case "UnsetPreventEscape":
      return { ...model, preventEscape: false };
    case "ToggleCanSave":
      window.localStorage.setItem("holmes--can-save", !model.canSave);
      return { ...model, canSave: !model.canSave };
    case "Navigate":
      window.localStorage.setItem("holmes--page", msg.data);
      return { ...model, page: msg.data };
    case "NotificationsMsg":
      return {
        ...model,
        notifications: await notifications.update(
          model.notifications,
          msg.data,
          dispatch,
        ),
      };
    case "SettingsMsg":
      return {
        ...model,
        settings: await settings.update(model.settings, msg.data, dispatch),
      };
    case "NavMsg":
      return {
        ...model,
        nav: await nav.update(model.nav, msg.data, dispatch),
      };
    case "CalibrationMsg":
      return {
        ...model,
        calibration: await calibration.update(
          model.calibration,
          msg.data,
          dispatch,
          createNotification,
        ),
      };
    case "SimulationMsg":
      return {
        ...model,
        simulation: await simulation.update(
          model.simulation,
          msg.data,
          dispatch,
          createNotification,
        ),
      };
    case "ProjectionMsg":
      return {
        ...model,
        projection: await projection.update(
          model.projection,
          msg.data,
          dispatch,
          createNotification,
        ),
      };
    default:
      return model;
  }
}

function dispathCheckEscape(model, event, dispatch) {
  if (checkEscape(model, event, dispatch)) {
    [
      "NotificationsMsg",
      "SettingsMsg",
      "NavMsg",
      "CalibrationMsg",
      "SimulationMsg",
      "ProjectionMsg",
    ].forEach((msg) => {
      dispatch({ type: msg, data: { type: "CheckEscape", data: event } });
    });
  }
}

/********/
/* view */
/********/

async function initView(model, dispatch) {
  await injectSvgSprite();
  document.body.append(notifications.initView(dispatch));
  document.body.append(
    create("header", {}, [
      create("h1", {}, "HOLMES"),
      settings.initView(dispatch),
      nav.initView(dispatch),
    ]),
  );
  document.body.append(
    create("main", {}, [
      calibration.initView(dispatch),
      simulation.initView(dispatch),
      projection.initView(dispatch),
    ]),
  );
  document.body.addEventListener("click", (event) =>
    dispatch({ type: "CheckEscape", data: event }),
  );
  document.body.addEventListener("keydown", (event) =>
    dispatch({ type: "CheckEscape", data: event }),
  );
  loadingView(model);
}

async function injectSvgSprite() {
  if (!document.getElementById("svg-sprite")) {
    try {
      const resp = await fetch("/static/assets/icons/icons.svg");
      if (!resp.ok) {
        console.error("Failed to load SVG sprite:", resp.status);
        return;
      }
      const sprite = await resp.text();
      document.body.insertAdjacentHTML("beforebegin", sprite);
    } catch (e) {
      console.error("Failed to inject SVG sprite:", e);
    }
  }
}

function view(msg, model, dispatch) {
  loadingView(model);
  pageView(model);
  switch (msg.type) {
    case "NotificationsMsg":
      notifications.view(model.notifications, dispatch);
      break;
    case "SettingsMsg":
      settings.view(model.settings, dispatch, model.canSave);
      break;
    case "NavMsg":
      nav.view(model.nav, dispatch);
      break;
    case "CalibrationMsg":
      calibration.view(model.calibration, dispatch);
      break;
    case "SimulationMsg":
      simulation.view(model.simulation, dispatch);
      break;
    case "ProjectionMsg":
      projection.view(model.projection, dispatch);
      break;
  }
}

function loadingView(model) {
  const loading =
    model.loading ||
    model.settings.loading ||
    model.nav.loading ||
    model.calibration.loading ||
    model.simulation.loading ||
    model.projection.loading;

  const faviconLink = document.querySelector("link[rel~='icon']");
  if (!faviconLink) return;

  if (loading) {
    if (!faviconLink.href.endsWith("/loading.svg")) {
      faviconLink.href = "/static/assets/icons/loading.svg";
    }
  } else {
    if (!faviconLink.href.endsWith("/favicon.svg")) {
      faviconLink.href = "/static/assets/icons/favicon.svg";
    }
  }
}

function pageView(model) {
  [...document.querySelectorAll("section")].forEach((section) => {
    if (section.id === model.page) {
      section.removeAttribute("hidden");
    } else {
      section.setAttribute("hidden", true);
    }
  });
}

/********/
/* init */
/********/

async function init() {
  let queue = [];
  let processing = false;

  let model = initModel();

  const processQueue = async () => {
    processing = true;
    while (queue.length > 0) {
      const msg = queue.shift();
      model = await update(model, msg, dispatch);
      // console.log(msg, model);
      view(msg, model, dispatch);
    }
    processing = false;
  };

  const dispatch = async (msg) => {
    queue.push(msg);
    if (!processing) {
      processQueue();
    }
  };

  await initView(model, dispatch);
  [
    initialMsg,
    notifications.initialMsg,
    settings.initialMsg,
    nav.initialMsg,
    calibration.initialMsg,
    simulation.initialMsg,
    projection.initialMsg,
  ].forEach((msg) => {
    if (msg) {
      if (Array.isArray(msg)) {
        msg.forEach((_msg) => {
          dispatch(_msg);
        });
      } else {
        dispatch(msg);
      }
    }
  });
}

window.addEventListener("load", init);
