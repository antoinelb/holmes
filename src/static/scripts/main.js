/**********/
/* update */
/**********/

export function changeApp(app) {
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
