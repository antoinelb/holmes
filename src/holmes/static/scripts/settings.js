import { create } from "./utils/elements.js";
import { onKey } from "./utils/listeners.js";
import { range } from "./utils/misc.js";

/*********/
/* model */
/*********/

export function initModel() {
  return {
    loading: false,
    open: false,
    theme: window.localStorage.getItem("holmes--settings--theme") ?? "dark",
    version: null,
  };
}

export const initialMsg = {
  type: "SettingsMsg",
  data: { type: "GetVersion" },
};

/**********/
/* update */
/**********/

export async function update(model, msg, dispatch) {
  dispatch = createDispatch(dispatch);
  switch (msg.type) {
    case "CheckEscape":
      const settingsCheckEl = document.getElementById("settings");
      if (
        msg.data.type === "click" &&
        settingsCheckEl?.contains(msg.data.target)
      ) {
        return model;
      } else {
        return { ...model, open: false };
      }
    case "GetVersion":
      getVersion(dispatch);
      return { ...model, loading: true };
    case "GotVersion":
      return { ...model, loading: false, version: msg.data };
    case "ToggleOpen":
      return { ...model, open: !model.open };
    case "ToggleTheme":
      const theme = model.theme === "dark" ? "light" : "dark";
      window.localStorage.setItem("holmes--settings--theme", theme);
      return { ...model, theme: theme };
    case "Reset":
      range(window.localStorage.length)
        .map((i) => window.localStorage.key(i))
        .filter((key) => key.substring(0, 6) === "holmes")
        .forEach((key) => {
          window.localStorage.removeItem(key);
        });
      window.location.reload();
      return model;
    default:
      return model;
  }
}

function createDispatch(dispatch) {
  return (msg) => dispatch({ type: "SettingsMsg", data: msg });
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
    dispatch({ type: "GotVersion", data: version });
  } catch (e) {
    clearTimeout(timeout);
    if (e.name === "AbortError") {
      console.error("Version fetch timed out");
    } else {
      console.error("Failed to fetch version:", e);
    }
    dispatch({ type: "GotVersion", data: "unknown" });
  }
}

/********/
/* view */
/********/

export function initView(dispatch) {
  dispatch = createDispatch(dispatch);
  document.addEventListener("keydown", (event) =>
    onKey(
      "T",
      async () =>
        await dispatch({
          type: "ToggleTheme",
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
              type: "ToggleOpen",
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
                type: "ToggleTheme",
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
                type: "Reset",
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

export function view(model, dispatch) {
  dispatch = createDispatch(dispatch);

  const settingsEl = document.getElementById("settings");
  if (settingsEl) {
    if (model.open) {
      settingsEl.classList.add("settings--open");
    } else {
      settingsEl.classList.remove("settings--open");
    }
  }

  if (model.theme === "dark") {
    document.body.classList.remove("light");
  } else {
    document.body.classList.add("light");
  }

  const versionSpan = document.querySelector("#version span:last-child");
  if (versionSpan && versionSpan.textContent !== model.version) {
    versionSpan.textContent = model.version;
  }
}
