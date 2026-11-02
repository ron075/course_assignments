"use strict";

const CATEGORY_LABELS = {
  overview: "Overview",
  composition: "Composition",
  hydrophobicity: "Hydrophobicity",
  chemistry: "Chemistry & charge",
  features: "Sequence features",
  cleavage: "Cleavage",
  antibody: "Antibody",
};

const EXAMPLE_SEQUENCE =
  "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDD" +
  "MPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR";

const byId = (id) => document.getElementById(id);
let bridge = null;
let appSettings = null;
let currentAnalysis = null;
let visibleCategories = [];
let activeCategory = "overview";
let toastTimer = 0;

function node(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== "") element.textContent = String(text);
  return element;
}

function invoke(method, ...args) {
  return new Promise((resolve, reject) => {
    if (!bridge || typeof bridge[method] !== "function") {
      reject(new Error("The Python application bridge is not ready."));
      return;
    }
    bridge[method](...args, (raw) => {
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error("The application returned an invalid response."));
      }
    });
  });
}

function setStatus(message, kind = "") {
  const status = byId("appStatus");
  status.textContent = message;
  status.className = `status-line${kind ? ` ${kind}` : ""}`;
}

function showToast(message, isError = false) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 3300);
}

function applyTheme(mode, effectiveTheme) {
  byId("themeSelect").value = mode;
  document.documentElement.dataset.theme = effectiveTheme;
  if (appSettings) {
    document.documentElement.style.fontSize = `${(appSettings.fontSize * 4) / 3}px`;
  }
}

function setBusy(button, busy, text) {
  if (!button.dataset.defaultLabel) button.dataset.defaultLabel = button.textContent.trim();
  button.disabled = busy;
  button.textContent = busy ? text : button.dataset.defaultLabel;
}

function setView(view) {
  const onResults = view === "results" && currentAnalysis !== null;
  byId("inputView").hidden = onResults;
  byId("resultsView").hidden = !onResults;
  byId("mainNav").classList.toggle("active", !onResults);
  byId("mainNav").toggleAttribute("aria-current", !onResults);
  byId("dataNav").classList.toggle("active", onResults);
  byId("dataNav").toggleAttribute("aria-current", onResults);
  byId("dataNav").disabled = currentAnalysis === null;
  byId("searchControl").hidden = !onResults;
  byId("searchLabel").hidden = !onResults;
  byId("exportButton").disabled = currentAnalysis === null;
  byId("pageTitle").textContent = onResults ? "Analysis data" : "Protein Analysis Studio";
  byId("pageEyebrow").textContent = onResults ? "RESULTS WORKSPACE" : "WORKSPACE";
  if (!onResults) {
    byId("globalSearch").value = "";
    byId("searchResults").hidden = true;
    byId("resultsContent").hidden = false;
    byId("categoryTabs").hidden = false;
  }
}

function getCategories(context) {
  const relevant =
    context === "antibody"
      ? ["antibody"]
      : ["overview", "composition", "hydrophobicity", "chemistry", "features", "cleavage"];
  const enabled = relevant.filter(
    (key) => key === "overview" || appSettings.categories[key] !== false,
  );
  return enabled.length ? enabled : [context === "antibody" ? "antibody" : "overview"];
}

function createTable(headers, rows, numericColumns = [], category = activeCategory, targetPrefix = "row") {
  const wrap = node("div", "table-wrap");
  const table = node("table", "data-table");
  const thead = node("thead");
  const headerRow = node("tr");
  headers.forEach((header, index) => {
    const th = node("th", numericColumns.includes(index) ? "numeric" : "", header);
    headerRow.append(th);
  });
  thead.append(headerRow);
  const tbody = node("tbody");
  rows.forEach((row, index) => {
    const tr = node("tr");
    tr.id = `search-target-${category}-${targetPrefix}-${index}`;
    tr.tabIndex = -1;
    row.forEach((value, index) => {
      tr.append(node("td", numericColumns.includes(index) ? "numeric" : "", value));
    });
    tbody.append(tr);
  });
  table.append(thead, tbody);
  wrap.append(table);
  return wrap;
}

function referenceHeading(title, reference, tagName = "h3") {
  const heading = node(tagName);
  if (appSettings?.enableReferenceLinks && reference) {
    const link = node("a", "reference-link", title);
    link.href = "#";
    link.dataset.reference = reference;
    heading.append(link);
  } else {
    heading.textContent = title;
  }
  return heading;
}

function block(title, description = "", reference = "") {
  const section = node("section", "panel-block");
  if (title) section.append(referenceHeading(title, reference));
  if (description) section.append(node("p", "muted-copy", description));
  return section;
}

function renderOverview(data) {
  const panel = node("div", "category-panel");
  const heading = node("div", "panel-heading");
  const titleBlock = node("div");
  titleBlock.append(referenceHeading("At a glance", "protparam"));
  titleBlock.append(
    node("p", "", "Sequence-derived measurements and summary properties."),
  );
  heading.append(titleBlock);
  panel.append(heading);

  const grid = node("div", "metric-grid");
  const accents = ["#6ea9ff", "#59d9c4", "#bc9aff", "#ffc36f", "#ff8ba5", "#76d99b"];
  data.cards.forEach(([label, value], index) => {
    const card = node("article", "metric-card");
    card.style.setProperty("--metric-accent", accents[index % accents.length]);
    card.append(node("div", "metric-label", label));
    card.append(node("div", "metric-value", value));
    grid.append(card);
  });
  panel.append(grid);
  const summary = block("Sequence metrics");
  summary.append(createTable(["Metric", "Value"], data.overview, [], "overview", "summary"));
  panel.append(summary);
  const metrics = data.metrics;
  const extinction = block(
    "Extinction coefficients",
    "At 280 nm in water · M⁻¹ cm⁻¹. Absorbance is for 0.1% (1 g/L) protein.",
    "",
  );
  const absorbance = (value) => (Number(value) / Number(data.molecularWeight)).toFixed(3);
  extinction.append(createTable(
    ["Assumption", "Extinction coefficient", "Absorbance"],
    [
      [
        "All cysteine pairs form cystines",
        Number(metrics.extinction_coefficient_oxidized).toLocaleString(),
        absorbance(metrics.extinction_coefficient_oxidized),
      ],
      [
        "All cysteines are reduced",
        Number(metrics.extinction_coefficient_reduced).toLocaleString(),
        absorbance(metrics.extinction_coefficient_reduced),
      ],
    ],
    [1, 2],
    "overview",
    "extinction",
  ));
  panel.append(extinction);

  const firstResidue = data.sequence[0];
  const firstItem = data.composition.find((item) => item.residue === firstResidue);
  const firstAbbreviation = firstItem?.abbreviation
    ? `${firstItem.abbreviation[0]}${firstItem.abbreviation.slice(1).toLowerCase()}`
    : firstResidue;
  const halfLife = block(
    "Estimated half-life",
    `The N-terminal residue is ${firstResidue} (${firstAbbreviation}). Estimates assume an unmodified N-terminus and follow the N-end rule.`,
    "n-end-rule",
  );
  halfLife.append(createTable(
    ["Model organism / assay", "Estimated half-life"],
    [
      ["Mammalian reticulocytes (in vitro)", metrics.estimated_half_life[0]],
      ["Yeast (in vivo)", metrics.estimated_half_life[1]],
      ["Escherichia coli (in vivo)", metrics.estimated_half_life[2]],
    ],
    [],
    "overview",
    "half-life",
  ));
  panel.append(halfLife);

  const stability = block(
    "Sequence stability estimates",
    "Instability index below 40 predicts a stable protein; above 40 predicts possible instability.",
    "",
  );
  stability.append(createTable(
    ["Metric", "Estimate"],
    [
      [
        "Instability index",
        metrics.instability_index === null
          ? "Unavailable for ambiguous residues"
          : `${Number(metrics.instability_index).toFixed(2)} · ${metrics.stability_classification}`,
      ],
      ["Aliphatic index", Number(metrics.aliphatic_index).toFixed(2)],
    ],
    [],
    "overview",
    "stability",
  ));
  panel.append(stability);

  const sequence = block("Analyzed sequence");
  const sequenceCode = node("pre", "sequence-display", data.sequence);
  sequence.append(sequenceCode);
  panel.append(sequence);
  return panel;
}

function renderComposition(data) {
  const panel = node("div", "category-panel");
  const heading = node("div", "panel-heading");
  const titleBlock = node("div");
  titleBlock.append(referenceHeading("Amino-acid composition", "amino-acids"));
  titleBlock.append(node("p", "", "Residue counts and percentages in the analyzed sequence."));
  const sortLabel = node("label", "composition-sort-label", "Sort");
  const sortSelect = node("select", "composition-sort");
  sortSelect.setAttribute("aria-label", "Sort amino-acid composition");
  [
    ["alphabetical", "Alphabetical"],
    ["percentage", "Percentage (high to low)"],
  ].forEach(([value, label]) => {
    const option = node("option", "", label);
    option.value = value;
    sortSelect.append(option);
  });
  sortLabel.append(sortSelect);
  heading.append(titleBlock, sortLabel);
  panel.append(heading);
  function drawComposition(sortOrder) {
    const items = [...data.composition];
    if (sortOrder === "percentage") {
      items.sort((left, right) => right.percent - left.percent || left.fullName.localeCompare(right.fullName));
    } else {
      items.sort((left, right) => left.fullName.localeCompare(right.fullName));
    }
    return renderBarChart(
      items.map((item) => ({
        id: `search-target-composition-residue-${item.residue}`,
      label: item.fullName,
      detail: `${item.abbreviation} / ${item.residue}`,
      count: item.count,
      percent: item.percent,
      color: "var(--accent)",
      tooltip: `${item.fullName} · ${item.abbreviation} / ${item.residue} · ${item.count} (${item.percent.toFixed(2)}%)`,
      })),
      "composition-chart-amino",
    );
  }
  const chartHost = node("div");
  chartHost.append(drawComposition("alphabetical"));
  sortSelect.addEventListener("change", () => {
    chartHost.replaceChildren(drawComposition(sortSelect.value));
  });
  panel.append(chartHost);

  const atomic = block(
    "Atomic composition",
    "Counts are for the neutral polypeptide, including terminal water. Ambiguous residues prevent an exact atomic formula.",
    "protparam",
  );
  const atomCounts = data.metrics.atomic_composition;
  if (atomCounts) {
    atomic.append(createTable(
      ["Element", "Symbol", "Count"],
      ["Carbon", "Hydrogen", "Nitrogen", "Oxygen", "Sulfur"].map((element, index) => {
        const symbol = ["C", "H", "N", "O", "S"][index];
        return [element, symbol, Number(atomCounts[symbol]).toLocaleString()];
      }),
      [2],
      "composition",
      "atomic",
    ));
    const formula = node("p", "composition-formula");
    formula.id = "search-target-composition-formula";
    formula.tabIndex = -1;
    formula.append(node("strong", "", "Formula: "));
    const chemicalFormula = node("span", "chemical-formula");
    const formulaParts = String(data.metrics.formula).match(/[A-Z][a-z]?\d*/g) || [];
    formulaParts.forEach((part) => {
      const match = part.match(/^([A-Z][a-z]?)(\d*)$/);
      if (!match) {
        chemicalFormula.append(document.createTextNode(part));
        return;
      }
      chemicalFormula.append(document.createTextNode(match[1]));
      if (match[2]) {
        const subscript = node("sub", "formula-subscript", match[2]);
        chemicalFormula.append(subscript);
      }
    });
    formula.append(chemicalFormula);
    formula.append(node("span", "", ` · Total number of atoms: ${Number(data.metrics.total_atoms).toLocaleString()}`));
    atomic.append(formula);
  } else {
    atomic.append(node("p", "muted-copy", "Atomic counts and formula are unavailable because the sequence contains ambiguous residues."));
  }
  panel.append(atomic);
  return panel;
}

function renderBarChart(items, chartClass = "") {
  const scroller = node("div", "bar-chart-scroll");
  const chart = node("div", "composition-chart");
  if (chartClass) chart.classList.add(chartClass);
  chart.style.setProperty("--bar-count", String(Math.max(items.length, 1)));
  if (!chartClass) chart.style.minWidth = `${items.length * 54}px`;
  const maxPercent = Math.max(1, ...items.map((item) => item.percent));
  items.forEach((item) => {
    const column = node("article", "bar-column");
    if (item.id) {
      column.id = item.id;
      column.tabIndex = -1;
    }
    const track = node("div", "bar-track");
    const fill = node("div", "bar-fill");
    fill.style.height = `${Math.max(2, (item.percent / maxPercent) * 100)}%`;
    fill.style.setProperty("--bar-color", item.color || "var(--accent)");
    fill.title = item.tooltip || `${item.label}: ${item.count} (${item.percent.toFixed(2)}%)`;
    track.append(fill);
    column.append(
      track,
      node("strong", "bar-label", item.label),
      node("span", "bar-detail", item.detail || ""),
      node("span", "bar-count", `${item.count} residues`),
      node("span", "bar-percent", `${item.percent.toFixed(2)}%`),
    );
    chart.append(column);
  });
  scroller.append(chart);
  return scroller;
}

function attachChartTooltip(svg, card, pointCount, getText) {
  const tooltip = node("div", "chart-tooltip");
  tooltip.hidden = true;
  card.append(tooltip);
  svg.addEventListener("pointermove", (event) => {
    const bounds = svg.getBoundingClientRect();
    const scale = Math.min(bounds.width / 800, bounds.height / 310);
    const horizontalInset = (bounds.width - 800 * scale) / 2;
    const plotLeft = bounds.left + horizontalInset + 66 * scale;
    const plotRight = bounds.left + horizontalInset + 780 * scale;
    if (event.clientX < plotLeft || event.clientX > plotRight) {
      tooltip.hidden = true;
      return;
    }
    const fraction = (event.clientX - plotLeft) / (plotRight - plotLeft);
    const index = Math.min(
      pointCount - 1,
      Math.max(0, Math.round(fraction * (pointCount - 1))),
    );
    tooltip.textContent = getText(index);
    tooltip.hidden = false;
    const cardBounds = card.getBoundingClientRect();
    tooltip.style.left = `${Math.max(8, Math.min(
      event.clientX - cardBounds.left + 12,
      cardBounds.width - tooltip.offsetWidth - 8,
    ))}px`;
    tooltip.style.top = `${Math.max(8, event.clientY - cardBounds.top - tooltip.offsetHeight - 12)}px`;
  });
  svg.addEventListener("pointerleave", () => {
    tooltip.hidden = true;
  });
}

function hydrophobicityGroup(value) {
  if (value >= 1) return "hydrophobic";
  if (value <= -1) return "hydrophilic";
  return "neutral";
}

function groupComposition(composition, category) {
  const definitions = category === "hydrophobicity"
    ? [
        ["hydrophobic", "Hydrophobic", "var(--hydrophobic)"],
        ["neutral", "Neutral", "var(--neutral)"],
        ["hydrophilic", "Hydrophilic", "var(--hydrophilic)"],
      ]
    : [
        ["neutral", "Mostly neutral", "var(--neutral)"],
        ["negative", "Mostly negative", "var(--negative)"],
        ["positive", "Mostly positive", "var(--positive)"],
      ];
  return definitions.map(([group, label, color]) => {
    const residues = composition.filter((item) => {
      if (category === "hydrophobicity") {
        return hydrophobicityGroup(Number(item.hydrophobicityValue)) === group;
      }
      if (group === "positive") return ["K", "R"].includes(item.residue);
      if (group === "negative") return ["D", "E"].includes(item.residue);
      return !["K", "R", "D", "E"].includes(item.residue);
    });
    const count = residues.reduce((total, item) => total + item.count, 0);
    const total = composition.reduce((sum, item) => sum + item.count, 0);
    return {
      label,
      detail: residues.map((item) => item.residue).join(" "),
      count,
      percent: total ? (count / total) * 100 : 0,
      color,
      tooltip: `${label} · ${count} residues (${total ? ((count / total) * 100).toFixed(2) : "0.00"}%)`,
    };
  });
}

function renderLineChart(points, title, targetId, axisLabel, reference = "") {
  const card = node("div", "chart-card");
  if (targetId) {
    card.id = targetId;
    card.tabIndex = -1;
  }
  card.append(referenceHeading(title, reference));
  if (!points || !points.length) {
    card.append(node("div", "empty-state", "Not enough sequence to draw this profile."));
    return card;
  }
  const controls = node("div", "chart-controls");
  const resetButton = node("button", "button button-quiet", "Reset zoom");
  resetButton.type = "button";
  resetButton.disabled = true;
  controls.append(resetButton, node("span", "zoom-hint", "Drag across the graph to zoom in"));
  card.append(controls);
  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("viewBox", "0 0 800 310");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", title);
  svg.classList.add("chart-svg", "is-zoomable");
  const left = 66;
  const right = 780;
  const top = 22;
  const bottom = 258;
  card.append(svg);
  const tooltip = node("div", "chart-tooltip");
  tooltip.hidden = true;
  card.append(tooltip);
  let startIndex = 0;
  let endIndex = points.length - 1;
  let dragStart = null;
  let selection = null;

  function localX(event) {
    const bounds = svg.getBoundingClientRect();
    const scale = Math.min(bounds.width / 800, bounds.height / 310);
    const inset = (bounds.width - 800 * scale) / 2;
    return (event.clientX - bounds.left - inset) / scale;
  }

  function appendText(x, y, text, anchor) {
    const label = document.createElementNS(svgNs, "text");
    label.setAttribute("x", String(x));
    label.setAttribute("y", String(y));
    label.setAttribute("text-anchor", anchor);
    label.classList.add("chart-axis-label");
    label.textContent = String(text);
    svg.append(label);
  }

  function draw() {
    svg.replaceChildren();
    const visible = points.slice(startIndex, endIndex + 1);
    const values = visible.map((point) => Number(point.value));
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 0);
    const range = Math.max(max - min, 0.1);
    for (let index = 0; index <= 4; index += 1) {
      const ratio = index / 4;
      const y = top + (bottom - top) * ratio;
      const line = document.createElementNS(svgNs, "line");
      line.setAttribute("x1", String(left));
      line.setAttribute("x2", String(right));
      line.setAttribute("y1", String(y));
      line.setAttribute("y2", String(y));
      line.classList.add("chart-gridline");
      svg.append(line);
      appendText(left - 9, y + 4, (max - range * ratio).toFixed(1), "end");
    }
    const coordinates = visible.map((point, index) => [
      visible.length === 1 ? (left + right) / 2 : left + (index / (visible.length - 1)) * (right - left),
      bottom - ((Number(point.value) - min) / range) * (bottom - top),
    ]);
    let pathData = "";
    coordinates.forEach(([x, y], index) => {
      const originalIndex = startIndex + index;
      const startsChain = index === 0
        || points[originalIndex].chain !== points[originalIndex - 1].chain;
      pathData += `${startsChain ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)} `;
    });
    const path = document.createElementNS(svgNs, "path");
    path.setAttribute("d", pathData.trim());
    path.classList.add("chart-line");
    svg.append(path);
    appendText(left, 278, visible[0].position, "start");
    appendText(right, 278, visible.at(-1).position, "end");
    appendText((left + right) / 2, 302, axisLabel, "middle");
    selection = document.createElementNS(svgNs, "rect");
    selection.classList.add("chart-selection");
    selection.setAttribute("y", String(top));
    selection.setAttribute("height", String(bottom - top));
    selection.setAttribute("visibility", "hidden");
    svg.append(selection);
    resetButton.disabled = startIndex === 0 && endIndex === points.length - 1;
  }

  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || points.length < 3) return;
    const x = localX(event);
    if (x < left || x > right) return;
    dragStart = Math.max(left, Math.min(right, x));
    svg.setPointerCapture(event.pointerId);
    tooltip.hidden = true;
  });
  svg.addEventListener("pointermove", (event) => {
    const rawX = localX(event);
    if (dragStart !== null) {
      const x = Math.max(left, Math.min(right, rawX));
      selection.setAttribute("x", String(Math.min(dragStart, x)));
      selection.setAttribute("width", String(Math.abs(x - dragStart)));
      selection.setAttribute("visibility", "visible");
      return;
    }
    if (rawX < left || rawX > right) {
      tooltip.hidden = true;
      return;
    }
    const x = rawX;
    const index = Math.min(
      endIndex - startIndex,
      Math.max(0, Math.round(((x - left) / (right - left)) * (endIndex - startIndex))),
    );
    tooltip.textContent = points[startIndex + index].tooltip;
    tooltip.hidden = false;
    const cardBounds = card.getBoundingClientRect();
    tooltip.style.left = `${Math.max(8, Math.min(
      event.clientX - cardBounds.left + 12,
      cardBounds.width - tooltip.offsetWidth - 8,
    ))}px`;
    tooltip.style.top = `${Math.max(8, event.clientY - cardBounds.top - tooltip.offsetHeight - 12)}px`;
  });
  svg.addEventListener("pointerup", (event) => {
    if (dragStart === null) return;
    const finish = Math.max(left, Math.min(right, localX(event)));
    const initial = dragStart;
    dragStart = null;
    selection.setAttribute("visibility", "hidden");
    if (Math.abs(finish - initial) < 18) return;
    const pointIndex = (x) => Math.round(
      (x - left) / (right - left) * (endIndex - startIndex),
    ) + startIndex;
    const first = pointIndex(Math.min(initial, finish));
    const last = pointIndex(Math.max(initial, finish));
    if (last - first < 1) return;
    startIndex = first;
    endIndex = last;
    tooltip.hidden = true;
    draw();
  });
  svg.addEventListener("pointercancel", () => {
    dragStart = null;
    if (selection) selection.setAttribute("visibility", "hidden");
  });
  svg.addEventListener("pointerleave", () => {
    if (dragStart === null) tooltip.hidden = true;
  });
  resetButton.addEventListener("click", () => {
    startIndex = 0;
    endIndex = points.length - 1;
    tooltip.hidden = true;
    draw();
  });
  draw();
  return card;
}

function renderHydrophobicity(data) {
  const panel = node("div", "category-panel");
  const section = block(
    "Hydrophobicity profile",
    "Per-residue Kyte–Doolittle values. Drag across the line to zoom; hover for residue details.",
    "hydrophobicity",
  );
  const residueNames = new Map(
    data.composition.map((item) => [
      item.residue,
      { fullName: item.fullName, abbreviation: item.abbreviation },
    ]),
  );
  const chartPoints = data.residueDetails.map((residue) => {
    const names = residueNames.get(residue.residue);
    const point = { ...residue, ...names };
    point.tooltip = `Residue ${point.residueNumber} · Chain ${point.chain} · ${point.fullName || point.residue} (${point.abbreviation || "UNK"}/${point.residue}) · Kyte–Doolittle ${Number(point.value).toFixed(2)}`;
    return point;
  });
  section.append(renderLineChart(
    chartPoints,
    "Hydrophobicity by residue",
    "search-target-hydrophobicity-profile",
    "Sequence position",
    "",
  ));
  const groups = block(
    "Amino-acid hydrophobicity groups",
    "Grouped by Kyte–Doolittle side-chain score: hydrophobic ≥ 1, hydrophilic ≤ −1, neutral otherwise.",
    "hydrophobicity",
  );
  groups.append(renderBarChart(groupComposition(data.composition, "hydrophobicity")));
  panel.append(section, groups);
  return panel;
}

function renderChargeChart(data) {
  const card = node("div", "chart-card");
  card.id = "search-target-chemistry-charge-chart";
  card.tabIndex = -1;
  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("viewBox", "0 0 800 310");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Estimated protein net charge across pH");
  svg.classList.add("chart-svg");
  const left = 66;
  const right = 780;
  const top = 22;
  const bottom = 258;
  const values = data.charge.map(([ph, value]) => [Number(ph), Number(value)]);
  const min = Math.min(...values.map(([, charge]) => charge), 0);
  const max = Math.max(...values.map(([, charge]) => charge), 0);
  const range = Math.max(max - min, 0.1);
  for (let index = 0; index <= 4; index += 1) {
    const ratio = index / 4;
    const y = top + (bottom - top) * ratio;
    const line = document.createElementNS(svgNs, "line");
    line.setAttribute("x1", String(left));
    line.setAttribute("x2", String(right));
    line.setAttribute("y1", String(y));
    line.setAttribute("y2", String(y));
    line.classList.add("chart-gridline");
    svg.append(line);
    const label = document.createElementNS(svgNs, "text");
    label.setAttribute("x", String(left - 9));
    label.setAttribute("y", String(y + 4));
    label.setAttribute("text-anchor", "end");
    label.classList.add("chart-axis-label");
    label.textContent = (max - range * ratio).toFixed(1);
    svg.append(label);
  }
  const points = values.map(([ph, charge], index) => [
    left + (index / Math.max(values.length - 1, 1)) * (right - left),
    bottom - ((charge - min) / range) * (bottom - top),
    ph,
    charge,
  ]);
  const path = document.createElementNS(svgNs, "path");
  path.setAttribute("d", points.map(([x, y], index) =>
    `${index ? "L" : "M"} ${x.toFixed(2)} ${y.toFixed(2)}`,
  ).join(" "));
  path.classList.add("chart-line");
  svg.append(path);
  points.forEach(([x, y, ph, charge]) => {
    const circle = document.createElementNS(svgNs, "circle");
    circle.setAttribute("cx", String(x));
    circle.setAttribute("cy", String(y));
    circle.setAttribute("r", "5");
    circle.classList.add("chart-dot");
    const tooltip = document.createElementNS(svgNs, "title");
    tooltip.textContent = `pH ${ph} · Estimated net charge ${charge.toFixed(3)} · Henderson–Hasselbalch model`;
    circle.append(tooltip);
    svg.append(circle);
    const xLabel = document.createElementNS(svgNs, "text");
    xLabel.setAttribute("x", String(x));
    xLabel.setAttribute("y", "278");
    xLabel.setAttribute("text-anchor", "middle");
    xLabel.classList.add("chart-axis-label");
    xLabel.textContent = String(ph);
    svg.append(xLabel);
  });
  const xAxis = document.createElementNS(svgNs, "text");
  xAxis.setAttribute("x", String((left + right) / 2));
  xAxis.setAttribute("y", "302");
  xAxis.setAttribute("text-anchor", "middle");
  xAxis.classList.add("chart-axis-label");
  xAxis.textContent = "pH";
  svg.append(xAxis);
  card.append(svg);
  attachChartTooltip(svg, card, values.length, (index) => {
    const [ph, charge] = values[index];
    return `pH ${ph} · Estimated net charge ${charge.toFixed(3)} · Henderson–Hasselbalch model`;
  });
  return card;
}

function renderChemistry(data) {
  const panel = node("div", "category-panel");
  const charge = block(
    "Estimated net charge by pH",
    "Henderson–Hasselbalch estimate; hover over a point for its pH and charge.",
    "protparam",
  );
  charge.append(renderChargeChart(data));
  const chargeGroups = block(
    "Residue charge groups at native pH",
    "Side-chain groups at pH 7.4: Lys/Arg positive, Asp/Glu negative, and the remaining residues mostly neutral.",
    "protparam",
  );
  chargeGroups.append(renderBarChart(groupComposition(data.composition, "chemistry")));
  const properties = block(
    "Composition and physicochemical properties",
    "",
    "protparam",
  );
  properties.append(
    createTable(["Property", "Value"], data.chemistry, [], "chemistry", "property"),
  );
  const note = node(
    "p",
    "note",
    "Charge and composition properties are theoretical sequence-based estimates, not experimental measurements.",
  );
  panel.append(charge, chargeGroups, properties, note);
  return panel;
}

function renderFeatures(data) {
  const panel = node("div", "category-panel");
  panel.append(referenceHeading("Sequence feature matches", "features"));
  const table = createTable(["Feature", "Result"], data.features, [], "features", "feature");
  if (appSettings.enableReferenceLinks) {
    const references = ["glycosylation", "peptide-cutter", "hydrophobicity"];
    table.querySelectorAll("tbody tr").forEach((row, index) => {
      const label = row.cells[0].textContent;
      const reference = references[index] || "features";
      if (reference !== "features") {
        const link = node("a", "reference-link", label);
        link.href = "#";
        link.dataset.reference = reference;
        row.cells[0].replaceChildren(link);
      }
    });
  }
  panel.append(table);
  panel.append(
    node(
      "p",
      "note",
      "Motifs and cleavage positions are sequence-pattern matches, not evidence of biological processing or post-translational modification.",
    ),
  );
  return panel;
}

function renderCleavage(data) {
  const panel = node("div", "category-panel");
  panel.append(referenceHeading("Cleavage-site candidates", "peptide-cutter"));
  panel.append(node(
    "p",
    "note",
    "Positions are 1-based cut boundaries. Enzyme specificity is simplified; signal-peptide marks are heuristic candidates, not validated processing sites.",
  ));
  const tracks = node("section", "cleavage-tracks");
  const rows = Object.entries(data.cleavageSites || {}).map(([enzyme, positions]) => [
    enzyme,
    positions.join(", ") || "None detected",
  ]);
  rows.push([
    "Signal peptide (heuristic)",
    (data.signalPeptideCleavageCandidates || []).join(", ") || "None detected",
  ]);
  rows.forEach(([label, value], rowIndex) => {
    const row = node("div", "cleavage-row");
    row.id = `search-target-cleavage-site-${rowIndex}`;
    row.tabIndex = -1;
    row.append(node("strong", "cleavage-label", label));
    const track = node("div", "cleavage-track");
    track.setAttribute("aria-label", `${label} cleavage positions`);
    const positions = rowIndex === rows.length - 1
      ? (data.signalPeptideCleavageCandidates || [])
      : (data.cleavageSites || {})[label] || [];
    positions.forEach((position) => {
      const marker = node("span", `cleavage-marker${rowIndex === rows.length - 1 ? " signal-marker" : ""}`);
      marker.style.left = `${Math.max(0, Math.min(100, position / data.sequence.length * 100))}%`;
      marker.title = `${label}: cut after residue ${position}`;
      marker.setAttribute("aria-label", marker.title);
      track.append(marker);
    });
    row.append(track, node("span", "cleavage-values", value));
    tracks.append(row);
  });
  panel.append(tracks);
  return panel;
}

function renderAntibody(data) {
  const panel = node("div", "category-panel");
  panel.append(referenceHeading("Antibody sequence summary", "protparam"));
  panel.append(node("p", "note", data.summary));
  panel.append(
    createTable(
      ["Component", "Length", "Molecular weight"],
      data.rows,
      [1, 2],
      "antibody",
      "component",
    ),
  );
  return panel;
}

const CATEGORY_RENDERERS = {
  overview: renderOverview,
  composition: renderComposition,
  hydrophobicity: renderHydrophobicity,
  chemistry: renderChemistry,
  features: renderFeatures,
  cleavage: renderCleavage,
  antibody: renderAntibody,
};

function renderTabs() {
  const tabs = byId("categoryTabs");
  tabs.replaceChildren();
  visibleCategories.forEach((category) => {
    const button = node(
      "button",
      `category-tab${category === activeCategory ? " active" : ""}`,
      CATEGORY_LABELS[category],
    );
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(category === activeCategory));
    button.addEventListener("click", () => {
      activeCategory = category;
      renderTabs();
      renderActiveCategory();
    });
    tabs.append(button);
  });
}

function renderActiveCategory() {
  const renderer = CATEGORY_RENDERERS[activeCategory];
  byId("resultsContent").replaceChildren(renderer(currentAnalysis));
}

function collectSearchRows() {
  const rows = [];
  const pushRows = (category, metricRows, targetPrefix) => {
    metricRows.forEach((row, index) => {
      rows.push({
        category,
        label: String(row[0]),
        value: row.slice(1).map(String).join(" · "),
        target: `search-target-${category}-${targetPrefix}-${index}`,
        searchable: row.map(String),
      });
    });
  };
  const pushGraph = (category, label, values, pointLabels, target) => {
    rows.push({
      category,
      label,
      value: `Interactive graph · ${values.length} data points`,
      target,
      searchable: [
        label,
        `${values.length} data points`,
        ...values.map((value) => Number(value).toFixed(3)),
        ...pointLabels,
      ],
    });
  };
  if (currentAnalysis.context === "antibody") {
    pushRows("antibody", currentAnalysis.rows, "component");
    return rows;
  }
  if (visibleCategories.includes("overview")) {
    pushRows("overview", currentAnalysis.overview, "summary");
    pushRows(
      "overview",
      [
        [
          "All cysteine pairs form cystines",
          currentAnalysis.metrics.extinction_coefficient_oxidized,
        ],
        [
          "All cysteines are reduced",
          currentAnalysis.metrics.extinction_coefficient_reduced,
        ],
      ],
      "extinction",
    );
    pushRows(
      "overview",
      [
        [
          "Mammalian reticulocytes (in vitro)",
          currentAnalysis.metrics.estimated_half_life[0],
        ],
        ["Yeast (in vivo)", currentAnalysis.metrics.estimated_half_life[1]],
        ["Escherichia coli (in vivo)", currentAnalysis.metrics.estimated_half_life[2]],
      ],
      "half-life",
    );
    pushRows(
      "overview",
      [
        [
          "Instability index",
          currentAnalysis.metrics.instability_index ?? "Unavailable",
          currentAnalysis.metrics.stability_classification,
        ],
        ["Aliphatic index", currentAnalysis.metrics.aliphatic_index],
      ],
      "stability",
    );
  }
  if (visibleCategories.includes("composition")) {
    pushRows(
      "composition",
      currentAnalysis.composition.map((item) => [
        `${item.fullName} · ${item.abbreviation}/${item.residue}`,
        item.count,
        `${item.percent.toFixed(2)}%`,
      ]),
      "residue",
    );
    rows.slice(-currentAnalysis.composition.length).forEach((row) => {
      const residue = currentAnalysis.composition.find((item) =>
        row.label.includes(`${item.abbreviation}/${item.residue}`),
      )?.residue;
      if (residue) row.target = `search-target-composition-residue-${residue}`;
    });
    const atomCounts = currentAnalysis.metrics.atomic_composition;
    if (atomCounts) {
      const atomicRowsStart = rows.length;
      pushRows(
        "composition",
        [
          ["Carbon", "C", atomCounts.C],
          ["Hydrogen", "H", atomCounts.H],
          ["Nitrogen", "N", atomCounts.N],
          ["Oxygen", "O", atomCounts.O],
          ["Sulfur", "S", atomCounts.S],
        ],
        "atomic",
      );
      rows.slice(atomicRowsStart).forEach((row, index) => {
        row.target = `search-target-composition-atomic-${index}`;
      });
      rows.push({
        category: "composition",
        label: "Atomic formula",
        value: `${currentAnalysis.metrics.formula} · ${currentAnalysis.metrics.total_atoms} atoms`,
        target: "search-target-composition-formula",
        searchable: [
          "Atomic formula",
          String(currentAnalysis.metrics.formula),
          String(currentAnalysis.metrics.total_atoms),
        ],
      });
    }
  }
  if (visibleCategories.includes("hydrophobicity")) {
    pushGraph(
      "hydrophobicity",
      "Hydrophobicity profile",
      currentAnalysis.residueDetails.map((residue) => Number(residue.value)),
      currentAnalysis.residueDetails.map(
        (residue) => `Position ${residue.residueNumber} ${residue.chain} ${residue.residue}`,
      ),
      "search-target-hydrophobicity-profile",
    );
  }
  if (visibleCategories.includes("chemistry")) {
    pushRows("chemistry", currentAnalysis.chemistry, "property");
    pushGraph(
      "chemistry",
      "Charge versus pH",
      currentAnalysis.charge.map(([_ph, value]) => Number(value)),
      currentAnalysis.charge.map(([ph]) => `pH ${ph}`),
      "search-target-chemistry-charge-chart",
    );
  }
  if (visibleCategories.includes("features")) {
    pushRows("features", currentAnalysis.features, "feature");
  }
  if (visibleCategories.includes("cleavage")) {
    Object.entries(currentAnalysis.cleavageSites || {}).forEach(([enzyme, positions], index) => {
      pushRows("cleavage", [[enzyme, positions.join(", ") || "None detected"]], "site");
      rows.at(-1).target = `search-target-cleavage-site-${index}`;
    });
    pushRows(
      "cleavage",
      [[
        "Signal peptide (heuristic)",
        (currentAnalysis.signalPeptideCleavageCandidates || []).join(", ") || "None detected",
      ]],
      "site",
    );
    rows.at(-1).target = `search-target-cleavage-site-${Object.keys(currentAnalysis.cleavageSites || {}).length}`;
  }
  return rows;
}

function updateSearch(query) {
  const term = query.trim().toLocaleLowerCase();
  const searchResults = byId("searchResults");
  const searching = term.length > 0;
  searchResults.hidden = !searching;
  byId("resultsContent").hidden = searching;
  byId("categoryTabs").hidden = searching;
  if (!searching) return;
  const matches = collectSearchRows().filter((row) =>
    row.searchable.join(" ").toLocaleLowerCase().includes(term),
  );
  byId("searchResultsTitle").textContent = `${matches.length} matching value${matches.length === 1 ? "" : "s"}`;
  const body = byId("searchResultsBody");
  body.replaceChildren();
  matches.forEach((row) => {
    const tr = node("tr");
    tr.dataset.target = row.target;
    tr.dataset.category = row.category;
    tr.setAttribute("role", "button");
    tr.setAttribute("aria-label", `Open ${CATEGORY_LABELS[row.category]}: ${row.label}`);
    tr.tabIndex = 0;
    [CATEGORY_LABELS[row.category], row.label, row.value].forEach((value) =>
      tr.append(node("td", "", value)),
    );
    body.append(tr);
  });
  if (!matches.length) {
    const tr = node("tr");
    const td = node("td", "empty-state", "No matching values");
    td.colSpan = 3;
    tr.append(td);
    body.append(tr);
  }
}

function openSearchTarget(resultRow) {
  const category = resultRow.dataset.category;
  const targetId = resultRow.dataset.target;
  if (!category || !visibleCategories.includes(category)) return;
  activeCategory = category;
  renderTabs();
  renderActiveCategory();
  byId("globalSearch").value = "";
  updateSearch("");
  requestAnimationFrame(() => {
    const target = document.getElementById(targetId);
    if (!target) {
      showToast("The matching result is no longer available.", true);
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    target.focus({ preventScroll: true });
    target.classList.remove("search-target-highlight");
    void target.offsetWidth;
    target.classList.add("search-target-highlight");
  });
}

function displayAnalysis(data) {
  currentAnalysis = data;
  visibleCategories = getCategories(data.context);
  activeCategory = visibleCategories[0];
  byId("globalSearch").value = "";
  byId("searchResults").hidden = true;
  byId("resultsContent").hidden = false;
  byId("categoryTabs").hidden = false;
  updateAnalysisTitle(data);
  byId("resultSubtitle").textContent =
    data.context === "antibody"
      ? "Heavy and light chain overview."
      : data.context === "structure"
        ? `${data.sequence.length.toLocaleString()} residues · PDB ${data.pdbId} · ${data.analysisChains.length > 1 ? `all ${data.analysisChains.length} chains` : `chain ${data.analysisChains[0]}`}`
        : `${data.sequence.length.toLocaleString()} residues · Protein sequence`;
  byId("resultContext").textContent =
    data.context === "antibody"
      ? "ANTIBODY ANALYSIS"
      : data.context === "structure"
        ? "STRUCTURE ANALYSIS"
        : "PROTEIN ANALYSIS";
  renderTabs();
  renderActiveCategory();
  byId("dataNav").disabled = false;
  setView("results");
  const invalid = data.invalidCharacters || [];
  setStatus(
    data.context === "antibody"
      ? "Antibody analysis updated."
      : `Analyzed ${data.sequence.length} residues${invalid.length ? ` · ignored invalid symbols: ${invalid.join(", ")}` : ""}.`,
    "success",
  );
}

function updateAnalysisTitle(data) {
  const title = data.context === "antibody" ? "Antibody sequence summary" : data.name;
  const reference = data.context === "structure" && data.pdbId
    ? `pdb:${data.pdbId}`
    : data.context === "antibody" ? "protparam" : "";
  byId("resultName").replaceChildren(
    appSettings.enableReferenceLinks && reference
      ? (() => {
          const link = node("a", "reference-link", title);
          link.href = "#";
          link.dataset.reference = reference;
          return link;
        })()
      : node("span", "", title),
  );
}

async function submitProtein(event) {
  event.preventDefault();
  const button = event.submitter || byId("proteinForm").querySelector('[type="submit"]');
  setBusy(button, true, "Analyzing…");
  setStatus("Calculating sequence properties…");
  try {
    const result = await invoke(
      "analyzeSequence",
      byId("sequenceInput").value,
      byId("proteinName").value,
      "protein",
    );
    if (!result.ok) {
      setStatus(result.error, "error");
      return;
    }
    displayAnalysis(result.analysis);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
  }
}

async function submitAntibody(event) {
  event.preventDefault();
  const button = event.submitter || byId("antibodyForm").querySelector('[type="submit"]');
  setBusy(button, true, "Analyzing…");
  try {
    const result = await invoke(
      "analyzeAntibody",
      byId("heavyInput").value,
      byId("lightInput").value,
      byId("antibodyType").value,
    );
    if (!result.ok) {
      setStatus(result.error, "error");
      return;
    }
    displayAnalysis(result.analysis);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
  }
}

async function fetchStructure(event) {
  event.preventDefault();
  const button = byId("fetchButton");
  setBusy(button, true, "Fetching…");
  byId("pdbStatus").textContent = "Retrieving structure and available protein chains…";
  try {
    const result = await invoke("fetchPdb", byId("pdbInput").value);
    if (!result.ok) {
      byId("pdbStatus").textContent = result.error;
      setStatus(result.error, "error");
      return;
    }
    currentAnalysis = null;
    visibleCategories = [];
    byId("sequenceInput").value = "";
    byId("proteinName").value = "";
    byId("dataNav").disabled = true;
    setView("input");
    byId("proteinMode").click();
    byId("pdbInput").value = result.pdbId;
    populateChains(result.chains, result.selectedChain);
    byId("pdbStatus").textContent = `Loaded PDB ${result.pdbId} with ${result.chains.length} chain(s). Choose a chain or all chains, then analyze.`;
    setStatus("Select the PDB chain(s) to include in the analysis.");
  } catch (error) {
    byId("pdbStatus").textContent = error.message;
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
  }
}

function populateChains(chains, selectedId) {
  const select = byId("chainSelect");
  select.replaceChildren();
  const allOption = node("option", "", `All chains · ${(chains || []).reduce((total, chain) => total + chain.length, 0)} aa`);
  allOption.value = "__all__";
  select.append(allOption);
  (chains || []).forEach((chain) => {
    const option = node("option", "", `Chain ${chain.id} · ${chain.length} aa`);
    option.value = chain.id;
    option.selected = chain.id === selectedId;
    select.append(option);
  });
  byId("chainPicker").hidden = !chains || chains.length === 0;
}

async function analyzeSelectedChain() {
  const button = byId("analyzeChainButton");
  setBusy(button, true, "Analyzing…");
  try {
    const chainId = byId("chainSelect").value;
    const result = chainId === "__all__"
      ? await invoke("analyzeAllChains", byId("pdbInput").value)
      : await invoke("analyzeChain", byId("pdbInput").value, chainId);
    if (!result.ok) {
      setStatus(result.error, "error");
      return;
    }
    byId("sequenceInput").value = result.analysis.sequence;
    byId("proteinName").value = result.analysis.name;
    byId("pdbStatus").textContent = `Analyzed ${chainId === "__all__" ? "all chains" : `chain ${chainId}`} from PDB ${byId("pdbInput").value.toUpperCase()}.`;
    displayAnalysis(result.analysis);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
  }
}

async function openFasta() {
  try {
    const result = await invoke("openFasta");
    if (result.ok) {
      byId("sequenceInput").value = result.contents;
      byId("proteinName").value = result.name;
      setStatus(`Loaded ${result.name}. Select Analyze sequence to continue.`);
    } else if (result.error) {
      setStatus(result.error, "error");
    }
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function openAnalysis() {
  try {
    const result = await invoke("openAnalysis");
    if (result.ok) displayAnalysis(result.analysis);
    else if (!result.cancelled) showToast(result.error, true);
  } catch (error) {
    showToast(error.message, true);
  }
}

function buildSettingsCategories() {
  const container = byId("categorySettings");
  container.replaceChildren();
  Object.entries(CATEGORY_LABELS).forEach(([key, label]) => {
    const choice = node("label", "category-choice");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = key;
    checkbox.checked = key === "overview" || appSettings.categories[key] !== false;
    checkbox.disabled = key === "overview";
    choice.append(checkbox, node("span", "", label));
    container.append(choice);
  });
}

function openSettings() {
  buildSettingsCategories();
  byId("fontSizeSetting").value = String(appSettings.fontSize);
  byId("startMaximized").checked = appSettings.startMaximized;
  byId("fullScreenSetting").checked = appSettings.fullScreen;
  byId("enableReferenceLinks").checked = appSettings.enableReferenceLinks;
  byId("settingsDialog").showModal();
}

async function saveSettings() {
  const categories = {};
  byId("categorySettings")
    .querySelectorAll('input[type="checkbox"]')
    .forEach((checkbox) => {
      categories[checkbox.name] = checkbox.checked;
    });
  const settings = {
    categories,
    fontSize: Number(byId("fontSizeSetting").value),
    startMaximized: byId("startMaximized").checked,
    fullScreen: byId("fullScreenSetting").checked,
    enableReferenceLinks: byId("enableReferenceLinks").checked,
  };
  try {
    const result = await invoke("saveSettings", JSON.stringify(settings));
    if (!result.ok) {
      showToast(result.error, true);
      return;
    }
    appSettings = result.settings;
    applyTheme(appSettings.themeMode, appSettings.effectiveTheme);
    if (currentAnalysis) {
      updateAnalysisTitle(currentAnalysis);
      visibleCategories = getCategories(currentAnalysis.context);
      if (!visibleCategories.includes(activeCategory)) activeCategory = visibleCategories[0];
      renderTabs();
      renderActiveCategory();
      if (byId("globalSearch").value) updateSearch(byId("globalSearch").value);
    }
    byId("settingsDialog").close();
    showToast("Settings saved.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function changeTheme() {
  const mode = byId("themeSelect").value;
  try {
    const result = await invoke("setTheme", mode);
    if (!result.ok) {
      showToast(result.error, true);
      return;
    }
    appSettings.themeMode = mode;
    applyTheme(mode, result.effectiveTheme);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function exportAnalysis() {
  try {
    const result = await invoke("exportAnalysis", currentAnalysis.name);
    if (result.ok) showToast(result.message);
    else if (!result.cancelled) showToast(result.error, true);
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindEvents() {
  byId("windowCloseButton").addEventListener("click", () => {
    invoke("closeWindow").catch((error) => showToast(error.message, true));
  });
  byId("windowDragRegion").addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button, a, input, select")) return;
    invoke("startWindowMove").catch((error) => showToast(error.message, true));
  });
  document.addEventListener("pointerdown", (event) => {
    const edgeSize = 8;
    const atLeft = event.clientX <= edgeSize;
    const atRight = event.clientX >= window.innerWidth - edgeSize;
    const atTop = event.clientY <= edgeSize;
    const atBottom = event.clientY >= window.innerHeight - edgeSize;
    const vertical = atTop ? "top" : atBottom ? "bottom" : "";
    const horizontal = atLeft ? "left" : atRight ? "right" : "";
    const edge = vertical && horizontal
      ? `${vertical}-${horizontal}`
      : vertical || horizontal;
    if (!edge || event.button !== 0) return;
    invoke("startWindowResize", edge).catch((error) => showToast(error.message, true));
  }, true);
  byId("mainNav").addEventListener("click", () => setView("input"));
  byId("dataNav").addEventListener("click", () => setView("results"));
  byId("sidebarToggle").addEventListener("click", () => {
    const collapsed = byId("sidebar").classList.toggle("collapsed");
    byId("appShell").classList.toggle("sidebar-is-collapsed", collapsed);
    byId("sidebarToggle").textContent = collapsed ? "›" : "‹";
    byId("sidebarToggle").title = collapsed ? "Expand sidebar" : "Collapse sidebar";
    byId("sidebarToggle").setAttribute(
      "aria-label",
      collapsed ? "Expand sidebar" : "Collapse sidebar",
    );
  });
  byId("themeSelect").addEventListener("change", changeTheme);
  byId("settingsButton").addEventListener("click", openSettings);
  byId("saveSettings").addEventListener("click", saveSettings);
  byId("fetchForm").addEventListener("submit", fetchStructure);
  byId("analyzeChainButton").addEventListener("click", analyzeSelectedChain);
  byId("proteinForm").addEventListener("submit", submitProtein);
  byId("antibodyForm").addEventListener("submit", submitAntibody);
  byId("proteinMode").addEventListener("click", () => {
    byId("proteinMode").classList.add("active");
    byId("antibodyMode").classList.remove("active");
    byId("proteinMode").setAttribute("aria-pressed", "true");
    byId("antibodyMode").setAttribute("aria-pressed", "false");
    byId("proteinForm").hidden = false;
    byId("antibodyForm").hidden = true;
  });
  byId("antibodyMode").addEventListener("click", () => {
    byId("antibodyMode").classList.add("active");
    byId("proteinMode").classList.remove("active");
    byId("antibodyMode").setAttribute("aria-pressed", "true");
    byId("proteinMode").setAttribute("aria-pressed", "false");
    byId("proteinForm").hidden = true;
    byId("antibodyForm").hidden = false;
  });
  byId("importFastaButton").addEventListener("click", openFasta);
  byId("importAnalysisButton").addEventListener("click", openAnalysis);
  byId("exampleButton").addEventListener("click", () => {
    byId("proteinMode").click();
    byId("proteinName").value = "Example protein";
    byId("sequenceInput").value = EXAMPLE_SEQUENCE;
    setStatus("Example sequence loaded. Select Analyze sequence to continue.");
  });
  byId("clearButton").addEventListener("click", () => {
    byId("sequenceInput").value = "";
    byId("proteinName").value = "";
    currentAnalysis = null;
    visibleCategories = [];
    byId("dataNav").disabled = true;
    setView("input");
    setStatus("Sequence input cleared.");
  });
  byId("globalSearch").addEventListener("input", (event) => updateSearch(event.target.value));
  byId("clearSearch").addEventListener("click", () => {
    byId("globalSearch").value = "";
    updateSearch("");
    byId("globalSearch").focus();
  });
  byId("searchResultsBody").addEventListener("click", (event) => {
    const resultRow = event.target.closest("tr[data-target]");
    if (resultRow) openSearchTarget(resultRow);
  });
  byId("searchResultsBody").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const resultRow = event.target.closest("tr[data-target]");
    if (!resultRow) return;
    event.preventDefault();
    openSearchTarget(resultRow);
  });
  document.addEventListener("click", async (event) => {
    const referenceLink = event.target.closest("a[data-reference]");
    if (!referenceLink) return;
    event.preventDefault();
    try {
      const result = await invoke("openReference", referenceLink.dataset.reference);
      if (!result.ok) showToast(result.error, true);
    } catch (error) {
      showToast(error.message, true);
    }
  });
  byId("backToInput").addEventListener("click", () => setView("input"));
  byId("exportButton").addEventListener("click", exportAnalysis);
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (!byId("searchControl").hidden) byId("globalSearch").focus();
    }
  });
}

function initialize() {
  bindEvents();
  if (typeof qt === "undefined" || !qt.webChannelTransport) {
    setStatus("The embedded desktop bridge is unavailable.", "error");
    return;
  }
  new QWebChannel(qt.webChannelTransport, (channel) => {
    bridge = channel.objects.bridge;
    bridge.getInitialState((raw) => {
      try {
        appSettings = JSON.parse(raw);
        applyTheme(appSettings.themeMode, appSettings.effectiveTheme);
        if (bridge.systemThemeChanged) {
          bridge.systemThemeChanged.connect((theme) => {
            if (appSettings.themeMode === "System") {
              appSettings.effectiveTheme = theme;
              applyTheme("System", theme);
            }
          });
        }
      } catch (error) {
        setStatus(`Unable to load application settings: ${error.message}`, "error");
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", initialize);
