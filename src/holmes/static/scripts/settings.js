import { create } from "./utils/elements.js";
import { onKey } from "./utils/listeners.js";
import { range } from "./utils/misc.js";

/*********/
/* model */
/*********/

export function initSettings() {
  return {
    loading: false,
    open: false,
    theme: window.localStorage.getItem("holmes--settings--theme") ?? "dark",
    version: null,
  };
}

/**********/
/* update */
/**********/

export function update(model, msg, dispatch) {
  switch (msg.type) {
    case "settings/ToggleOpen":
      return {
        ...model,
        settings: { ...model.settings, open: !model.settings.open },
      };
    case "settings/ToggleTheme":
      return toggleTheme(model);
    case "settings/GetVersion":
      getVersion(dispatch);
      return { ...model, settings: { ...model.settings, loading: true } };
    case "settings/GotVersion":
      return {
        ...model,
        settings: { ...model.settings, loading: false, version: msg.data },
      };
    case "settings/ResetAll":
      resetAll();
      return model;
    default:
      return model;
  }
}

export function closeOnEscape(model, event) {
  const settingsDiv = document.getElementById("settings");
  if (event.type === "click" && settingsDiv?.contains(event.target)) {
    return model;
  }
  return { ...model, open: false };
}

function toggleTheme(model) {
  const theme = model.settings.theme === "dark" ? "light" : "dark";
  window.localStorage.setItem("holmes--settings--theme", theme);
  return { ...model, settings: { ...model.settings, theme: theme } };
}

function resetAll() {
  range(window.localStorage.length)
    .map((i) => window.localStorage.key(i))
    .filter((key) => key.substring(0, 6) === "holmes")
    .forEach((key) => {
      window.localStorage.removeItem(key);
    });
  window.location.reload();
}

async function getVersion(dispatch) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const resp = await fetch("/version", { signal: controller.signal });
    clearTimeout(timeout);
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const version = await resp.text();
    dispatch({ type: "settings/GotVersion", data: version });
  } catch (e) {
    clearTimeout(timeout);
    if (e.name === "AbortError") {
      console.error("Version fetch timed out");
    } else {
      console.error("Failed to fetch version:", e);
    }
    dispatch({ type: "settings/GotVersion", data: "unknown" });
  }
}

/********/
/* view */
/********/

export function initSettingsView(dispatch) {
  document.addEventListener("keydown", (event) =>
    onKey(
      "T",
      async () =>
        await dispatch({
          type: "settings/ToggleTheme",
        }),
      event,
    ),
  );
  return create("div", { id: "settings" }, [
    create(
      "button",
      { title: "Toggle settings" },
      [
        create("svg", { class: "icon" }, [
          create("use", { href: "#icon-menu" }),
        ]),
      ],
      [
        {
          event: "click",
          fct: () =>
            dispatch({
              type: "settings/ToggleOpen",
            }),
        },
      ],
    ),
    create("div", {}, [
      create(
        "button",
        { id: "theme" },
        [
          create("svg", { id: "theme__moon", class: "icon" }, [
            create("use", { href: "#icon-moon" }),
          ]),
          create("svg", { id: "theme__sun", class: "icon" }, [
            create("use", { href: "#icon-sun" }),
          ]),
          create("span", {}, ["Toggle theme"]),
          create("span", { class: "hotkey" }, ["T"]),
        ],
        [
          {
            event: "click",
            fct: async () =>
              await dispatch({
                type: "settings/ToggleTheme",
              }),
          },
        ],
      ),
      create(
        "button",
        { id: "reset" },
        [
          create("svg", { class: "icon" }, [
            create("use", { href: "#icon-refresh-cw" }),
          ]),
          create("span", {}, ["Reset all"]),
        ],
        [
          {
            event: "click",
            fct: async () =>
              await dispatch({
                type: "settings/ResetAll",
              }),
          },
        ],
      ),
      create("div", { id: "version" }, [
        create("span", {}, ["Version: "]),
        create("span"),
      ]),
    ]),
  ]);
}

export function settingsView(model) {
  const settingsEl = document.getElementById("settings");
  if (settingsEl) {
    if (model.settings.open) {
      settingsEl.classList.add("settings--open");
    } else {
      settingsEl.classList.remove("settings--open");
    }
  }

  if (model.settings.theme === "dark") {
    document.body.classList.remove("light");
  } else {
    document.body.classList.add("light");
  }

  const versionSpan = document.querySelector("#version span:last-child");
  if (versionSpan && versionSpan.textContent !== model.settings.version) {
    versionSpan.textContent = model.settings.version;
  }
}
