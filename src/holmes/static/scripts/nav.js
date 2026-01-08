import { create } from "./utils/elements.js";

/*********/
/* model */
/*********/

export function initModel() {
  return {
    loading: false,
    open: false,
  };
}

export const initialMsg = null;

/**********/
/* update */
/**********/

export async function update(model, msg, dispatch) {
  dispatch = createDispatch(dispatch);
  switch (msg.type) {
    case "CheckEscape":
      if (
        msg.data.type === "click" &&
        document.getElementById("nav").contains(msg.data.target)
      ) {
        return model;
      } else {
        return { ...model, open: false };
      }
    case "ToggleOpen":
      return { ...model, open: !model.open };
    default:
      return model;
  }
}

function createDispatch(dispatch) {
  return (msg) => dispatch({ type: "NavMsg", data: msg });
}

/********/
/* view */
/********/

export function initView(dispatch) {
  const globalDispatch = dispatch;
  dispatch = createDispatch(dispatch);
  return create("div", { id: "nav" }, [
    create(
      "button",
      { title: "Toggle navigation" },
      [
        create("svg", { class: "icon" }, [
          create("use", { href: "#icon-grid" }),
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
    create("nav", {}, [
      create(
        "button",
        {},
        ["Calibration"],
        [
          {
            event: "click",
            fct: async () => {
              await dispatch({ type: "ToggleOpen" });
              await globalDispatch({
                type: "Navigate",
                data: "calibration",
              });
            },
          },
        ],
      ),
      create(
        "button",
        {},
        ["Simulation"],
        [
          {
            event: "click",
            fct: async () => {
              await dispatch({ type: "ToggleOpen" });
              await globalDispatch({
                type: "Navigate",
                data: "simulation",
              });
            },
          },
        ],
      ),
      create(
        "button",
        {},
        ["Projection"],
        [
          {
            event: "click",
            fct: async () => {
              await dispatch({ type: "ToggleOpen" });
              await globalDispatch({
                type: "Navigate",
                data: "projection",
              });
            },
          },
        ],
      ),
    ]),
  ]);
}

export function view(model, dispatch) {
  dispatch = createDispatch(dispatch);

  if (model.open) {
    document.getElementById("nav").classList.add("nav--open");
  } else {
    document.getElementById("nav").classList.remove("nav--open");
  }
}
