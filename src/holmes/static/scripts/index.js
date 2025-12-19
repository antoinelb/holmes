"use strict";

import * as header from "./header.js";
import * as calibration from "./calibration.js";
import * as simulation from "./simulation.js";
import * as projection from "./projection.js";

async function init() {
  await header.init();
  await precompileFunctions();
  await calibration.init();
  await simulation.init();
  await projection.init();
}

async function precompileFunctions() {
  const notification = header.addNotification("Started precompiling...");
  await fetch("/precompile");
  header.toggleLoading(false);
  document.getElementById("calibration").removeAttribute("hidden");
  document.querySelector("main > .loading").setAttribute("hidden", true);
  header.removeNotification(notification);
}


window.addEventListener("load", init);
