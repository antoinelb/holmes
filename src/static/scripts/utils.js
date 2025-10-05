export function onKey(key, callback, event, modifiers) {
  const withCtrl = modifiers ? modifiers.withCtrl | false : false;
  const withAlt = modifiers ? modifiers.withAlt | false : false;
  if (event.target.tagName != "INPUT" && event.target.tagName != "SELECT") {
    if (
      event.key == key &&
      event.ctrlKey == withCtrl &&
      event.altKey == withAlt
    ) {
      callback(event);
      event.preventDefault();
    }
  }
}

export function range(start, end) {
  if (end === undefined) {
    return [...Array(start).keys()];
  } else {
    return [...Array(end).keys()].filter((x) => x >= start);
  }
}

export function checkEscape(model, event, dispatch) {
  if (model.preventEscape) {
    return false;
  } else {
    if (event.type == "click") {
      return event.target.classList.contains("form__bg");
    } else if (event.type == "keydown") {
      if (event.key == "Escape") {
        const focused = document.activeElement;
        if (focused.tagName == "INPUT" || focused.tagName == "SELECT") {
          focused.blur();
          dispatch({ type: "SetPreventEscape" });
          return false;
        } else {
          return true;
        }
      } else {
        return false;
      }
    } else {
      return false;
    }
  }
}

export function clear(node) {
  [...node.children].forEach((child) => {
    node.removeChild(child);
  });
}

export function round(n, d) {
  return Math.round(n * 10 ** d) / 10 ** d;
}

export function createSlider(id, name, min, max, isInteger) {
  const slider = document.createElement("div");
  slider.classList.add("slider");

  const span = document.createElement("span");
  span.classList.add("slider__value");
  slider.appendChild(span);

  const input = document.createElement("input");
  input.setAttribute("type", "range");
  input.setAttribute("id", id);
  input.setAttribute("name", name);
  slider.appendChild(input);

  const range = document.createElement("div");
  range.classList.add("slider__range");
  slider.appendChild(range);

  initSlider(slider, min, max, isInteger);

  return slider;
}

export function initSlider(slider, min, max, isInteger, nValues) {
  if (!nValues) {
    nValues = 5;
  }

  const input = slider.querySelector("input")
  const value = slider.querySelector(".slider__value");
  const values = slider.querySelector(".slider__range");
  clear(values);

  input.setAttribute("min", min);
  input.setAttribute("max", max);
  input.setAttribute("step", isInteger ? "1" : "0.1");

  if (isInteger) {
    input.value = Math.round((max + min) / 2);
    value.textContent = Math.round((max + min) / 2);
  } else {
    input.value = round((max + min) / 2, 1).toFixed(1);
    value.textContent = round((max + min) / 2, 1).toFixed(1);
  }

  range(nValues).forEach(i => {
    const span = document.createElement("span");
    if (isInteger) {
      span.textContent = Math.round(min + i * (max - min) / (nValues - 1));
    } else {
      span.textContent = round(min + i * (max - min) / (nValues - 1), 1).toFixed(1);
    }

    // Calculate position accounting for thumb width (webkit sliders have ~20px thumb)
    // The track effectively starts at 10px and ends at width-10px
    const thumbRadius = 10; // Half of thumb width
    const percent = (i / (nValues - 1)) * 100;
    const offset = thumbRadius * (1 - 2 * i / (nValues - 1));
    span.style.position = 'absolute';
    span.style.left = `calc(${percent}% + ${offset}px)`;
    span.style.transform = 'translateX(-50%)';
    values.appendChild(span);
  })

  input.addEventListener("input", event => updateSlider(event.target.parentNode));

  updateSlider(slider);

}

function updateSlider(slider) {
  const input = slider.querySelector("input")
  const span = slider.querySelector(".slider__value");
  const isInteger = input.getAttribute("step") == "1";

  if (isInteger) {
    span.textContent = input.value;
  } else {
    span.textContent = parseFloat(input.value).toFixed(1);
  }

  const percent = (parseFloat(input.value) - parseFloat(input.getAttribute("min"))) /
    (parseFloat(input.getAttribute("max")) - parseFloat(input.getAttribute("min"))) * 100;

  span.style.setProperty("left", `${round(percent, 1)}%`);
  span.style.setProperty("transform", `translateX(-${percent}%)`);
}

export function createLoading() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("icon")
  svg.classList.add("loading")
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "/static/assets/sprite.svg#loader")
  svg.appendChild(use);
  return svg
}
