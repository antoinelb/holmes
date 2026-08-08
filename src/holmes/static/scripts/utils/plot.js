import { formatNumber, frenchLocale } from "./misc.js";
import { language, t } from "./text.js";

// holmes-style timeseries: grid lines + bare tick labels (no spines), a
// hairline series path (or daily bars with mark: "bar"), and x-axis brush
// zoom with double-click reset; data is [{date: Date, [field]: number|null}]
export function hydrographView(
  _svg,
  data,
  colour,
  {
    field = "streamflow",
    label = t("Streamflow (mm)", "Débit (mm)"),
    mark = "line",
    xLabels = true,
  } = {},
) {
  const width = _svg.clientWidth;
  const height = _svg.clientHeight;
  const svg = d3.select(_svg);
  svg.selectAll("*").remove();
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  // absolute pixel positions of the plot area edges (holmes convention);
  // the left margin only holds a two-line title when there is one, and a
  // chart without tick labels gives the bottom margin back to the plot
  const boundaries = {
    l: label ? 62 : 32,
    r: width - 25,
    t: 5,
    b: height - (xLabels ? 20 : 5),
  };

  const xScale = d3
    .scaleTime()
    .domain(d3.extent(data, (d) => d.date))
    .range([boundaries.l, boundaries.r]);
  const values = data.filter((d) => d[field] !== null);
  const yScale = d3
    .scaleLinear()
    // bars grow from zero, a line spans its own extent
    .domain([
      mark === "bar" ? 0 : d3.min(values, (d) => d[field]),
      d3.max(values, (d) => d[field]),
    ])
    .range([boundaries.b, boundaries.t]);
  const line = d3
    .line()
    // gap-filled days are null: break the line rather than bridge gaps
    .defined((d) => d[field] !== null)
    .x((d) => xScale(d.date))
    .y((d) => yScale(d[field]));

  const yTickValues = fittingTicks(yScale, boundaries.b - boundaries.t);

  // bars are one filled path holding a box per day, not one rect per day: a
  // full record is ~30k days on a ~600px chart, so the rects stacked ~50 deep
  // per pixel column and their nodes slowed every later layout. Mirrors
  // `line` — a generator applied to one element, re-applied on zoom
  const bars =
    mark === "bar"
      ? (path, scale) =>
          path.attr("d", barPath(data, scale, yScale, boundaries.b, field))
      : null;

  gridView(svg, xScale, yScale, yTickValues);
  axesView(svg, xScale, yScale, boundaries, label, yTickValues, xLabels);
  marksView(
    svg,
    data,
    line,
    bars,
    xScale,
    boundaries,
    colour,
    `${_svg.id}-clip`,
    field,
  );
  brushView(svg, xScale, boundaries, line, bars);
}

// several timeseries on shared x/y scales: an optional warmup band and dashed
// reference guide under the grid, then one hairline path per series drawn
// models → median → observations so the observations read on top; brush zoom
// re-maps every path with a single shared line generator
// series: [{key, kind: "model"|"median"|"observations", colour, points}]
export function multiSeriesView(
  _svg,
  series,
  {
    xType = "time",
    label = null,
    xLabels = true,
    warmupEnd = null,
    reference = null,
    showPoints = false,
  } = {},
) {
  const width = _svg.clientWidth;
  const height = _svg.clientHeight;
  const svg = d3.select(_svg);
  svg.selectAll("*").remove();
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  const boundaries = {
    l: label ? 62 : 32,
    r: width - 25,
    t: 5,
    b: height - (xLabels ? 20 : 5),
  };

  const xValues = series.flatMap((s) => s.points.map((p) => p.x));
  const xScale = (xType === "linear" ? d3.scaleLinear() : d3.scaleTime())
    .domain(d3.extent(xValues))
    .range([boundaries.l, boundaries.r]);
  // the warmup period carries the models' spin-up transients, which are often
  // an order of magnitude off; excluding them keeps the domain readable and
  // lets the clip cut the spikes off at the top
  const finite = series.flatMap((s) =>
    s.points.filter((p) => p.y !== null && p.y !== undefined),
  );
  const afterWarmup =
    warmupEnd === null ? finite : finite.filter((p) => p.x >= warmupEnd);
  // a period shorter than the warmup leaves nothing to scale on
  const yValues = (afterWarmup.length ? afterWarmup : finite).map((p) => p.y);
  // the guide must sit inside the plot, so widen the domain to reach it
  if (reference !== null) {
    yValues.push(reference);
  }
  const yScale = d3
    .scaleLinear()
    .domain(d3.extent(yValues))
    .range([boundaries.b, boundaries.t])
    .nice();
  const line = d3
    .line()
    // a null point breaks the line rather than bridging the gap
    .defined((d) => d.y !== null && d.y !== undefined)
    .x((d) => xScale(d.x))
    .y((d) => yScale(d.y));

  const yTickValues = fittingTicks(yScale, boundaries.b - boundaries.t);

  // bottom to top: warmup band, reference guide, grid, axes, then series
  if (warmupEnd !== null) {
    warmupView(svg, xScale, boundaries, warmupEnd);
  }
  if (reference !== null) {
    referenceView(svg, xScale, yScale, boundaries, reference);
  }
  gridView(svg, xScale, yScale, yTickValues);
  axesView(
    svg,
    xScale,
    yScale,
    boundaries,
    label,
    yTickValues,
    xLabels,
    (scale) => multiXAxis(scale, xType),
  );
  seriesView(
    svg,
    series,
    line,
    boundaries,
    `${_svg.id}-clip`,
    showPoints ? { xScale, yScale } : null,
  );
  legendView(svg, series, boundaries);
  multiBrushView(svg, xScale, boundaries, line, xType, showPoints);
}

// categorical dot profile: one row per metric with a faint gridline and an
// end-anchored label, one faint dot per model plus a solid median dot drawn
// on top (the median reads through colour and stacking, like the series
// palette), and a dashed vertical guide at the optimal value
// rows: [{key, label, dots: [{model, value}], median: number|null}]
export function dotProfileView(_svg, rows, { reference = 1 } = {}) {
  const width = _svg.clientWidth;
  const height = _svg.clientHeight;
  const svg = d3.select(_svg);
  svg.selectAll("*").remove();
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  // the left margin holds the metric labels rather than a rotated title
  const boundaries = { l: 170, r: width - 25, t: 5, b: height - 20 };

  const finite = rows
    .flatMap((row) => [...row.dots.map((d) => d.value), row.median])
    .filter((v) => Number.isFinite(v));
  // the guide must sit inside the plot, so widen the domain to reach it
  const xScale = d3
    .scaleLinear()
    .domain(d3.extent([...finite, reference]))
    .range([boundaries.l, boundaries.r])
    .nice();
  const rowHeight = (boundaries.b - boundaries.t) / rows.length;
  const rowY = (i) => boundaries.t + (i + 0.5) * rowHeight;

  // per-row gridlines and labels stand in for a categorical y axis
  svg
    .selectAll(".grid-horizontal")
    .data(rows)
    .join("line")
    .attr("class", "grid-horizontal")
    .attr("x1", boundaries.l)
    .attr("x2", boundaries.r)
    .attr("y1", (_, i) => rowY(i))
    .attr("y2", (_, i) => rowY(i));
  svg
    .selectAll(".dot-profile-label")
    .data(rows)
    .join("text")
    .attr("class", "dot-profile-label")
    .attr("x", boundaries.l - 8)
    .attr("y", (_, i) => rowY(i) + 4)
    .attr("text-anchor", "end")
    .text((row) => row.label);

  // dashed so the guide never reads as a gridline or an axis spine
  svg
    .append("line")
    .attr("class", "reference-line red")
    .attr("stroke-dasharray", "4 3")
    .attr("x1", xScale(reference))
    .attr("x2", xScale(reference))
    .attr("y1", boundaries.t)
    .attr("y2", boundaries.b);
  svg
    .append("text")
    .attr("class", "reference-label red")
    .attr("x", xScale(reference) + 4)
    .attr("y", boundaries.t + 11)
    .text("Optimal");

  svg
    .append("g")
    .attr("class", "x-axis")
    .attr("transform", `translate(0, ${boundaries.b})`)
    .call(
      d3
        .axisBottom(xScale)
        .ticks(5)
        .tickSize(0)
        .tickFormat((x) => formatNumber(x)),
    )
    .call((g) => g.select(".domain").remove());

  // model dots first, the median last so it paints over any tie
  svg
    .selectAll(".series-point--model")
    .data(
      rows.flatMap((row, i) =>
        row.dots
          .filter((d) => Number.isFinite(d.value))
          .map((d) => ({ ...d, y: rowY(i) })),
      ),
    )
    .join("circle")
    .attr("class", "series-point series-point--model")
    .attr("data-model", (d) => d.model)
    .attr("r", 4)
    .attr("cx", (d) => xScale(d.value))
    .attr("cy", (d) => d.y);
  svg
    .selectAll(".series-point--median")
    .data(
      rows
        .map((row, i) => ({ value: row.median, y: rowY(i) }))
        .filter((d) => Number.isFinite(d.value)),
    )
    .join("circle")
    .attr("class", "series-point series-point--median")
    .attr("r", 4)
    .attr("cx", (d) => xScale(d.value))
    .attr("cy", (d) => d.y);
}

// annual regime ensemble: day-of-year x axis labelled by month, one hairline
// per climate member under one median per hydro model under the complete
// median, plus a dashed historical reference; brush zoom like multiSeriesView
// series: [{key, kind: "member"|"model"|"historical"|"median", model?,
//           colour?, points}]
export function regimeView(_svg, series, { label = null } = {}) {
  const width = _svg.clientWidth;
  const height = _svg.clientHeight;
  const svg = d3.select(_svg);
  svg.selectAll("*").remove();
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  const boundaries = {
    l: label ? 62 : 32,
    r: width - 25,
    t: 5,
    b: height - 20,
  };

  const xScale = d3
    .scaleLinear()
    .domain([1, 365])
    .range([boundaries.l, boundaries.r]);
  const yValues = series.flatMap((s) =>
    s.points.filter((p) => p.y !== null && p.y !== undefined).map((p) => p.y),
  );
  const yScale = d3
    .scaleLinear()
    .domain([0, d3.max(yValues)])
    .range([boundaries.b, boundaries.t])
    .nice();
  const line = d3
    .line()
    // a null point breaks the line rather than bridging the gap
    .defined((d) => d.y !== null && d.y !== undefined)
    .x((d) => xScale(d.x))
    .y((d) => yScale(d.y));

  const yTickValues = fittingTicks(yScale, boundaries.b - boundaries.t);

  gridView(svg, xScale, yScale, yTickValues);
  axesView(
    svg,
    xScale,
    yScale,
    boundaries,
    label,
    yTickValues,
    true,
    regimeXAxis,
  );
  regimeSeriesView(svg, series, line, boundaries, `${_svg.id}-clip`);
  regimeLegendView(svg, series, boundaries);
  regimeBrushView(svg, xScale, boundaries, line);
}

// all indicators on one figure: five categorical columns sharing a split
// (polylinear) y scale broken at `breakValue`, so the low-flow indicators
// keep `lowFraction` of the height instead of being crushed by the freshet;
// dots are one per (hydro model, member), the ticks the ensemble median and
// the historical reference
// columns: [{key, label, dots: [{model, value}], median, historical}]
export function splitColumnView(
  _svg,
  columns,
  {
    breakValue = 2,
    lowFraction = 0.58,
    historicalLabel = t("historical", "historique"),
  } = {},
) {
  const width = _svg.clientWidth;
  const height = _svg.clientHeight;
  const svg = d3.select(_svg);
  svg.selectAll("*").remove();
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  const boundaries = { l: 40, r: width - 25, t: 8, b: height - 20 };

  const finite = columns
    .flatMap((c) => [...c.dots.map((d) => d.value), c.median, c.historical])
    .filter((v) => Number.isFinite(v));
  // dots have no slope to distort, which is why the break is safe here; the
  // top of the high segment is niced so its ticks land on round values
  const [, yMax] = d3.nice(breakValue, Math.max(d3.max(finite), breakValue), 4);
  const yBreak = boundaries.b - lowFraction * (boundaries.b - boundaries.t);
  const yScale = d3
    .scaleLinear()
    .domain([0, breakValue, yMax])
    .range([boundaries.b, yBreak, boundaries.t]);
  const yTickValues = [
    ...d3.ticks(0, breakValue, 4),
    ...d3.ticks(breakValue, yMax, 3).filter((v) => v > breakValue),
  ];

  svg
    .selectAll(".grid-horizontal")
    .data(yTickValues)
    .join("line")
    .attr("class", "grid-horizontal")
    .attr("x1", boundaries.l)
    .attr("x2", boundaries.r)
    .attr("y1", (d) => yScale(d))
    .attr("y2", (d) => yScale(d));
  svg
    .append("g")
    .attr("class", "y-axis")
    .attr("transform", `translate(${boundaries.l}, 0)`)
    .call(
      d3
        .axisLeft(yScale)
        .tickValues(yTickValues)
        .tickSize(0)
        .tickFormat((x) => formatNumber(x)),
    )
    .call((g) => g.select(".domain").remove());
  breakGlyphView(svg, boundaries, yBreak);

  const colWidth = (boundaries.r - boundaries.l) / columns.length;
  const colX = (i) => boundaries.l + (i + 0.5) * colWidth;
  svg
    .selectAll(".dot-profile-label")
    .data(columns)
    .join("text")
    .attr("class", "dot-profile-label")
    .attr("x", (_, i) => colX(i))
    .attr("y", boundaries.b + 14)
    .attr("text-anchor", "middle")
    .text((c) => c.label);

  // dots first, ticks last so the references paint over the cloud; each dot
  // is nudged inside its column so members do not stack on one vertical
  // line. the golden-ratio stride is a deterministic scatter that fills the
  // whole band uniformly and interleaves the models rather than grouping them
  const band = colWidth * 0.25;
  svg
    .selectAll(".series-point--member")
    .data(
      columns.flatMap((c, i) =>
        c.dots
          .filter((d) => Number.isFinite(d.value))
          .map((d, j) => ({
            ...d,
            x: colX(i) + (((j * 0.618033988749895) % 1) - 0.5) * band,
          })),
      ),
    )
    .join("circle")
    .attr("class", "series-point series-point--member")
    .attr("data-model", (d) => d.model)
    .attr("r", 3)
    .attr("cx", (d) => d.x)
    .attr("cy", (d) => yScale(d.value));
  svg
    .selectAll(".series-tick--historical")
    .data(
      columns
        .map((c, i) => ({ value: c.historical, i }))
        .filter((d) => Number.isFinite(d.value)),
    )
    .join("line")
    .attr("class", "series-tick series-tick--historical green")
    .attr("stroke-dasharray", "4 3")
    .attr("x1", (d) => colX(d.i) - 16)
    .attr("x2", (d) => colX(d.i) + 16)
    .attr("y1", (d) => yScale(d.value))
    .attr("y2", (d) => yScale(d.value));
  svg
    .selectAll(".series-tick--median")
    .data(
      columns
        .map((c, i) => ({ value: c.median, i }))
        .filter((d) => Number.isFinite(d.value)),
    )
    .join("line")
    .attr("class", "series-tick series-tick--median")
    .attr("x1", (d) => colX(d.i) - 16)
    .attr("x2", (d) => colX(d.i) + 16)
    .attr("y1", (d) => yScale(d.value))
    .attr("y2", (d) => yScale(d.value));

  splitLegendView(svg, boundaries, historicalLabel);
}

// d3 treats a tick count as a hint and can return half again as many, which
// stacks labels on a short chart; keep its "nice" values but drop every nth
// so at most one lands per label-height of plot area
function fittingTicks(yScale, plotHeight) {
  const maxTicks = Math.min(5, Math.max(2, Math.floor(plotHeight / 14)));
  const candidates = yScale.ticks(maxTicks);
  const stride = Math.ceil(candidates.length / maxTicks);
  return candidates.filter((_, i) => i % stride === 0);
}

function gridView(svg, xScale, yScale, yTickValues) {
  svg
    .selectAll(".grid-horizontal")
    .data(yTickValues)
    .join("line")
    .attr("class", "grid-horizontal")
    .attr("x1", xScale.range()[0])
    .attr("x2", xScale.range()[1])
    .attr("y1", (d) => yScale(d))
    .attr("y2", (d) => yScale(d));
}

function axesView(
  svg,
  xScale,
  yScale,
  boundaries,
  label,
  yTickValues,
  xLabels,
  xAxisGen = xAxis,
) {
  // stacked charts share one x scale, so only the bottom one is labelled;
  // updateChart's select(".x-axis") is a no-op when it is absent
  if (xLabels) {
    svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${boundaries.b})`)
      .call(xAxisGen(xScale))
      .call((g) => g.select(".domain").remove());
  }
  svg
    .append("g")
    .attr("class", "y-axis")
    .attr("transform", `translate(${boundaries.l}, 0)`)
    .call(
      d3
        .axisLeft(yScale)
        .tickValues(yTickValues)
        .tickSize(0)
        .tickFormat((x) => formatNumber(x)),
    )
    .call((g) => g.select(".domain").remove());
  // a null label leaves the margin empty so both columns still align
  if (label) {
    titleView(svg, boundaries, label);
  }
}

// the title is rotated, so each line reads as its own vertical column;
// splitting the units off keeps the longest line short enough for a chart
// that only has room for one
function titleView(svg, boundaries, label) {
  const [name, units] = splitLabel(label);
  const title = svg
    .append("text")
    .attr(
      "transform",
      `translate(11, ${(boundaries.t + boundaries.b) / 2}) rotate(-90)`,
    )
    .attr("class", "axis-title")
    .attr("text-anchor", "middle");
  title.append("tspan").attr("x", 0).text(name);
  if (units) {
    title.append("tspan").attr("x", 0).attr("dy", "1.25em").text(units);
  }
}

function splitLabel(label) {
  const match = label.match(/^(.*?)\s*(\(.*\))$/);
  return match ? [match[1], match[2]] : [label, null];
}

function xAxis(xScale) {
  return d3.axisBottom(xScale).ticks(5).tickSize(0).tickFormat(tickDate);
}

// d3's default multi-scale format, but with abbreviated months (%b not %B);
// French month names come from the frenchLocale rather than d3's default
function tickDate(date) {
  const format =
    d3.timeDay(date) < date
      ? "%H:%M"
      : d3.timeMonth(date) < date
        ? "%b %d"
        : d3.timeYear(date) < date
          ? "%b"
          : "%Y";
  return (
    language === "fr" ? frenchLocale.format(format) : d3.timeFormat(format)
  )(date);
}

function marksView(
  svg,
  data,
  line,
  bars,
  xScale,
  boundaries,
  colour,
  clipId,
  field,
) {
  // the clip keeps the zoomed marks inside the plot area; its id must be
  // unique per chart since several coexist on the page
  svg
    .append("defs")
    .append("clipPath")
    .attr("id", clipId)
    .append("rect")
    .attr("x", boundaries.l)
    .attr("y", boundaries.t)
    .attr("width", boundaries.r - boundaries.l)
    .attr("height", boundaries.b - boundaries.t);
  const content = svg
    .append("g")
    .attr("class", "chart-content")
    .attr("clip-path", `url(#${clipId})`);
  // missing data shows as faint red spans, like the experiment figures
  content
    .selectAll(".missing-rect")
    .data(missingRuns(data, field))
    .join("rect")
    .attr("class", "missing-rect red")
    .attr("opacity", 0.2)
    .attr("y", boundaries.t)
    .attr("height", boundaries.b - boundaries.t)
    .call(placeMissingRects, xScale);
  if (bars) {
    content
      .append("path")
      .attr("class", `bar-path ${colour}`)
      .call(bars, xScale);
  } else {
    content
      .append("path")
      .attr("class", `streamflow-line ${colour}`)
      .datum(data)
      .attr("d", line);
  }
}

// contiguous null runs as inclusive [start, end] date spans
function missingRuns(data, field) {
  const runs = [];
  let current = null;
  for (const d of data) {
    if (d[field] !== null) {
      current = null;
    } else if (current === null) {
      current = { start: d.date, end: d.date };
      runs.push(current);
    } else {
      current.end = d.date;
    }
  }
  return runs;
}

// works on selections and transitions; single days keep a 1px presence
// (the experiment figures use a rule for those)
function placeMissingRects(rects, xScale) {
  rects
    .attr("x", (d) => xScale(d.start))
    .attr("width", (d) => Math.max(xScale(d.end) - xScale(d.start), 1));
}

// one box per day — bottom-left, top-left, top-right, bottom-right — as its
// own subpath; the fill closes each along the baseline, so no explicit Z is
// needed and null days simply leave a gap
function barPath(data, xScale, yScale, baseline, field) {
  const width = barWidth(xScale);
  const parts = [];
  for (const d of data) {
    if (d[field] === null) {
      continue;
    }
    const left = xScale(d.date).toFixed(1);
    const right = (xScale(d.date) + width).toFixed(1);
    const top = yScale(d[field]).toFixed(1);
    parts.push(`M${left},${baseline}V${top}H${right}V${baseline}`);
  }
  return parts.join("");
}

// every day is the same width, so it is measured once per draw rather than
// per bar; below a pixel the boxes overlap into a solid block, which is what
// a decades-long record should read as
function barWidth(xScale) {
  const [start] = xScale.domain();
  return Math.max(xScale(d3.timeDay.offset(start, 1)) - xScale(start), 1);
}

function brushView(svg, xScale, boundaries, line, bars) {
  const xDomain = xScale.domain();
  const brush = d3
    .brushX()
    .extent([
      [boundaries.l, boundaries.t],
      [boundaries.r, boundaries.b],
    ])
    .on("end", (event) => {
      // clearing the brush below re-fires "end" with a null selection
      if (!event.selection) {
        return;
      }
      const [x0, x1] = event.selection;
      xScale.domain([xScale.invert(x0), xScale.invert(x1)]);
      brushGroup.call(brush.move, null);
      updateChart(svg, xScale, line, bars);
    });
  const brushGroup = svg.append("g").attr("class", "brush").call(brush);
  svg.on("dblclick", () => {
    xScale.domain(xDomain);
    updateChart(svg, xScale, line, bars);
  });
}

// zoom re-maps x on the existing DOM with a transition instead of redrawing
function updateChart(svg, xScale, line, bars) {
  const t = svg.transition().duration(750);
  const axis = svg.select(".x-axis");
  axis.transition(t).call(xAxis(xScale));
  // the axis re-inserts its spine on every call
  axis.select(".domain").remove();
  svg.selectAll(".missing-rect").transition(t).call(placeMissingRects, xScale);
  // bar boxes change width with the zoom, so the path is regenerated rather
  // than interpolated: tweening a ~30k-segment `d` costs far more than
  // rebuilding it
  if (bars) {
    svg.select(".bar-path").call(bars, xScale);
  }
  svg.select(".streamflow-line").transition(t).attr("d", line);
}

// linear axes carry counts/indices, so keep the ticks whole and format them
// like the y axis; time axes reuse the multi-scale date format
function multiXAxis(xScale, xType) {
  const axis = d3.axisBottom(xScale).tickSize(0);
  if (xType === "linear") {
    const integers = xScale.ticks(5).filter((t) => Number.isInteger(t));
    return integers.length
      ? axis.tickValues(integers).tickFormat((x) => formatNumber(x))
      : axis.ticks(5).tickFormat((x) => formatNumber(x));
  }
  return axis.ticks(5).tickFormat(tickDate);
}

// shaded [xMin, warmupEnd] band; its end value rides as the datum so the zoom
// update can re-map the width and hide it once it falls out of view
function warmupView(svg, xScale, boundaries, warmupEnd) {
  svg
    .append("rect")
    .attr("class", "warmup-rect")
    .attr("y", boundaries.t)
    .attr("height", boundaries.b - boundaries.t)
    .datum(warmupEnd)
    .call(placeWarmup, xScale);
  svg
    .append("text")
    .attr("class", "warmup-label")
    .attr("y", boundaries.t + 12)
    .attr("text-anchor", "middle")
    .datum(warmupEnd)
    .text(t("warmup", "initialisation"))
    .call(placeWarmupLabel, xScale);
}

// works on selections and transitions; the band always starts at the plot's
// left edge and hides entirely once its end sits before the visible domain
function placeWarmup(rects, xScale) {
  const [x0] = xScale.range();
  const [d0] = xScale.domain();
  rects
    .attr("x", x0)
    .attr("width", (d) => Math.max(xScale(d) - x0, 0))
    .attr("display", (d) => (d < d0 ? "none" : null));
}

// centred in the visible part of the band; hidden with it, and also once the
// band is too narrow for the word to fit
function placeWarmupLabel(labels, xScale) {
  const [x0] = xScale.range();
  const [d0] = xScale.domain();
  labels
    .attr("x", (d) => (x0 + Math.max(xScale(d), x0)) / 2)
    .attr("display", (d) => (d < d0 || xScale(d) - x0 < 45 ? "none" : null));
}

// the optimal-score guide; both endpoints and its y are fixed, so the zoom
// update leaves it untouched
function referenceView(svg, xScale, yScale, boundaries, reference) {
  const y = yScale(reference);
  svg
    .append("line")
    .attr("class", "reference-line red")
    .attr("x1", xScale.range()[0])
    .attr("x2", xScale.range()[1])
    .attr("y1", y)
    .attr("y2", y);
  // left-anchored: the legend owns the top-right corner, and the label is
  // pushed below the guide when it would otherwise sit above the plot
  svg
    .append("text")
    .attr("class", "reference-label red")
    .attr("x", xScale.range()[0] + 4)
    .attr("y", y - boundaries.t < 12 ? y + 11 : y - 3)
    .text("Optimal");
}

// kinds present in the chart, as a stack of swatch + label rows in the plot's
// top-right corner; kinds are the only thing the caller can style, so one row
// per kind describes every path without listing 20 models
const legendLabels = {
  model: "simulations",
  median: t("median", "médiane"),
  observations: "observations",
};

function legendView(svg, series, boundaries) {
  // the first series of each kind supplies the swatch's colour class, and may
  // override the label (a lone model reads as "simulation", not "median")
  const kinds = [];
  for (const s of series) {
    if (s.kind in legendLabels && !kinds.some((k) => k.kind === s.kind)) {
      kinds.push({
        kind: s.kind,
        colour: s.colour,
        label: s.label ?? legendLabels[s.kind],
      });
    }
  }
  if (kinds.length === 0) {
    return;
  }
  const rows = svg
    .append("g")
    .attr("class", "legend")
    .selectAll("g")
    .data(kinds)
    .join("g")
    .attr(
      "transform",
      (_, i) => `translate(${boundaries.r}, ${boundaries.t + 12 + i * 21})`,
    );
  rows
    .append("line")
    .attr(
      "class",
      (k) =>
        `series-line series-line--${k.kind}${k.colour ? ` ${k.colour}` : ""}`,
    )
    .attr("x1", -18)
    .attr("x2", 0)
    .attr("y1", -4)
    .attr("y2", -4);
  rows
    .append("text")
    .attr("class", "legend-label")
    .attr("x", -22)
    .attr("text-anchor", "end")
    .text((k) => k.label);
}

// one clipped path per series so the zoom stays inside the plot; models are
// drawn first and observations last so the observed series reads on top, and
// each series object is the datum so the shared line generator can re-run
function seriesView(svg, series, line, boundaries, clipId, scales) {
  svg
    .append("defs")
    .append("clipPath")
    .attr("id", clipId)
    .append("rect")
    .attr("x", boundaries.l)
    .attr("y", boundaries.t)
    .attr("width", boundaries.r - boundaries.l)
    .attr("height", boundaries.b - boundaries.t);
  // the median is the ensemble's answer, so it reads over the observations
  const order = { model: 0, observations: 1, median: 2 };
  const sorted = [...series].sort((a, b) => order[a.kind] - order[b.kind]);
  const content = svg
    .append("g")
    .attr("class", "chart-content")
    .attr("clip-path", `url(#${clipId})`);
  content
    .selectAll("path")
    .data(sorted)
    .join("path")
    .attr(
      "class",
      (s) =>
        `series-line series-line--${s.kind}${s.colour ? ` ${s.colour}` : ""}`,
    )
    // model-backed series get a stable hook for hover cross-highlighting; a
    // lone model is drawn as the median, so the hook cannot key off the kind
    .attr("data-model", (s) => s.model ?? null)
    // SVG has no z-index, so a hover raises a path by moving it in the DOM;
    // this records the paint order it has to be restored to
    .attr("data-order", (_, i) => i)
    .attr("d", (s) => line(s.points));
  if (scales) {
    seriesPointsView(content, sorted, scales);
  }
}

// markers for a short series, where a line of one or two segments reads as
// nothing at all; each circle carries its series so the zoom can re-place it
function seriesPointsView(content, sorted, { xScale, yScale }) {
  content
    .selectAll("circle")
    .data(
      sorted.flatMap((s) =>
        s.points
          .filter((p) => p.y !== null && p.y !== undefined)
          .map((p) => ({ ...p, series: s })),
      ),
    )
    .join("circle")
    .attr(
      "class",
      (d) =>
        `series-point series-point--${d.series.kind}${
          d.series.colour ? ` ${d.series.colour}` : ""
        }`,
    )
    .attr("data-model", (d) => d.series.model ?? null)
    .attr("r", 4)
    .attr("cx", (d) => xScale(d.x))
    .attr("cy", (d) => yScale(d.y));
}

function multiBrushView(svg, xScale, boundaries, line, xType, showPoints) {
  const xDomain = xScale.domain();
  const brush = d3
    .brushX()
    .extent([
      [boundaries.l, boundaries.t],
      [boundaries.r, boundaries.b],
    ])
    .on("end", (event) => {
      // clearing the brush below re-fires "end" with a null selection
      if (!event.selection) {
        return;
      }
      const [x0, x1] = event.selection;
      xScale.domain([xScale.invert(x0), xScale.invert(x1)]);
      brushGroup.call(brush.move, null);
      updateMultiChart(svg, xScale, line, xType, showPoints);
    });
  const brushGroup = svg.append("g").attr("class", "brush").call(brush);
  svg.on("dblclick", () => {
    xScale.domain(xDomain);
    updateMultiChart(svg, xScale, line, xType, showPoints);
  });
}

// the reference line is domain-fixed, so only the x axis, warmup band and the
// series paths re-map; each path re-runs the one shared line generator
function updateMultiChart(svg, xScale, line, xType, showPoints) {
  const t = svg.transition().duration(750);
  const axis = svg.select(".x-axis");
  axis.transition(t).call(multiXAxis(xScale, xType));
  // the axis re-inserts its spine on every call
  axis.select(".domain").remove();
  svg.selectAll(".warmup-rect").transition(t).call(placeWarmup, xScale);
  svg.selectAll(".warmup-label").transition(t).call(placeWarmupLabel, xScale);
  // the legend swatches are .series-line too, so only the clipped paths move
  svg
    .selectAll(".chart-content .series-line")
    .transition(t)
    .attr("d", (s) => line(s.points));
  if (showPoints) {
    svg
      .selectAll(".series-point")
      .transition(t)
      .attr("cx", (d) => xScale(d.x));
  }
}

// first day of each month in the fixed non-leap year the day-of-year axis
// lives in (the backend's Feb 29 -> 28 remap targets the same year)
const monthStarts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
const monthNames = t(
  "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
  "jan fév mar avr mai jun jul aoû sep oct nov déc",
).split(" ");

// month-start ticks restricted to the visible domain; a deep zoom keeps too
// few of them, so it falls back to plain day-of-year numbers
function regimeXAxis(xScale) {
  const [d0, d1] = xScale.domain();
  const visible = monthStarts.filter((d) => d >= d0 && d <= d1);
  const axis = d3.axisBottom(xScale).tickSize(0);
  if (visible.length < 2) {
    return axis.ticks(5).tickFormat((x) => formatNumber(x));
  }
  return axis
    .tickValues(visible)
    .tickFormat((d) => monthNames[monthStarts.indexOf(d)]);
}

// like seriesView but with the projection stacking: members under model
// medians under the historical reference under the complete median, and the
// historical line dashed (an attribute, mirroring dotProfileView's guide,
// rather than another CSS variant)
function regimeSeriesView(svg, series, line, boundaries, clipId) {
  svg
    .append("defs")
    .append("clipPath")
    .attr("id", clipId)
    .append("rect")
    .attr("x", boundaries.l)
    .attr("y", boundaries.t)
    .attr("width", boundaries.r - boundaries.l)
    .attr("height", boundaries.b - boundaries.t);
  const order = { member: 0, model: 1, historical: 2, median: 3 };
  const sorted = [...series].sort((a, b) => order[a.kind] - order[b.kind]);
  const content = svg
    .append("g")
    .attr("class", "chart-content")
    .attr("clip-path", `url(#${clipId})`);
  content
    .selectAll("path")
    .data(sorted)
    .join("path")
    .attr(
      "class",
      (s) =>
        `series-line series-line--${s.kind}${s.colour ? ` ${s.colour}` : ""}`,
    )
    .attr("stroke-dasharray", (s) => (s.kind === "historical" ? "4 3" : null))
    // model-backed series get a stable hook for hover cross-highlighting;
    // the complete median and the historical reference carry none, so a
    // hover never dims or recolours them
    .attr("data-model", (s) => s.model ?? null)
    // SVG has no z-index, so a hover raises a path by moving it in the DOM;
    // this records the paint order it has to be restored to
    .attr("data-order", (_, i) => i)
    .attr("d", (s) => line(s.points));
}

const regimeLegendLabels = {
  member: t("members", "membres"),
  model: t("model medians", "médianes des modèles"),
  median: t("median", "médiane"),
  historical: t("historical", "historique"),
};

// one row per kind present, like legendView; kept separate because the kinds
// (and the dashed historical swatch) are projection-specific
function regimeLegendView(svg, series, boundaries) {
  const kinds = [];
  for (const s of series) {
    if (s.kind in regimeLegendLabels && !kinds.some((k) => k.kind === s.kind)) {
      kinds.push({
        kind: s.kind,
        colour: s.colour,
        label: s.label ?? regimeLegendLabels[s.kind],
      });
    }
  }
  if (kinds.length === 0) {
    return;
  }
  const rows = svg
    .append("g")
    .attr("class", "legend")
    .selectAll("g")
    .data(kinds)
    .join("g")
    .attr(
      "transform",
      (_, i) => `translate(${boundaries.r}, ${boundaries.t + 12 + i * 21})`,
    );
  rows
    .append("line")
    .attr(
      "class",
      (k) =>
        `series-line series-line--${k.kind}${k.colour ? ` ${k.colour}` : ""}`,
    )
    .attr("stroke-dasharray", (k) =>
      k.kind === "historical" ? "4 3" : null,
    )
    .attr("x1", -18)
    .attr("x2", 0)
    .attr("y1", -4)
    .attr("y2", -4);
  rows
    .append("text")
    .attr("class", "legend-label")
    .attr("x", -22)
    .attr("text-anchor", "end")
    .text((k) => k.label);
}

function regimeBrushView(svg, xScale, boundaries, line) {
  const xDomain = xScale.domain();
  const brush = d3
    .brushX()
    .extent([
      [boundaries.l, boundaries.t],
      [boundaries.r, boundaries.b],
    ])
    .on("end", (event) => {
      // clearing the brush below re-fires "end" with a null selection
      if (!event.selection) {
        return;
      }
      const [x0, x1] = event.selection;
      xScale.domain([xScale.invert(x0), xScale.invert(x1)]);
      brushGroup.call(brush.move, null);
      updateRegimeChart(svg, xScale, line);
    });
  const brushGroup = svg.append("g").attr("class", "brush").call(brush);
  svg.on("dblclick", () => {
    xScale.domain(xDomain);
    updateRegimeChart(svg, xScale, line);
  });
}

// its own updater (not updateMultiChart) so the zoomed axis keeps the month
// labels instead of falling back to bare numbers
function updateRegimeChart(svg, xScale, line) {
  const t = svg.transition().duration(750);
  const axis = svg.select(".x-axis");
  axis.transition(t).call(regimeXAxis(xScale));
  // the axis re-inserts its spine on every call
  axis.select(".domain").remove();
  // the legend swatches are .series-line too, so only the clipped paths move
  svg
    .selectAll(".chart-content .series-line")
    .transition(t)
    .attr("d", (s) => line(s.points));
}

// the scale-break marker: a bg-filled gap in the axis edge crossed by two
// slanted strokes, plus a faint dashed hairline across the plot so the break
// is visible far from the axis
function breakGlyphView(svg, boundaries, yBreak) {
  svg
    .append("line")
    .attr("class", "grid-horizontal")
    .attr("stroke-dasharray", "3 4")
    .attr("x1", boundaries.l)
    .attr("x2", boundaries.r)
    .attr("y1", yBreak)
    .attr("y2", yBreak);
  svg
    .selectAll(".axis-break")
    .data([-2, 3])
    .join("line")
    .attr("class", "axis-break")
    .attr("x1", boundaries.l - 6)
    .attr("x2", boundaries.l + 6)
    .attr("y1", (d) => yBreak + d + 3)
    .attr("y2", (d) => yBreak + d - 3);
}

// the ticks are the only marks needing explanation; the dots are described
// by the model list beside the chart
function splitLegendView(svg, boundaries, historicalLabel) {
  const rows = svg
    .append("g")
    .attr("class", "legend")
    .selectAll("g")
    .data([
      {
        label: t("median", "médiane"),
        cls: "series-tick series-tick--median",
        dash: null,
      },
      {
        label: historicalLabel,
        cls: "series-tick series-tick--historical green",
        dash: "4 3",
      },
    ])
    .join("g")
    .attr(
      "transform",
      (_, i) => `translate(${boundaries.r}, ${boundaries.t + 12 + i * 21})`,
    );
  rows
    .append("line")
    .attr("class", (k) => k.cls)
    .attr("stroke-dasharray", (k) => k.dash)
    .attr("x1", -18)
    .attr("x2", 0)
    .attr("y1", -4)
    .attr("y2", -4);
  rows
    .append("text")
    .attr("class", "legend-label")
    .attr("x", -22)
    .attr("text-anchor", "end")
    .text((k) => k.label);
}
