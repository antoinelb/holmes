"use strict";

import * as header from "./header.js";

async function init() {
  await header.init();
}


window.addEventListener("load", init);
