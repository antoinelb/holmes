export function create(type, attributes = {}, children = [], events = []) {
  const node =
    type === "svg" || type === "use"
      ? document.createElementNS("http://www.w3.org/2000/svg", type)
      : document.createElement(type);
  Object.keys(attributes).forEach((key) => {
    if (key === "style") {
      Object.keys(attributes[key]).forEach((style) => {
        node.style.setProperty(style, attributes[key][style]);
      });
    } else {
      node.setAttribute(key, attributes[key]);
    }
  });
  if (!Array.isArray(children)) {
    children = [children];
  }
  children.forEach((child) => {
    if (typeof child === "string" || typeof child === "number") {
      node.appendChild(document.createTextNode(child));
    } else {
      node.appendChild(child);
    }
  });
  if (type === "form") {
    events = [
      ...events,
      { event: "submit", fct: (event) => event.preventDefault() },
    ];
  }
  events.forEach((event) => {
    node.addEventListener(event.event, event.fct);
  });
  return node;
}

export function clear(node) {
  [...node.children].forEach((child) => {
    node.removeChild(child);
  });
}

// transform (optional) maps between the raw parameter space (number input,
// change payloads) and the range input's own space, so a log-scaled parameter
// can slide smoothly over several orders of magnitude while the number input
// still reads and writes the raw value; null keeps the two spaces identical
export function createSlider(
  id,
  min,
  max,
  isInteger,
  events = [],
  initialVal = null,
  transform = null,
) {
  if (initialVal === null) {
    initialVal = isInteger
      ? Math.round((max + min) / 2)
      : round((max + min) / 2, 1);
  }

  // the range input lives in transformed space when a transform is given; its
  // step is a thousandth of that span so float sliders stay fine-grained
  const tMin = transform ? transform.toSlider(min) : min;
  const tMax = transform ? transform.toSlider(max) : max;
  const rangeStep = transform ? (tMax - tMin) / 1000 : isInteger ? "1" : "0.01";
  const rangeValue = transform
    ? transform.toSlider(initialVal)
    : isInteger
      ? initialVal.toString()
      : initialVal.toFixed(1);
  const numberValue = isInteger ? initialVal.toString() : initialVal.toFixed(1);

  return create("div", { class: "slider" }, [
    create(
      "input",
      {
        type: "range",
        min: tMin,
        max: tMax,
        step: rangeStep,
        value: rangeValue,
      },
      [],
      [
        ...events,
        {
          event: "input",
          fct: (event) => {
            document.getElementById(id).value = transform
              ? transform.fromSlider(Number(event.target.value))
              : event.target.value;
          },
        },
      ],
    ),
    create(
      "input",
      {
        id: id,
        type: "number",
        min: min,
        max: max,
        step: isInteger ? "1" : "0.01",
        value: numberValue,
      },
      [],
      [
        {
          event: "input",
          fct: (event) => {
            setTimeout(() => {
              event.target.value = Math.min(
                Math.max(event.target.value, min),
                max,
              );
              const slider = event.target.parentNode.querySelector(
                "input[type='range']",
              );
              slider.value = transform
                ? transform.toSlider(Number(event.target.value))
                : event.target.value;
              slider.dispatchEvent(new Event("change", { bubbles: true }));
            }, 500);
          },
        },
      ],
    ),
  ]);
}

export function createIcon(icon) {
  return create("svg", { class: "icon" }, [
    create("use", { href: `#icon-${icon}` }),
  ]);
}

export function createLoading() {
  return create("svg", { class: "icon loading" }, [
    create("use", { href: "#icon-loader" }),
  ]);
}

export function createCheckbox(attributes, events) {
  return create("div", { class: "checkbox" }, [
    create("input", { type: "checkbox", ...attributes }, [], events),
    create("span", { class: "checkbox__bg" }),
    create("span", { class: "checkbox__fg" }),
  ]);
}
