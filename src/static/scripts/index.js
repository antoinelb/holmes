"use strict";

import * as header from "./header.js";
import * as calibration from "./calibration.js";
import * as simulation from "./simulation.js";
import * as projection from "./projection.js";

async function init() {
  await header.init();
  await calibration.init();
  await simulation.init();
  await projection.init();
  await precompileFunctions();
  calibration.allowRunning();
}

async function precompileFunctions() {
  await fetch("/precompile");
}


window.addEventListener("load", init);
