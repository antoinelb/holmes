import { clear, create } from "../utils/elements.js";

// order and display names are fixed by the assignment; parameter counts and
// descriptions come from the backend model_info payload
const hydroModels = [
  { id: "gr4j", label: "GR4J" },
  { id: "bucket", label: "Bucket" },
  { id: "cequeau", label: "CEQUEAU" },
  { id: "crec", label: "CREC" },
  { id: "gardenia", label: "Gardénia" },
  { id: "hbv", label: "HBV" },
  { id: "hymod", label: "HYMOD" },
  { id: "ihacres", label: "IHACRES" },
  { id: "martine", label: "Martine" },
  { id: "mohyse", label: "MOHYSE" },
  { id: "mordor", label: "MORDOR" },
  { id: "nam", label: "NAM" },
  { id: "pdm", label: "PDM" },
  { id: "sacramento", label: "Sacramento" },
  { id: "simhyd", label: "SIMHYD" },
  { id: "smar", label: "SMAR" },
  { id: "tank", label: "Tank" },
  { id: "topmodel", label: "TOPMODEL" },
  { id: "wageningen", label: "Wageningen" },
  { id: "xinanjiang", label: "Xinanjiang" },
];

const snowModels = [
  { id: "none", label: "None" },
  { id: "cemaneige", label: "CemaNeige" },
];

// "none" is a real, selectable value but not a backend model, so its blurb is
// hardcoded here rather than read from model_info
const noneDescription =
  "Rain only — precipitation reaches the model directly, with no snow accumulation or melt accounting.";

/**********/
/* update */
/**********/

export function update(model, msg, dispatch) {
  switch (msg.type) {
    case "model/GetModelInfo":
      // guard so a disconnected socket or an in-flight request doesn't spin
      // the dispatch queue; "pending" marks the request until the reply lands
      if (model.modelInfo || model.ws?.readyState !== WebSocket.OPEN) {
        return model;
      }
      model.ws.send(JSON.stringify({ type: "model_info" }));
      return { ...model, modelInfo: "pending" };
    case "model/GotModelInfo":
      return { ...model, modelInfo: msg.data };
    case "model/ToggleMode": {
      // the whole control is one switch: either half flips it. the mode is
      // read here rather than in the click handler, which is built once and
      // would capture a stale config
      const mode =
        model.config.modelMode === "ensemble" ? "single" : "ensemble";
      dispatch({ type: "SetConfig", data: { key: "modelMode", value: mode } });
      // ensemble -> single keeps only the first selected model
      const selected = model.config.hydroModels ?? [];
      if (mode === "single" && selected.length > 1) {
        dispatch({
          type: "SetConfig",
          data: { key: "hydroModels", value: selected.slice(0, 1) },
        });
      }
      return model;
    }
    case "model/ToggleModel": {
      // read the fresh model here (the handlers are built once, so their
      // closures would capture a stale config)
      const id = msg.data;
      const selected = model.config.hydroModels ?? [];
      const next =
        model.config.modelMode === "ensemble"
          ? selected.includes(id)
            ? selected.filter((m) => m !== id)
            : [...selected, id]
          : [id];
      dispatch({
        type: "SetConfig",
        data: { key: "hydroModels", value: next },
      });
      return model;
    }
    case "model/SelectAll":
    case "model/ClearAll": {
      // the buttons are hidden outside ensemble mode, but a stale dispatch
      // must not leave single mode holding 20 models (or none)
      if (model.config.modelMode !== "ensemble") {
        return model;
      }
      dispatch({
        type: "SetConfig",
        data: {
          key: "hydroModels",
          value:
            msg.type === "model/SelectAll" ? hydroModels.map((m) => m.id) : [],
        },
      });
      return model;
    }
    case "model/Hover":
      return { ...model, modelDetail: msg.data };
    default:
      return model;
  }
}

/********/
/* view */
/********/

// the step owns the whole canvas and needs no side panel; clearing #controls
// lets its `&:empty { display: none }` rule hide it
export function controlsView(_model, _dispatch) {
  const controls = document.getElementById("controls");
  if (controls.dataset.step !== "model") {
    controls.dataset.step = "model";
    clear(controls);
  }
}

export function canvasView(model, dispatch) {
  const canvas = document.getElementById("canvas");
  // structure is built once per step entry, then reconciled in place:
  // rebuilding under a click swallows it
  if (canvas.dataset.step !== "model") {
    canvas.dataset.step = "model";
    clear(canvas);
    canvas.append(rootView(dispatch));
  }
  fetchModelInfo(model, dispatch);
  syncCanvas(model);
}

// fetch-on-view (like weather's fetchWeather): covers a reload landing on this
// step and a reconnect clearing the "pending" sentinel; the update guard stops
// re-dispatch on later renders
function fetchModelInfo(model, dispatch) {
  if (!model.modelInfo && model.ws?.readyState === WebSocket.OPEN) {
    dispatch({ type: "model/GetModelInfo" });
  }
}

function rootView(dispatch) {
  return create("div", { class: "model" }, [
    headerView(dispatch),
    create(
      "div",
      { id: "model__grid", class: "model__grid" },
      hydroModels.map((m) => optionView(m, "hydro", dispatch)),
    ),
    create("section", { class: "model__snow" }, [
      create("h3", { class: "model__subtitle" }, "Snow model"),
      create(
        "div",
        { class: "model__snow-options" },
        snowModels.map((m) => optionView(m, "snow", dispatch)),
      ),
    ]),
    create("div", { id: "model__detail", class: "model__detail" }),
  ]);
}

function headerView(dispatch) {
  return create("div", { class: "model__header" }, [
    create("h2", { class: "model__title" }, "Hydrological model"),
    create("div", { id: "model__mode", class: "model__mode" }, [
      modeButton("single", "Single", dispatch),
      modeButton("ensemble", "Ensemble", dispatch),
    ]),
    // only meaningful for a multi-selection, so hidden in single mode
    create("div", { id: "model__bulk", class: "model__bulk" }, [
      bulkButton("SelectAll", "Select all", dispatch),
      bulkButton("ClearAll", "Clear", dispatch),
    ]),
    create("span", { id: "model__summary", class: "model__summary" }),
  ]);
}

function bulkButton(action, label, dispatch) {
  return create("button", { class: "model__bulk-btn", type: "button" }, label, [
    { event: "click", fct: () => dispatch({ type: `model/${action}` }) },
  ]);
}

function modeButton(mode, label, dispatch) {
  return create(
    "button",
    { id: `model__mode-${mode}`, class: "model__mode-btn", type: "button" },
    label,
    [{ event: "click", fct: () => dispatch({ type: "model/ToggleMode" }) }],
  );
}

// hydro clicks toggle the array (semantics decided in update by the mode);
// snow clicks set the scalar directly, since no fresh config read is needed
function optionView(m, kind, dispatch) {
  return create(
    "button",
    {
      id: `model__option-${kind}-${m.id}`,
      class: "model__option",
      type: "button",
    },
    [
      create("span", { class: "model__glyph" }),
      create("span", { class: "model__option-label" }, m.label),
    ],
    [
      {
        event: "click",
        fct: () =>
          dispatch(
            kind === "hydro"
              ? { type: "model/ToggleModel", data: m.id }
              : {
                  type: "SetConfig",
                  data: { key: "snowModel", value: m.id },
                },
          ),
      },
      {
        event: "mouseenter",
        fct: () =>
          dispatch({ type: "model/Hover", data: { kind: kind, id: m.id } }),
      },
    ],
  );
}

function syncCanvas(model) {
  const mode = model.config.modelMode ?? "single";
  const selected = model.config.hydroModels ?? [];

  // the mode class drives the glyph morph (circle <-> square) in CSS
  const grid = document.getElementById("model__grid");
  grid.classList.toggle("model__grid--single", mode === "single");
  grid.classList.toggle("model__grid--ensemble", mode === "ensemble");

  // the container class positions the sliding fill; the per-button class only
  // carries the label colour, since the fill is one shared element
  document
    .getElementById("model__mode")
    .classList.toggle("model__mode--ensemble", mode === "ensemble");
  document
    .getElementById("model__mode-single")
    .classList.toggle("model__mode-btn--active", mode === "single");
  document
    .getElementById("model__mode-ensemble")
    .classList.toggle("model__mode-btn--active", mode === "ensemble");

  document.getElementById("model__bulk").hidden = mode !== "ensemble";

  document.getElementById("model__summary").textContent = summaryText(
    mode,
    selected,
  );

  hydroModels.forEach((m) => {
    const btn = document.getElementById(`model__option-hydro-${m.id}`);
    btn.classList.toggle("model__option--selected", selected.includes(m.id));
    btn.querySelector(".model__option-label").textContent =
      `${m.label} (${hydroCount(model, m.id)} params)`;
  });

  snowModels.forEach((m) => {
    const btn = document.getElementById(`model__option-snow-${m.id}`);
    btn.classList.toggle(
      "model__option--selected",
      model.config.snowModel === m.id,
    );
    btn.querySelector(".model__option-label").textContent = snowLabel(model, m);
  });

  detailView(model);
}

function summaryText(mode, selected) {
  if (mode === "ensemble") {
    return `ensemble of ${selected.length} model${
      selected.length === 1 ? "" : "s"
    }`;
  }
  // the glyph already marks the single selection, so its name would be
  // redundant here; only the empty case needs a cue
  return selected.length ? "" : "no model selected";
}

// "…" until the payload lands, then the parameter count
function hydroCount(model, id) {
  const info = isLoaded(model.modelInfo) ? model.modelInfo.hydro?.[id] : null;
  return info ? info.parameters.length : "…";
}

// "none" carries no parameters; cemaneige shows its count once loaded
function snowLabel(model, m) {
  if (m.id === "none") {
    return m.label;
  }
  const info = isLoaded(model.modelInfo) ? model.modelInfo.snow?.[m.id] : null;
  return info
    ? `${m.label} (${info.parameters.length} params)`
    : `${m.label} (… params)`;
}

// the panel is sticky: last-hovered model, else the first selected one; it
// never empties on mouseleave (no Hover is dispatched there)
function detailView(model) {
  const detail = document.getElementById("model__detail");
  const target = detailTarget(model);
  const info = target ? detailInfo(model, target) : null;
  const signature = detailSignature(target, info);
  if (detail.dataset.signature === signature) {
    return;
  }
  detail.dataset.signature = signature;
  clear(detail);

  if (!target) {
    detail.append(
      create(
        "p",
        { class: "model__detail-empty" },
        "Hover over a model to see its details.",
      ),
    );
    return;
  }
  if (info === null) {
    detail.append(
      create("p", { class: "model__detail-loading" }, "Loading model details…"),
    );
    return;
  }
  detail.append(
    create(
      "h3",
      { class: "model__detail-title" },
      info.parameters.length
        ? `${info.label} (${info.parameters.length} params)`
        : info.label,
    ),
    create("p", { class: "model__detail-description" }, info.description),
    create(
      "div",
      { class: "model__detail-params" },
      // x-indices are uniform names from array position, not backend-provided
      info.parameters.map((desc, i) =>
        create("span", { class: "model__param" }, [
          create("b", { class: "model__param-name" }, `x${i + 1}`),
          ` — ${desc}`,
        ]),
      ),
    ),
  );
}

function detailTarget(model) {
  if (model.modelDetail) {
    return model.modelDetail;
  }
  const first = (model.config.hydroModels ?? [])[0];
  return first ? { kind: "hydro", id: first } : null;
}

// null means "not available yet" -> the loading placeholder; the snow "none"
// blurb is always available
function detailInfo(model, target) {
  if (target.kind === "snow" && target.id === "none") {
    return { label: "None", description: noneDescription, parameters: [] };
  }
  if (!isLoaded(model.modelInfo)) {
    return null;
  }
  const group =
    target.kind === "hydro" ? model.modelInfo.hydro : model.modelInfo.snow;
  const raw = group?.[target.id];
  if (!raw) {
    return null;
  }
  return {
    label: displayName(target),
    description: raw.description,
    parameters: raw.parameters,
  };
}

function detailSignature(target, info) {
  if (!target) {
    return "empty";
  }
  return `${target.kind}|${target.id}|${info ? "loaded" : "loading"}`;
}

function displayName(target) {
  const list = target.kind === "hydro" ? hydroModels : snowModels;
  return list.find((m) => m.id === target.id)?.label ?? target.id;
}

// "pending" (a string) and null both read as not-yet-loaded
function isLoaded(modelInfo) {
  return modelInfo != null && typeof modelInfo === "object";
}
