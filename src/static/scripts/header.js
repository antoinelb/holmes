import { onKey } from "./utils.js";
import * as main from "./main.js";

/********/
/* init */
/********/

export async function init() {
  addEventListeners();
  await initView();
}

async function initView() {
  initTheme();
  await initVersion();
}

function addEventListeners() {
  document.getElementById("nav").addEventListener("click", toggleNav)
  document.querySelectorAll("nav button").forEach(
    button => {
      button.addEventListener("click", event => main.changeApp(event.target.textContent.toLowerCase()))
    }
  );
  document.getElementById("settings").addEventListener("click", toggleSettings)
  document.getElementById("theme").addEventListener("click", toggleTheme)

  document.addEventListener("keydown", (event) =>
    onKey(
      "N",
      toggleNav,
      event,
    ),
  );
  document.addEventListener("keydown", (event) =>
    onKey(
      "S",
      toggleSettings,
      event,
    ),
  );
  document.addEventListener("keydown", (event) =>
    onKey(
      "T",
      toggleTheme,
      event,
    ),
  );
}

function initTheme() {
  const theme = localStorage.getItem("theme") || "dark";
  if (theme == "dark") {
    document.body.classList.remove("light");
  } else {
    document.body.classList.add("light");
  }
}

async function initVersion() {
  const resp = await fetch("/version");
  const version = await resp.text();
  document.querySelector("#version span:last-child").textContent = version;
}

/**********/
/* update */
/**********/

function toggleNav() {
  const nav = document.getElementById("nav");
  if (nav.classList.contains("nav--open")) {
    nav.classList.remove("nav--open");
  } else {
    nav.classList.add("nav--open");
  }
}

function toggleSettings() {
  const settings = document.getElementById("settings");
  if (settings.classList.contains("settings--open")) {
    settings.classList.remove("settings--open");
  } else {
    settings.classList.add("settings--open");
  }
}

function toggleTheme() {
  let theme = "";
  if (document.body.classList.contains("light")) {
    document.body.classList.remove("light");
    theme = "dark";
  } else {
    document.body.classList.add("light");
    theme = "light";
  }
  localStorage.setItem("theme", theme);
}
