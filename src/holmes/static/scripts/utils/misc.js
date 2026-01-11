export const frenchLocale = d3.timeFormatLocale({
  dateTime: "%A %e %B %Y à %X",
  date: "%Y-%m-%d",
  time: "%H:%M:%S",
  periods: ["", ""],
  days: [
    "dimanche",
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
  ],
  shortDays: ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"],
  months: [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
  ],
  shortMonths: [
    "jan",
    "fév",
    "mar",
    "avr",
    "mai",
    "jun",
    "jul",
    "aoû",
    "sep",
    "oct",
    "nov",
    "déc",
  ],
});

export const colours = [
  "blue",
  "red",
  "green",
  "purple",
  "orange",
  "pink",
  "turquoise",
  "yellow",
];

export function round(n, d) {
  return Math.round(n * 10 ** d) / 10 ** d;
}

export function formatNumber(n) {
  return n.toLocaleString("en-US").replace(/,/g, " ");
}

export function range(start, end) {
  if (end === undefined) {
    return [...Array(start).keys()];
  } else {
    return [...Array(end).keys()].filter((x) => x >= start);
  }
}

export function toTitle(text) {
  return text
    .split()
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

export function setEqual(set1, set2) {
  return set1.size === set2.size && [...set1].every((value) => set2.has(value));
}

/**
 * Set difference: returns elements in setA that are not in setB
 * Browser-compatible alternative to Set.prototype.difference()
 */
export function setDifference(setA, setB) {
  return new Set([...setA].filter((x) => !setB.has(x)));
}

/**
 * Log error with context and stack trace
 */
export function logError(context, error) {
  console.error(`[${context}]`, error);
  if (error instanceof Error && error.stack) {
    console.error(error.stack);
  }
}

/**
 * Validate that start date is before end date
 * Returns [isValid, errorMessage]
 */
export function validateDateRange(start, end) {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
    return [false, "Invalid date format"];
  }
  if (startDate >= endDate) {
    return [false, "Start date must be before end date"];
  }
  return [true, null];
}

/**
 * Validate calibration JSON structure
 * Returns [isValid, errorMessage]
 */
export function validateCalibrationJson(data) {
  if (data === null || typeof data !== "object") {
    return [false, "Invalid JSON structure"];
  }
  const required = [
    "hydroModel",
    "catchment",
    "objective",
    "transformation",
    "algorithm",
    "algorithmParams",
    "start",
    "end",
    "snowModel",
    "hydroParams",
  ];
  for (const key of required) {
    if (!(key in data)) {
      return [false, `Missing required field: ${key}`];
    }
  }
  return [true, null];
}
