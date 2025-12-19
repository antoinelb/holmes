import { onKey } from "./utils.js";

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
      button.addEventListener("click", event => changeApp(event.target.textContent.toLowerCase()))
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

export function addNotification(text, isError) {
  const notifications = document.getElementById("notifications");

  const notification = document.createElement("div");
  notification.classList.add("notification");
  notification.addEventListener("click", () => removeNotification(notification));
  if (isError) {
    notification.classList.add("error");
  }

  const textSpan = document.createElement("span");
  textSpan.textContent = text;
  notification.appendChild(textSpan);

  const progressBar = document.createElement("div");
  const progress = document.createElement("div");
  progressBar.appendChild(progress);
  notification.appendChild(progressBar);

  notifications.appendChild(notification);

  setTimeout(() => removeNotification(notification), 3000);

  return notification;
}

export function removeNotification(notification) {
  if (notification.parentNode !== null) {
    notification.parentNode.removeChild(notification);
  }
}

export function toggleLoading(loading) {
  if (loading) {
    document.querySelector("link[rel~='icon']").setAttribute("href", "/static/assets/loading.svg");
  } else {
    document.querySelector("link[rel~='icon']").setAttribute("href", "/static/assets/favicon.svg");
  }
}

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
  // Notify other modules that theme has changed
  window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
}

function changeApp(app) {
  const apps = document.querySelectorAll("main section");
  apps.forEach(
    app_ => {
      if (app_.querySelector("h2").textContent.toLowerCase() == app) {
        app_.removeAttribute("hidden");
      } else {
        app_.setAttribute("hidden", true);
      }
    }
  )
}
