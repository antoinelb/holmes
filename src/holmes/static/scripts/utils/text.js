// The language can only change through a full reload
// (settings.js:toggleLanguage), so a module-level constant can never go
// stale and every string can be resolved at build time.
export const language =
  window.localStorage.getItem("holmes--settings--language") ?? "en";

document.documentElement.lang = language === "fr" ? "fr-CA" : "en-CA";

export function t(en, fr) {
  return language === "fr" ? fr : en;
}

// for {en, fr} wire payloads (model_info, calibration_info)
export function pick(obj) {
  return obj[language];
}
