# AIR compliance audit & implementation plan

Audit of the HOLMES v4 UI against AIR v1.0 (`~/.claude/interface-rules.md`), 2026-08-15.
This file is the to-implement list; delete items as they land.

## Summary

The app is strong exactly where AIR is usually weak — all JS/CSS vendored, map tiles proxied through the backend, imports shape-validated, input persisted with `pagehide` flush, superseded replies keyed and dropped.
It systematically fails on three fronts:

- **The error channel**: every failure path ends in `console.error`, so failure renders as an infinite spinner, indistinguishable from "slow".
- **Action safety**: three unconfirmed, non-undoable destructive actions.
- **Display truth**: UTC dates rendered in local time, colour-only encodings, mid-edit input rewriting, bare spinners hiding stale-but-valid charts.

All new user-facing strings go through `t(en, fr)` (`utils/text.js`) — FR/EN parity is a shipping gate (ERR-7 + project rules).
Paths below are relative to `src/holmes/` unless noted.

---

## Tier 1 — critical

### 1. User-visible status/error surface (ERR-1, ERR-2, ALR-4, ALR-6)

Findings:

- `static/scripts/index.js:274-277` — `case "error": console.error(msg.data)`: every server error (weather/streamflow/station/calibration-data failures) updates no state and renders nothing; the affected chart spins forever.
- `steps/calibration.js:487-496`, `steps/simulation.js:112-117`, `steps/projection.js:133-138` — typed `*_error` events are console-only; the Stop button silently reverts to Calibrate with no explanation.
- `index.js:245-254` — localStorage quota overflow silently discards the whole attempt history (`console.error` only).
- No toast/banner/notification system exists anywhere in the app.

Changes:

- Add a reserved fixed status region `#status` to the shell (`index.js:initView`, top-centre; charts live in the bottom 24vh so it never occludes data), with `role="status"` and `aria-live="polite"`.
- Model gains `notices: []` (transient, never persisted); each notice: `{id, headline: {en, fr}, detail (raw server text), kind, retryMsg?}`.
- Notices persist until dismissed (× button) — no auto-dismiss; cap the stack (e.g. 5, oldest collapsed into a count).
- Wire every error path into it: generic `error` event, the three `Got*Error` handlers, quota overflow, calibration-killed-by-disconnect (see §2).
- Failed-load notices carry a **Retry** button that clears the pending request key and re-dispatches — this keeps the existing anti-hammer design (`simulation.js:113-116`) but makes retry user-driven instead of impossible.
- Headline is bilingual client text per event type; the server message is the copyable detail (ERR-1: what happened / what the system did / what's affected / what to do / copyable detail).

### 2. Connection status + recovery (DEG-2, ERR-4)

Findings:

- `index.js:171-179` — after 10 failed reconnects the circuit breaker (`utils/ws.js:35-38`) opens permanently; only signal is `console.error("Connection lost.")`; the only recovery is a manual page reload.
- While disconnected, every send is silently skipped (`model.ws?.readyState !== WebSocket.OPEN` guards across all steps); pending keys strand as eternal spinners.
- If the breaker opens mid-calibration, `calibrating` flags stay set forever → sliders and settings stay disabled with no explanation.
- The only global loading affordance is a favicon swap (`index.js:379-394`).

Changes:

- Persistent connection chip in `#status`: nothing when connected; "Reconnecting (attempt N/10)…" while backing off; "Disconnected — Reconnect" (button) once the breaker opens.
- The Reconnect button resets the ws state (`ws.js:resetReconnectState`) and dispatches `Connect`.
- When the breaker opens, clear `calibrating` flags (same as `Connected` does) and post a notice.
- When a reconnect reveals a run was killed server-side (`Connected` clears `calibrating`, `index.js:145-151`), post a notice saying the run was stopped by the disconnect.

### 3. Timezone display (TIM-1)

Findings:

- Dates are serialized as midnight-**UTC** epoch seconds (`utils/api.py:248-261`) but rendered with local-time d3: `static/scripts/utils/plot.js:548-566` (`tickDate` uses `d3.timeDay`/`d3.timeFormat`), and all x scales use `d3.scaleTime`.
- West of UTC (Quebec: −4/−5) every axis date renders as the previous evening, and the `%H:%M` branch fires on zoom, showing spurious "20:00" ticks on daily data.
- Filtering is already UTC-consistent (`new Date("YYYY-MM-DD")` parses UTC) and CSV export uses `toISOString()` — only the d3 display layer disagrees.

Changes:

- Switch every time scale to `d3.scaleUtc`; tick formatting to `d3.utcFormat` / `frenchLocale.utcFormat`; boundary checks to `d3.utcDay/utcMonth/utcYear`; drop the now-unreachable `%H:%M` branch.
- Sanity check: the July 1996 flood peak must land on the 20th, not the 19th.

### 4. Numeric input: no mid-edit rewriting (INP-7, ERR-6)

Findings:

- `utils/elements.js:110-126` — the number input clamps on a 500 ms timer after **every keystroke**; `Math.max("", min)` coerces an empty/mid-edit field to a clamped number while the user is still typing (typing "0.05" slowly in a `[0.01, 100]` field gets rewritten mid-keystroke).
- `.error-input` (`styles/template.css:206-209`) is defined but never applied by any script — there is no inline validation feedback at all.

Changes:

- Remove the `input`-timer handler; clamp + sync the range + fire `change` on the **`change` event** (blur/Enter commit) only.
- Invalid/empty on commit: keep the field content, mark with `.error-input` + `aria-invalid`, don't propagate; never clear the field.
- Verify the same commit-only discipline on SCE hyperparameter inputs (`calibration.js:1203-1233`) and weather n-stations (`weather.js:214-218`).

### 5. Focus visibility & keyboard basics (INP-4)

Findings:

- Zero `:focus-visible` anywhere; buttons have no focus style; the range input hard-disables it (`styles/elements.css:16` `outline: none`); the only real focus outline in the app is on selects (`template.css:181-183`).
- Settings panel is hidden with `transform: scale(0)` (`settings.css:60`) but its buttons stay in tab order (focusable-but-invisible trap).
- The map station dialog is not closed by Escape — only by clicking the map (`stations.js:981`).
- Hotkeys `T`/`L` only fire on Shift+letter: `utils/listeners.js:6` compares `event.key === key` exactly, but the UI hints show bare "T"/"L".

Changes:

- Global `:focus-visible { outline: 2px solid oklch(var(--theme-most)); outline-offset: 2px; }` in `template.css`; remove `outline: none` on the range input.
- `visibility: hidden` on the closed settings panel.
- Escape closes the station dialog (extend `checkEscape`, `listeners.js:16-39`).
- Hotkey comparison becomes case-insensitive.

---

## Tier 2 — action safety & provenance

### 6. Destructive actions get their AIR-mandated mechanism (ACT-2/3)

| Action | Today | Change |
|---|---|---|
| **Reset all** (`settings.js:75-83`) — wipes every `holmes*` key + reloads | one click, no confirm | **Delayed-with-cancel** (ACT-3): button becomes "Resetting in 5 s — Cancel" countdown, then executes. |
| **Clear bench** (`calibration.js:497-528`, button at 845-855) | one click, no confirm | **Undo** (ACT-2): execute immediately, stash `{attempts, draft, simulations}` in transient model state, notice with Undo button (valid until the next bench-mutating action). |
| **Context-change discard** (`calibration.js:225-280` silently drops the whole attempt history when an upstream config key changed) | silent | Notice naming what was discarded and why ("station changed"), with **Undo** restoring the stashed bench *and* the prior values of the changed context keys (one-deep stash: `{priorConfigKeys, attempts, draft}`). Fallback if config restore proves too entangled: notice + Undo-bench-only when the user returns to a matching context. |
| **Import over an existing bench with matching config** (`calibration.js:566-617` overwrites silently; the diff dialog only fires when config differs) | silent | Route through the existing native `<dialog>` confirm ("Importing replaces your current N attempts") when a bench exists. |

### 7. Loading keeps stale content visible + elapsed time (LAT-4, LAT-6)

Findings:

- `styles/pipeline.css:661-668` — the `--loading` class does `.plot { display: none }`, hiding the previous (stale but valid) chart during any refetch, even though the SVG is still in the DOM.
- `createLoading()` (`elements.js:138-142`) is a bare spinner: no elapsed time, no cancel, no timeout messaging; a failed load leaves it spinning forever (fixed via §1 notices).

Changes:

- Change `--loading` to overlay the spinner and dim the plot (`opacity: 0.4`) instead of hiding it.
- `createLoading()` gains an elapsed-time counter: a `<span>` updated by a 1 s interval that self-clears when `!el.isConnected` (views clear/rebuild nodes, so no teardown hook exists).
- Waiver (LAT-4 cancel): passive read loads have no cancel semantics here; supersession/navigation is the cancel, and calibration runs already have Stop buttons.

### 8. Export provenance (EXP-1, EXP-3)

Findings:

- All CSV exports are bare data: `["datetime", "streamflow"]` etc. — no units, no source, no generation time; the weather method survives only in the filename (`weather.js:133`).
- Numbers in CSVs use full double precision (`utils/export.js:24-26` `String(v)`).
- The JSON exports (calibration/simulation/projection) embed config — the strongest provenance in the app — but not app version or generation time.
- Snow params are exported as an anonymous magic array `[0.25, 3.74, qnbv]` (`calibration.js:731-733, 1753-1755`).

Changes:

- `exportCsv` (`utils/export.js`) gains a `#`-prefixed metadata header block: generated-at (ISO-8601 with offset), app version (already fetched via `settings/GetVersion`), station id + name, period, weather method (+ n_stations), per-column units, missing-value convention (empty field).
- Update all call sites: `stations.js:196-204`, `weather.js:124-141`, `calibration.js:1777-1802`, `simulation.js:604-623`, `projection.js:~700`.
- JSON exports add `version` and `generatedAt`; snow constants become keyed fields.

### 9. Unit consistency (TIM-3)

- Streamflow is mm/day in the data but labelled `mm` in stations/calibration/simulation (`plot.js:13`, `calibration.js:1656`, `simulation.js:471`) and `mm/day` in projection (`projection.js:595`).
- Standardize on **mm/day** for streamflow labels; precipitation stays `mm` (daily accumulation); the simulation metrics chart (`dotProfileView`) gets a "dimensionless" note in its caption.

### 10. ARIA & remaining keyboard gaps (INP-4/5)

Findings:

- Zero `aria-*`/`role`/`tabindex` in first-party code; icon-only sidebar/settings buttons have `title` only.
- Map legend visibility toggles are clickable `<div>`s (`stations.js:773-795`).
- Ensemble model identity is hover-only: the row `mouseenter` cross-highlight (`calibration.js:1298-1307`, `simulation.js:319-328`, `projection.js:457-466`) has no focus path; model descriptions likewise (`model.js:220-224`).

Changes:

- `aria-label` on icon-only buttons (pipeline steps `pipeline.js:186-198`, settings toggle, date-reset); `aria-hidden="true"` on `createIcon`/`createLoading` sprites.
- Legend toggles become real `<button>`s.
- Row cross-highlight and model descriptions also fire on `focus`/`blur` (rows get `tabindex="0"` or become buttons).
- Map markers stay pointer-only: station selection has a full keyboard path via the `<select>`s (`stations.js:256-270`) — LAY-5 satisfied; documented, not built.

---

## Tier 3 — encoding & polish

### 11. Non-colour redundancy (INP-3, TRU-5)

- **Observed vs simulated series**: distinguished today by hue + stacking only (`styles/index.css:46-75`, deliberately all hairlines). Give observations a wider stroke (~1.5×) so obs/model/median differ by width + stacking, not hue alone; historical stays dashed. Verify in greyscale.
- **Open vs closed stations**: blue vs red dot only (`map.css:130,226`). Closed markers become hollow rings (border, transparent fill).
- **Pipeline done vs stale**: green vs yellow border only (`pipeline.css:48-54`). Stale gets a dashed border, done stays solid.
- `.error-input` (§4) pairs the red border with `aria-invalid` and a message, not colour alone.

### 12. Gaps render as gaps in multi-series charts (TRU-4)

- `hydrographView` paints missing runs as faint red spans (`plot.js:594-633`); `multiSeriesView` only breaks the hairline, invisible at that width.
- Port the missing-run spans to `multiSeriesView` for the **observations** series (model simulations have no gaps).

### 13. Map tile failure is distinguishable (ERR-5)

- Backend returns a 200 black 1×1 on failure (`api.py:93-100`); Leaflet stretches it into flat black patches indistinguishable from the dark basemap, and HTTP 200 means `tileerror` never fires.
- Change to an HTTP 404 on fetch failure; set Leaflet `errorTileUrl` (`stations.js:718`) to a vendored 256×256 placeholder (dark grey, subtle diagonal hatch) under `static/assets/`.
- Update the backend tile-route tests.

### 14. Comma-decimal input (INP-6)

- `type="number"` + `Number()`/`valueAsNumber` rejects `1,5` for FR-CA users; no locale handling anywhere.
- Switch `createSlider`'s number input (and SCE hyperparameter inputs) to `type="text" inputmode="decimal"` with a shared `parseNumber` in `utils/misc.js` accepting comma decimals and space grouping; echo the parsed value into the field on commit.
- `formatNumber` (`misc.js:87-89`, hard-coded `en-US`) becomes locale-aware: decimal comma + space grouping in French.

### 15. Small defects surfaced by the audit

- `convert_for_json` (`utils/api.py:262-281`): NaN/±inf scrubbing only covers `pl.DataFrame` branches; a bare Python float NaN in a dict would kill the whole message client-side at `JSON.parse`. Scrub scalar floats too.
- `--font-title` is referenced (`template.css:81,149`, `elements.css:148`) but never defined — silently falls back to the browser default. Define it or drop the three usages.

---

## Implementation order

1. Tier 1 §1–2 (status surface + connection) — everything else's error paths land here.
2. Tier 1 §3–5 (tz, input, focus) — independent, small.
3. Tier 2 §6 (action safety) — builds on the notice/undo machinery from §1.
4. Tier 2 §7–10, then Tier 3 — largely independent of each other.

## Testing & verification

Per project rules: 100 % Python coverage, every frontend functionality e2e-covered.

- **Unit (Python)**: `tests/unit/utils/test_api.py` — scalar NaN/inf scrub; `tests/unit/test_api.py` — tile route 404s on failure.
- **e2e (Playwright)**: status notice appears on a forced server error and persists until dismissed; Retry re-requests; Reconnect chip + button after killing the ws; Reset-all countdown cancels; Clear-bench Undo restores attempts; import-over-bench confirm; CSV export contains the metadata header; number input keeps invalid text and flags it; Escape closes the station dialog; focus ring present on tabbed button.
- **Static analysis**: `make static-analysis` clean.
- **Manual**: `holmes run`, walk the pipeline once per language (all new strings in FR and EN); kill the server mid-calibration and confirm the notice; check axis dates are calendar-correct (July 1996 flood peaks on the 20th).
- **Screenshots**: `make screenshots` at the end — the status chip and label changes appear in doc screenshots; refresh affected scenes.

## Waivers (recorded per GOV-2)

Not applicable to a locally-served educational tool (no operators, no alarms, no unattended operation):

- Offline/PWA tiers: DEG-1/3/6, BLD-2/3.
- Telemetry & correction logging: §K (OBS).
- Alert catalogue & rate limiting: §G (the app has no alarms).
- Drills: DEG-5; clock-skew banner: TIM-6.
- Cancel on read loads: LAT-4 — supersession/navigation is the cancel.
- Chart value readout: absent feature, not a violation; deliberately not added.
