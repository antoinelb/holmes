import { formatDate, clear, round } from "./utils.js";
import { toggleLoading, addNotification } from "./header.js";
import "/static/assets/plotly-3.1.0.min.js";
import "/static/assets/jszip-3.10.1.min.js";

/*********/
/* model */
/*********/

let model = {
  config: [],
  periodMin: null,
  periodMax: null,
  lastTimeseries: null,
  lastMetrics: null,
};

/********/
/* init */
/********/

export async function init() {
  addEventListeners();
  await initView();
}

async function initView() {
}

function addEventListeners() {
  document.getElementById("simulation__import").addEventListener(
    "change", importCalibratedConfig
  )
  document
    .querySelector("label[for='simulation__period-start'] button")
    .addEventListener("click", updateToPeriodStart);
  document
    .querySelector("label[for='simulation__period-end'] button")
    .addEventListener("click", updateToPeriodEnd);
  document.getElementById("simulation__period").addEventListener("submit", runSimulation);
  document
    .querySelector("#simulation .results__export")
    .addEventListener("click", exportSimulationResults);
}


/**********/
/* update */
/**********/


function importCalibratedConfig(event) {
  const SIMULATION_KEYS = [
    "hydrological model",
    "catchment",
    "criteria",
    "streamflow transformation",
    "algorithm",
    "date start",
    "date end",
    "warmup",
    "snow model",
    "data type",
    "parameters",
  ];

  function updateConfig(event) {
    const table = document.getElementById("simulation__calibration-table");
    const configData = JSON.parse(event.target.result);
    model.config.push(configData);

    const div = document.createElement("div");
    const h4 = document.createElement("h4");
    h4.textContent = `Simulation ${model.config.length}`;
    div.appendChild(h4);

    SIMULATION_KEYS.forEach(key => {
      const val = configData[key];
      const span = document.createElement("span");
      if (typeof val === "object" && val !== null) {
        span.innerHTML = val.map(v => `${v.name}: ${round(v.value, 2)}`).join("<br />");
      } else {
        span.textContent = val ?? "";
      }
      div.appendChild(span);
    });

    table.appendChild(div);
    table.style.setProperty("--n-columns", model.config.length + 1);

    updateSimulationPeriodDefaults();
  }
  [...event.target.files].forEach(file => {
    const reader = new FileReader();
    reader.onload = updateConfig;
    reader.readAsText(file);
  });
  document.getElementById("simulation__period").removeAttribute("hidden");

}

async function updateSimulationPeriodDefaults() {
  const resp = await fetch("/calibration/config");
  if (!resp.ok) {
    addNotification(await resp.text(), true);
    return;
  }
  const config = await resp.json();
  const catchment = config.catchment.filter(catchment => catchment[0] ==
    model.config[model.config.length - 1].catchment).map(catchment =>
      ({ periodMin: new Date(catchment[2][0]), periodMax: new Date(catchment[2][1]) }))[0];
  model.periodMin = model.periodMin ? new Date(Math.max(catchment.periodMin, model.periodMin)) : catchment.periodMin;
  model.periodMax = model.periodMax ? new Date(Math.min(catchment.periodMax, model.periodMax)) : catchment.periodMax;

  const periodStart = document.getElementById("simulation__period-start");
  const periodEnd = document.getElementById("simulation__period-end");
  periodStart.setAttribute("min", model.periodMin);
  periodEnd.setAttribute("max", model.periodMax);

  if (periodStart.value == "" || periodStart.value < model.periodMin) {
    periodStart.value = formatDate(new
      Date(model.periodMax.getFullYear(), 0, 1));
  } if (periodEnd.value == "" || periodEnd.value >
    model.periodMax) {
    periodEnd.value = formatDate(model.periodMax);
  }
}

function updateToPeriodStart(event) {
  event.preventDefault();
  const input = document.getElementById("simulation__period-start");
  input.value = input.min;
}

function updateToPeriodEnd(event) {
  event.preventDefault();
  const input = document.getElementById("simulation__period-end");
  input.value = input.max;
}

function getPlotlyTemplate(theme) {
  // Dark theme colors - vibrant colors for dark backgrounds
  const darkColors = [
    "#fd7f6f", "#7eb0d5", "#b2e061", "#bd7ebe", "#ffb55a",
    "#ffee65", "#beb9db", "#fdcce5", "#8bd3c7",
  ];

  // Light theme colors - soft, muted palette for light backgrounds
  const lightColors = [
    "#d97373", "#5a9bc7", "#8fba4d", "#a866aa", "#e89a3c",
    "#d4b83e", "#9b94c4", "#e5a8c8", "#6cb3a3",
  ];

  if (theme === "light") {
    return {
      font: { color: "rgb(50,50,50)" },
      xaxis: { gridcolor: "#e5e5e5", linecolor: "rgb(80,80,80)" },
      yaxis: { gridcolor: "#e5e5e5", linecolor: "rgb(80,80,80)" },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      colorway: lightColors,
    };
  } else {
    return {
      font: { color: "rgb(230,230,230)" },
      xaxis: { gridcolor: "#2A3459", linecolor: "rgb(230,230,230)" },
      yaxis: { gridcolor: "#2A3459", linecolor: "rgb(230,230,230)" },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      colorway: darkColors,
    };
  }
}

function updateSimulationPlotTheme(event) {
  const fig = document.querySelector("#simulation .results__fig");
  if (!fig || !fig.data) return;

  const theme = event.detail.theme;
  const template = getPlotlyTemplate(theme);

  // Build update object for all axes (including subplots)
  const updates = {
    'font.color': template.font.color,
    'paper_bgcolor': template.paper_bgcolor,
    'plot_bgcolor': template.plot_bgcolor,
  };

  // Update all xaxis and yaxis (handles subplots)
  const layout = fig.layout;
  Object.keys(layout).forEach(key => {
    if (key.startsWith('xaxis') || key === 'xaxis') {
      updates[`${key}.gridcolor`] = template.xaxis.gridcolor;
      updates[`${key}.linecolor`] = template.xaxis.linecolor;
    }
    if (key.startsWith('yaxis') || key === 'yaxis') {
      updates[`${key}.gridcolor`] = template.yaxis.gridcolor;
      updates[`${key}.linecolor`] = template.yaxis.linecolor;
    }
  });

  // Update trace colors
  const dataUpdates = fig.data.map((trace, i) => ({
    'marker.color': template.colorway[i % template.colorway.length],
    'line.color': template.colorway[i % template.colorway.length],
  }));

  // Use Plotly.update to change both layout and traces
  Plotly.update(fig, dataUpdates, updates);
}

async function runSimulation(event) {
  event.preventDefault();

  const theme = document.querySelector("body").classList.contains("light") ? "light" : "dark";

  const loader = document.querySelector("#simulation__period .loading");
  const submit = document.querySelector("#simulation__period input[type='submit']");

  toggleLoading(true);
  loader.removeAttribute("hidden");
  submit.setAttribute("hidden", true);

  const fig = document.querySelector("#simulation .results__fig");

  const config = model.config.map(
    config => ({
      hydrological_model: config["hydrological model"],
      catchment: config.catchment,
      snow_model: config["snow model"],
      params: config.parameters,
      simulation_start: document.getElementById("simulation__period-start").value,
      simulation_end: document.getElementById("simulation__period-end").value,
    })
  )
  const resp = await fetch("/simulation/run", {
    method: "POST",
    body: JSON.stringify({
      configs: config, multimodel: document.getElementById("simulation__multimodel").checked, theme:
        theme
    }),
    headers: {
      "Content-type": "application/json",
    },
  });
  if (!resp.ok) {
    addNotification(await resp.text(), true);
    loader.setAttribute("hidden", true);
    submit.removeAttribute("hidden");
    toggleLoading(false);
    return;
  }
  const data = await resp.json();
  const figData = JSON.parse(data.fig);

  clear(fig);
  Plotly.newPlot(fig, figData.data, figData.layout, {
    displayLogo: false,
    modeBarButtonsToRemove: [
      "zoom",
      "pan",
      "select",
      "lasso",
      "zoomIn",
      "zoomOut",
      "autoScale",
      "resetScale",
    ],
  });

  // Add theme change listener for dynamic plot updates
  window.addEventListener('themeChanged', updateSimulationPlotTheme);

  // Store data for export
  model.lastTimeseries = data.timeseries;
  model.lastMetrics = data.metrics;

  fig.scrollIntoView({ behavior: "smooth", block: "end" });

  loader.setAttribute("hidden", true);
  submit.removeAttribute("hidden");
  toggleLoading(false);
  document.querySelector("#simulation .results__export").removeAttribute("hidden");
}

async function exportSimulationResults() {
  if (!model.lastTimeseries || !model.lastMetrics) {
    addNotification("No simulation results to export", true);
    return;
  }

  const loader = document.querySelector("#simulation .results .loading");
  const exportButton = document.querySelector("#simulation .results__export");

  toggleLoading(true);
  loader.removeAttribute("hidden");
  exportButton.setAttribute("hidden", true);

  try {
    const zip = new JSZip();

    // Get the plotly figure element
    const figElement = document.querySelector("#simulation .results__fig");

    // Save current theme and switch to light theme for export
    const currentTheme = document.querySelector("body").classList.contains("light") ? "light" : "dark";
    if (currentTheme === "dark") {
      const lightTemplate = getPlotlyTemplate("light");

      // Build update object for all axes (including subplots)
      const updates = {
        'font.color': lightTemplate.font.color,
        'paper_bgcolor': lightTemplate.paper_bgcolor,
        'plot_bgcolor': lightTemplate.plot_bgcolor,
      };

      // Update all xaxis and yaxis (handles subplots)
      const layout = figElement.layout;
      Object.keys(layout).forEach(key => {
        if (key.startsWith('xaxis') || key === 'xaxis') {
          updates[`${key}.gridcolor`] = lightTemplate.xaxis.gridcolor;
          updates[`${key}.linecolor`] = lightTemplate.xaxis.linecolor;
        }
        if (key.startsWith('yaxis') || key === 'yaxis') {
          updates[`${key}.gridcolor`] = lightTemplate.yaxis.gridcolor;
          updates[`${key}.linecolor`] = lightTemplate.yaxis.linecolor;
        }
      });

      // Update trace colors
      const dataUpdates = figElement.data.map((trace, i) => ({
        'marker.color': lightTemplate.colorway[i % lightTemplate.colorway.length],
        'line.color': lightTemplate.colorway[i % lightTemplate.colorway.length],
      }));

      await Plotly.update(figElement, dataUpdates, updates);
    }

    // Generate PNG using Plotly's built-in function
    const pngBlob = await new Promise((resolve) => {
      Plotly.toImage(figElement, {
        format: "png",
        width: 1200,
        height: 800
      }).then((dataUrl) => {
        fetch(dataUrl).then(r => r.blob()).then(resolve);
      });
    });

    const svgBlob = await new Promise((resolve) => {
      Plotly.toImage(figElement, {
        format: "svg",
        width: 1200,
        height: 800
      }).then((dataUrl) => {
        fetch(dataUrl).then(r => r.blob()).then(resolve);
      });
    });

    // Restore original theme if it was dark
    if (currentTheme === "dark") {
      const darkTemplate = getPlotlyTemplate("dark");

      // Build update object for all axes (including subplots)
      const updates = {
        'font.color': darkTemplate.font.color,
        'paper_bgcolor': darkTemplate.paper_bgcolor,
        'plot_bgcolor': darkTemplate.plot_bgcolor,
      };

      // Update all xaxis and yaxis (handles subplots)
      const layout = figElement.layout;
      Object.keys(layout).forEach(key => {
        if (key.startsWith('xaxis') || key === 'xaxis') {
          updates[`${key}.gridcolor`] = darkTemplate.xaxis.gridcolor;
          updates[`${key}.linecolor`] = darkTemplate.xaxis.linecolor;
        }
        if (key.startsWith('yaxis') || key === 'yaxis') {
          updates[`${key}.gridcolor`] = darkTemplate.yaxis.gridcolor;
          updates[`${key}.linecolor`] = darkTemplate.yaxis.linecolor;
        }
      });

      // Update trace colors
      const dataUpdates = figElement.data.map((trace, i) => ({
        'marker.color': darkTemplate.colorway[i % darkTemplate.colorway.length],
        'line.color': darkTemplate.colorway[i % darkTemplate.colorway.length],
      }));

      await Plotly.update(figElement, dataUpdates, updates);
    }

    // Add plot images to ZIP
    zip.file("plot.png", pngBlob);
    zip.file("plot.svg", svgBlob);

    // Create metrics CSV
    const metricsHeader = "simulation,nse_high,nse_medium,nse_low,water_balance,flow_variability,correlation\n";
    const metricsRows = model.lastMetrics.map(m =>
      `${m.simulation},${m.nse_high},${m.nse_medium},${m.nse_low},${m.water_balance},${m.flow_variability},${m.correlation}`
    ).join("\n");
    zip.file("metrics.csv", metricsHeader + metricsRows);

    // Create timeseries CSV
    const timeseriesKeys = Object.keys(model.lastTimeseries[0]);
    const timeseriesHeader = timeseriesKeys.join(",") + "\n";
    const timeseriesRows = model.lastTimeseries.map(row =>
      timeseriesKeys.map(key => row[key]).join(",")
    ).join("\n");
    zip.file("timeseries.csv", timeseriesHeader + timeseriesRows);

    // Generate ZIP and trigger download
    const zipBlob = await zip.generateAsync({ type: "blob" });
    const url = window.URL.createObjectURL(zipBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "simulation_results.zip";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    addNotification("Export completed successfully", false);
  } catch (error) {
    console.error("Export error:", error);
    addNotification("Export failed: " + error.message, true);
  } finally {
    loader.setAttribute("hidden", true);
    exportButton.removeAttribute("hidden");
    toggleLoading(false);
  }
}
