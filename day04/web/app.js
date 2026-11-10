"use strict";

const CATEGORY_LABELS = {
  overview: "Overview",
  composition: "Composition",
  hydrophobicity: "Hydrophobicity",
  chemistry: "Chemistry & charge",
  features: "Sequence features",
  cleavage: "Cleavage",
};

const EXAMPLE_SEQUENCE =
  "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDD" +
  "MPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR";

const byId = (id) => document.getElementById(id);
let bridge = null;
let appSettings = null;
let webMode = false;
let currentAnalysis = null;
let visibleCategories = [];
let activeCategory = "overview";
let chargeProfilePh = 7.4;
let selectedChargeResidues = null;
let activeStructureKey = "";
let activeStructureSource = "";
const IONIZABLE_RESIDUES = ["D", "E", "H", "C", "Y", "K", "R"];
let toastTimer = 0;

function node(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== "") element.textContent = String(text);
  return element;
}

function invoke(method, ...args) {
  if (webMode) {
    return fetch(`/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ args }),
    }).then(async (response) => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The request failed.");
      return result;
    });
  }
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
      ? ["overview", "composition", "chemistry", "features", "cleavage"]
      : ["overview", "composition", "hydrophobicity", "chemistry", "features", "cleavage"];
  const enabled = relevant.filter(
    (key) => key === "overview" || appSettings.categories[key] !== false,
  );
  return enabled.length ? enabled : ["overview"];
}

function parameterTooltip(label) {
  const lower = String(label).trim().toLocaleLowerCase();
  const definitions = {
    "theoretical pi": "Predicted pH at which the protein has approximately zero net charge, calculated from ionizable groups.",
    "gravy": "Grand average of hydropathicity: the mean Kyte–Doolittle hydropathy value across the sequence. Positive values indicate more hydrophobic sequences; negative values indicate more hydrophilic sequences.",
    "gravy score": "Grand average of hydropathicity: the mean Kyte–Doolittle hydropathy value across the sequence. Positive values indicate more hydrophobic sequences; negative values indicate more hydrophilic sequences.",
    "aromaticity": "Fraction of residues that are phenylalanine, tryptophan, or tyrosine.",
    "extinction coefficient": "Estimated absorbance coefficient at 280 nm in water, in M⁻¹ cm⁻¹, based on tryptophan, tyrosine, and cystine content.",
    "average residue mass": "Mean mass per amino-acid residue in the protein chain, accounting for water lost when peptide bonds form.",
    "unique residues": "Number of distinct amino-acid residue types present in the sequence.",
    "charge at ph 7": "Estimated total protein charge at pH 7 using Henderson–Hasselbalch ionization of terminal and ionizable side-chain groups.",
    "instability index": "Sequence-based estimate of in-vitro protein stability. Values below 40 are classified as stable; values above 40 as unstable.",
    "aliphatic index": "Relative volume contribution of alanine, valine, isoleucine, and leucine side chains; often used as an indicator of thermostability.",
    "shannon entropy (standard residues)": "Sequence diversity in bits per residue, calculated from the frequencies of the 20 standard amino acids.",
    "positive residues (k/r/h)": "Count of lysine, arginine, and histidine residues; this is a residue count, not the pH-dependent net charge.",
    "negative residues (d/e)": "Count of aspartic acid and glutamic acid residues; this is a residue count, not the pH-dependent net charge.",
    "basic residues": "Percentage of sequence residues that are lysine, arginine, or histidine.",
    "acidic residues": "Percentage of sequence residues that are aspartic acid or glutamic acid.",
    "cysteines": "Number of cysteine residues in the sequence.",
    "potential disulfide pairs (upper bound)": "Maximum possible number of cysteine pairs, assuming every cysteine can form a disulfide bond.",
    "all cysteine pairs form cystines": "Extinction estimate assumes cysteine residues pair into disulfide-bonded cystines.",
    "all cysteines are reduced": "Extinction estimate assumes cysteine residues are unpaired and reduced.",
    "absorbance": "Estimated absorbance of a 0.1% (1 g/L) protein solution in a 1 cm path-length cuvette.",
    "estimated half-life": "Estimated time for half of the protein to be degraded under the listed organism or assay conditions, based on the N-end rule.",
    "n-linked glycosylation sequons (n-x-s/t, x ≠ p; 1-based start)": "Potential N-linked glycosylation motif N-X-S/T, where X is any residue except proline. Positions are 1-based motif starts; a motif does not prove glycosylation.",
    "transmembrane-like hydrophobic regions (19 aa, heuristic)": "Heuristic regions with a 19-residue Kyte–Doolittle hydrophobicity-window mean of at least 1.6; this is not a validated membrane-topology prediction.",
    "serine/threonine-rich regions (10 aa, ≥ 50%; heuristic)": "Heuristic 10-residue windows containing at least 50% serine or threonine.",
    "low-complexity regions (12 aa, ≥ 60% one residue; heuristic)": "Heuristic 12-residue windows where one amino-acid type makes up at least 60% of the window.",
    "potential phosphorylation residues (s/t/y; not kinase-specific)": "Serine, threonine, and tyrosine positions that could be phosphorylation sites; no kinase specificity or experimental evidence is implied.",
    "n-terminal signal-peptide cleavage candidates (heuristic -3/-1 rule)": "Candidate signal-peptide cut positions from a simple small-residue −3/−1 motif heuristic; not a validated cleavage prediction.",
    "hydrophobic": "Residues with Kyte–Doolittle side-chain hydropathy values ≥ 1.",
    "hydrophilic": "Residues with Kyte–Doolittle side-chain hydropathy values ≤ −1.",
    "neutral": "For hydrophobicity grouping, residues with Kyte–Doolittle side-chain values between −1 and 1; in charge grouping, this label denotes the mostly neutral group at the selected native pH.",
    "mostly positive": "Grouped by basic side-chain character at native pH; primarily lysine and arginine.",
    "mostly negative": "Grouped by acidic side-chain character at native pH; primarily aspartic acid and glutamic acid.",
    "mostly neutral": "Side chains with no substantial positive or negative charge at the app's native reference pH.",
    "residue charge profile": "Estimated ionization charge of each ionizable amino-acid side chain at the selected pH. N- and C-terminal groups are described separately above.",
    "hydrophobicity by residue": "Kyte–Doolittle hydropathy value at each sequence position. Larger positive values indicate more hydrophobic character.",
    "hydrophobicity profile": "Moving-window mean of Kyte–Doolittle residue hydropathy scores; positive values indicate more hydrophobic sequence regions.",
    "amino-acid hydrophobicity groups": "Residues grouped by Kyte–Doolittle side-chain value: hydrophobic ≥ 1, hydrophilic ≤ −1, neutral otherwise.",
    "residue charge groups at native ph": "Residue side chains grouped by their predominant charge category at native pH; this is separate from the pH-dependent residue profile.",
    "atomic composition": "Estimated element counts for a neutral polypeptide chain, including terminal water; ambiguous amino acids prevent an exact formula.",
    "cleavage-site candidates": "Possible sequence cut sites from simplified enzyme rules; candidates are not evidence that cleavage occurs biologically.",
    "sequence feature matches": "Sequence motifs and heuristic regions; matches alone do not establish that a feature occurs experimentally.",
    "signal peptide (heuristic)": "Candidate signal-peptide cleavage positions from a simple −3/−1 rule; heuristic only.",
    "atomic formula": "Estimated elemental formula of the neutral polypeptide, including terminal water.",
    "trypsin": "Predicted cut after lysine (K) or arginine (R), except when the next residue is proline (P).",
    "chymotrypsin": "Predicted cut after phenylalanine (F), tryptophan (W), or tyrosine (Y), except before proline (P).",
    "lys-c": "Predicted cut after lysine (K), except before proline (P).",
    "glu-c": "Predicted cut after glutamic acid (E), except before proline (P).",
    "arg-c": "Predicted cut after arginine (R), except before proline (P).",
    "asp-n": "Predicted cut before aspartic acid (D), excluding the N-terminal position.",
    "cnbr": "Predicted cyanogen bromide cut after methionine (M).",
  };
  if (definitions[lower]) return definitions[lower];
  if (lower.startsWith("hydrophobic windows")) {
    return "Heuristic sequence regions whose moving-window Kyte–Doolittle mean reaches the threshold shown in the label.";
  }
  if (lower.startsWith("trypsin cleavage positions")) {
    return definitions.trypsin;
  }
  if (lower.startsWith("cysteine positions")) {
    return "1-based positions of cysteine residues, which may form disulfide bonds.";
  }
  if (lower.startsWith("n-linked glycosylation")) {
    return definitions["n-linked glycosylation sequons (n-x-s/t, x ≠ p; 1-based start)"];
  }
  if (lower === "extinction coefficients") {
    return "Estimated absorbance coefficients at 280 nm in water, based on aromatic residues and whether cysteines form disulfide bonds.";
  }
  if (lower === "sequence stability estimates") {
    return "Sequence-based stability indicators; these estimates do not replace experimental stability measurements.";
  }
  if (/^(carbon|hydrogen|nitrogen|oxygen|sulfur)$/.test(lower)) {
    return "Element count in the estimated neutral polypeptide formula, including terminal water.";
  }
  return "";
}

function addParameterTooltip(element, label) {
  const explanation = parameterTooltip(label);
  if (explanation) element.title = explanation;
  return element;
}

function createTable(headers, rows, numericColumns = [], category = activeCategory, targetPrefix = "row") {
  const wrap = node("div", "table-wrap");
  const table = node("table", "data-table");
  const thead = node("thead");
  const headerRow = node("tr");
  headers.forEach((header, index) => {
    const th = node("th", numericColumns.includes(index) ? "numeric" : "", header);
    addParameterTooltip(th, header);
    headerRow.append(th);
  });
  thead.append(headerRow);
  const tbody = node("tbody");
  rows.forEach((row, index) => {
    const tr = node("tr");
    tr.id = `search-target-${category}-${targetPrefix}-${index}`;
    tr.tabIndex = -1;
    row.forEach((value, index) => {
      const td = node("td", numericColumns.includes(index) ? "numeric" : "", value);
      if (index === 0) addParameterTooltip(td, value);
      tr.append(td);
    });
    tbody.append(tr);
  });
  table.append(thead, tbody);
  wrap.append(table);
  return wrap;
}

function referenceHeading(title, reference, tagName = "h3") {
  const heading = node(tagName);
  addParameterTooltip(heading, title);
  if (appSettings?.enableReferenceLinks && reference) {
    const link = node("a", "reference-link", title);
    addParameterTooltip(link, title);
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
    card.append(addParameterTooltip(node("div", "metric-label", label), label));
    card.append(node("div", "metric-value", value));
    grid.append(card);
  });
  panel.append(grid);
  const summary = block("Sequence metrics");
  summary.append(createTable(["Metric", "Value"], data.overview, [], "overview", "summary"));
  panel.append(summary);
  const metrics = data.metrics;
  if (data.context === "antibody") {
    const assembly = block(
      "Antibody assembly",
      data.summary,
      "",
    );
    assembly.append(createTable(
      ["Component", "Copies", "Total residues", "Total molecular weight"],
      data.rows,
      [1, 2, 3],
      "overview",
      "assembly",
    ));
    panel.append(assembly);
  }
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
    data.context === "antibody"
      ? "N-end rule estimates apply to each chain separately and do not predict the half-life of the assembled antibody."
      : data.analysisChains?.length > 1
        ? "This N-end rule estimate is for the first listed chain only; it does not predict the half-life of the full multi-chain assembly."
        : `The N-terminal residue is ${firstResidue} (${firstAbbreviation}). Estimates assume an unmodified N-terminus and follow the N-end rule.`,
    "n-end-rule",
  );
  halfLife.append(createTable(
    ["Model organism / assay", "Estimated half-life"],
    data.context === "antibody"
      ? data.antibodyComponents.map((component) => [
        `${component.label} × ${component.copies}`,
        component.estimatedHalfLife.join(" · "),
      ])
      : [
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
    const label = addParameterTooltip(node("strong", "bar-label", item.label), item.label);
    column.append(
      track,
      label,
      renderBarDetails(item),
      node("span", "bar-count", `${item.count} residues`),
      node("span", "bar-percent", `${item.percent.toFixed(2)}%`),
    );
    chart.append(column);
  });
  scroller.append(chart);
  return scroller;
}

function renderBarDetails(item) {
  const details = node("span", "bar-detail");
  if (item.residueDetails?.length) {
    item.residueDetails.forEach((residue, index) => {
      if (index) details.append(document.createTextNode(" "));
      const letter = node("span", "residue-letter", residue.residue);
      letter.title = `${residue.fullName} (${residue.abbreviation})`;
      letter.setAttribute("aria-label", letter.title);
      details.append(letter);
    });
  } else {
    details.textContent = item.detail || "";
  }
  return details;
}

function attachChartTooltip(svg, card, pointCount, getText, pointXPositions = null) {
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
    const count = typeof pointCount === "function" ? pointCount() : pointCount;
    if (!count) {
      tooltip.hidden = true;
      return;
    }
    let index;
    if (pointXPositions) {
      const positions = typeof pointXPositions === "function"
        ? pointXPositions()
        : pointXPositions;
      const chartX = 66 + ((event.clientX - plotLeft) / (plotRight - plotLeft)) * (780 - 66);
      index = positions.reduce(
        (nearest, x, candidate) =>
          Math.abs(x - chartX) < Math.abs(positions[nearest] - chartX)
            ? candidate
            : nearest,
        0,
      );
    } else {
      const fraction = (event.clientX - plotLeft) / (plotRight - plotLeft);
      index = Math.min(count - 1, Math.max(0, Math.round(fraction * (count - 1))));
    }
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
      residueDetails: residues.map((item) => ({
        residue: item.residue,
        fullName: item.fullName,
        abbreviation: item.abbreviation,
      })),
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

function residueChargeAtPH(residue, ph) {
  let charge = 0;
  if (residue.basicPka !== null && residue.basicPka !== undefined) {
    charge += 1 / (1 + (10 ** (ph - Number(residue.basicPka))));
  }
  if (residue.acidicPka !== null && residue.acidicPka !== undefined) {
    charge -= 1 / (1 + (10 ** (Number(residue.acidicPka) - ph)));
  }
  return charge;
}

function renderChargeChart(data) {
  const card = node("div", "chart-card");
  card.id = "search-target-chemistry-charge-profile";
  card.tabIndex = -1;
  card.append(referenceHeading("Residue charge profile", ""));
  const chargeNote = node(
    "p",
    "muted-copy",
    `${data.context === "antibody" || data.analysisChains?.length > 1 ? "Each polypeptide chain has its own N- and C-terminus. " : "Terminal groups also affect the first and last residues. "}The plotted values show side-chain charge only; terminal groups are not included. N-terminal pKa ${Number(data.chargeModel.nTerminusPka).toFixed(1)}, C-terminal pKa ${Number(data.chargeModel.cTerminusPka).toFixed(1)}.`,
  );
  card.append(chargeNote);
  const filterGroup = node("fieldset", "charge-residue-filters");
  filterGroup.append(node("legend", "", "Show residues"));
  const filterOptions = node("div", "charge-residue-options");
  const sequenceResidues = new Set(data.residueDetails.map((residue) => residue.residue));
  const availableResidues = IONIZABLE_RESIDUES.filter((residue) => sequenceResidues.has(residue));
  if (selectedChargeResidues === null) {
    selectedChargeResidues = new Set(availableResidues);
  } else {
    selectedChargeResidues = new Set(
      availableResidues.filter((residue) => selectedChargeResidues.has(residue)),
    );
  }
  availableResidues.forEach((residue) => {
    const info = data.composition.find((item) => item.residue === residue);
    const label = node("label", "charge-residue-option");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = residue;
    checkbox.checked = selectedChargeResidues.has(residue);
    checkbox.setAttribute(
      "aria-label",
      `Show ${info?.fullName || residue} (${info?.abbreviation || "UNK"})`,
    );
    label.append(
      checkbox,
      node("span", "charge-residue-option-letter", residue),
      node("span", "charge-residue-option-name", info?.fullName || "Unknown residue"),
    );
    filterOptions.append(label);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedChargeResidues.add(residue);
      else selectedChargeResidues.delete(residue);
      drawProfile();
      if (byId("globalSearch").value) updateSearch(byId("globalSearch").value);
    });
  });
  filterGroup.append(filterOptions);
  card.append(filterGroup);
  const control = node("div", "charge-ph-control");
  const sliderLabel = node("label", "", "pH");
  sliderLabel.htmlFor = "chargePhSlider";
  const slider = node("input", "charge-ph-slider");
  slider.id = "chargePhSlider";
  slider.type = "range";
  slider.min = "0";
  slider.max = "14";
  slider.step = "0.1";
  slider.value = String(chargeProfilePh);
  slider.setAttribute("aria-label", "pH for residue charge profile");
  slider.title = "pH at which the ionizable side-chain charges are estimated.";
  const valueLabel = node("output", "charge-ph-value", chargeProfilePh.toFixed(1));
  valueLabel.htmlFor = slider.id;
  valueLabel.setAttribute("aria-live", "polite");
  control.append(sliderLabel, slider, valueLabel);
  card.append(control);

  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("viewBox", "0 0 800 310");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Residue charge at each sequence position");
  svg.classList.add("chart-svg");
  const left = 66;
  const right = 780;
  const top = 22;
  const bottom = 258;
  const minCharge = -1;
  const maxCharge = 1;
  const zeroY = bottom - ((0 - minCharge) / (maxCharge - minCharge)) * (bottom - top);
  const residues = data.residueDetails.filter((residue) =>
    IONIZABLE_RESIDUES.includes(residue.residue),
  );
  const sequenceLength = data.residueDetails.length;
  const points = [];

  function drawText(x, y, text, anchor) {
    const label = document.createElementNS(svgNs, "text");
    label.setAttribute("x", String(x));
    label.setAttribute("y", String(y));
    label.setAttribute("text-anchor", anchor);
    label.classList.add("chart-axis-label");
    label.textContent = text;
    svg.append(label);
  }

  function drawProfile() {
    svg.replaceChildren();
    points.length = 0;
    const values = residues.flatMap((residue) => {
      if (!selectedChargeResidues.has(residue.residue)) return [];
      const charge = residueChargeAtPH(residue, chargeProfilePh);
      const x = sequenceLength === 1
        ? (left + right) / 2
        : left + ((residue.position - 1) / (sequenceLength - 1)) * (right - left);
      const y = bottom - ((charge - minCharge) / (maxCharge - minCharge)) * (bottom - top);
      points.push({ x, y, charge, residue });
      return [{ x, y, charge, residue }];
    });

    [-1, -0.5, 0, 0.5, 1].forEach((tick) => {
      const y = bottom - ((tick - minCharge) / (maxCharge - minCharge)) * (bottom - top);
      const gridline = document.createElementNS(svgNs, "line");
      gridline.setAttribute("x1", String(left));
      gridline.setAttribute("x2", String(right));
      gridline.setAttribute("y1", String(y));
      gridline.setAttribute("y2", String(y));
      gridline.classList.add(tick === 0 ? "chart-zero-line" : "chart-gridline");
      svg.append(gridline);
      drawText(left - 9, y + 4, tick.toFixed(1), "end");
    });

    values.forEach(({ x, y, charge, residue }) => {
      const chargeClass = charge > 0.01
        ? "positive"
        : charge < -0.01
          ? "negative"
          : "neutral";
      const stem = document.createElementNS(svgNs, "line");
      stem.setAttribute("x1", String(x));
      stem.setAttribute("x2", String(x));
      stem.setAttribute("y1", String(zeroY));
      stem.setAttribute("y2", String(y));
      stem.classList.add("charge-profile-stem", `charge-profile-${chargeClass}`);
      const title = document.createElementNS(svgNs, "title");
      title.textContent = `${residue.fullName} (${residue.abbreviation}) at position ${residue.residueNumber}: charge ${charge.toFixed(3)} at pH ${chargeProfilePh.toFixed(1)}`;
      stem.append(title);
      svg.append(stem);

      const marker = document.createElementNS(svgNs, "circle");
      marker.setAttribute("cx", String(x));
      marker.setAttribute("cy", String(y));
      marker.setAttribute("r", "3");
      marker.classList.add("charge-profile-marker", `charge-profile-${chargeClass}`);
      marker.append(title.cloneNode(true));
      svg.append(marker);
    });

    if (!values.length) {
      drawText((left + right) / 2, (top + bottom) / 2, "Select at least one residue type", "middle");
    }

    drawText(left, 278, "1", "start");
    drawText(right, 278, String(sequenceLength || 1), "end");
    drawText((left + right) / 2, 302, "Residue position in sequence", "middle");
    const yAxisLabel = document.createElementNS(svgNs, "text");
    yAxisLabel.setAttribute("x", "15");
    yAxisLabel.setAttribute("y", String((top + bottom) / 2));
    yAxisLabel.setAttribute("text-anchor", "middle");
    yAxisLabel.setAttribute("transform", `rotate(-90 15 ${(top + bottom) / 2})`);
    yAxisLabel.classList.add("chart-axis-label");
    yAxisLabel.textContent = "Residue charge";
    svg.append(yAxisLabel);
  }

  drawProfile();
  card.append(svg);
  attachChartTooltip(
    svg,
    card,
    () => points.length,
    (index) => {
      const { residue, charge } = points[index];
      const chainLabel = residue.chain === "Sequence" ? "" : ` · Chain ${residue.chain}`;
      const terminalLabel = residue.isNTerminal
        ? " · N-terminus"
        : residue.isCTerminal
          ? " · C-terminus"
          : "";
      return `pH ${chargeProfilePh.toFixed(1)} · Residue ${residue.residueNumber}${chainLabel} · ${residue.fullName} (${residue.abbreviation}/${residue.residue}) · Charge ${charge.toFixed(3)}${terminalLabel}`;
    },
    () => points.map((point) => point.x),
  );
  slider.addEventListener("input", () => {
    chargeProfilePh = Number(slider.value);
    valueLabel.value = chargeProfilePh.toFixed(1);
    valueLabel.textContent = chargeProfilePh.toFixed(1);
    svg.setAttribute(
      "aria-label",
      `Residue charge at pH ${chargeProfilePh.toFixed(1)}`,
    );
    drawProfile();
    if (byId("globalSearch").value) updateSearch(byId("globalSearch").value);
  });
  return card;
}

function renderChemistry(data) {
  const panel = node("div", "category-panel");
  const charge = block(
    "Residue charge profile",
    "",
    "",
  );
  charge.append(renderChargeChart(data));
  const chargeGroups = block(
    "Residue charge groups at native pH",
    "",
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
  panel.append(charge, chargeGroups, properties);
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
        addParameterTooltip(link, label);
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
    row.append(addParameterTooltip(node("strong", "cleavage-label", label), label));
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
    const chargeResidues = currentAnalysis.residueDetails.filter((residue) =>
      IONIZABLE_RESIDUES.includes(residue.residue)
      && (selectedChargeResidues === null || selectedChargeResidues.has(residue.residue)),
    );
    pushGraph(
      "chemistry",
      `Residue charge profile at pH ${chargeProfilePh.toFixed(1)}`,
      chargeResidues.map((residue) => residueChargeAtPH(residue, chargeProfilePh)),
      chargeResidues.map((residue) =>
        `Position ${residue.residueNumber} ${residue.chain} ${residue.residue}`,
      ),
      "search-target-chemistry-charge-profile",
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
    const displayedValues = [CATEGORY_LABELS[row.category], row.label, row.value];
    displayedValues.forEach((value) => {
      const cell = node("td");
      appendSearchHighlight(cell, value, term);
      tr.append(cell);
    });
    const matchingSource = row.searchable.find((value) =>
      value.toLocaleLowerCase().includes(term),
    );
    if (
      matchingSource
      && !displayedValues.some((value) => value.toLocaleLowerCase().includes(term))
    ) {
      const valueCell = tr.cells[2];
      const context = node("span", "search-match-context");
      context.append(document.createTextNode("Match: "));
      appendSearchHighlight(context, matchingSource, term);
      valueCell.append(node("br"), context);
    }
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

function appendSearchHighlight(container, text, term) {
  const normalizedText = text.toLocaleLowerCase();
  let cursor = 0;
  let matchIndex = normalizedText.indexOf(term, cursor);
  while (matchIndex !== -1) {
    if (matchIndex > cursor) {
      container.append(document.createTextNode(text.slice(cursor, matchIndex)));
    }
    const highlight = node("mark", "search-match", text.slice(matchIndex, matchIndex + term.length));
    container.append(highlight);
    cursor = matchIndex + term.length;
    matchIndex = normalizedText.indexOf(term, cursor);
  }
  if (cursor < text.length || cursor === 0) {
    container.append(document.createTextNode(text.slice(cursor)));
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
  byId("downloadPdbButton").disabled = data.pdbDownloadAvailable !== true;
  selectedChargeResidues = null;
  visibleCategories = getCategories(data.context);
  activeCategory = visibleCategories[0];
  byId("globalSearch").value = "";
  byId("searchResults").hidden = true;
  byId("resultsContent").hidden = false;
  byId("categoryTabs").hidden = false;
  updateAnalysisTitle(data);
  byId("resultSubtitle").textContent =
    data.context === "antibody"
      ? data.summary
      : data.context === "structure"
        ? `${data.sequence.length.toLocaleString()} residues · ${data.structureName || `PDB ${data.pdbId}`} · ${data.analysisChains.length > 1 ? `all ${data.analysisChains.length} chains` : `chain ${data.analysisChains[0]}`}`
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
      "Antibody",
      Number(byId("heavyCount").value),
      Number(byId("lightCount").value),
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
  const pdbInput = byId("pdbInput");
  if (!pdbInput) {
    setStatus("The PDB identifier field is unavailable. Reload the app and try again.", "error");
    return;
  }
  const pdbId = pdbInput.value.trim();
  if (!/^[A-Za-z0-9]{4}$/.test(pdbId)) {
    const message = "Enter a four-character PDB ID, such as 1A7M.";
    byId("pdbStatus").textContent = message;
    setStatus(message, "error");
    pdbInput.focus();
    return;
  }
  setStructureSelectionEnabled(false);
  setBusy(button, true, "Fetching…");
  byId("pdbStatus").textContent = "Retrieving structure and available protein chains…";
  try {
    const result = await invoke("fetchPdb", pdbId);
    if (!result.ok) {
      byId("pdbStatus").textContent = result.error;
      setStatus(result.error, "error");
      return;
    }
    if (
      !Array.isArray(result.chains)
      || result.chains.length === 0
      || typeof result.structureKey !== "string"
      || typeof result.pdbId !== "string"
    ) {
      throw new Error("The PDB was retrieved, but its chain list could not be read.");
    }
    currentAnalysis = null;
    visibleCategories = [];
    byId("sequenceInput").value = "";
    byId("proteinName").value = "";
    byId("dataNav").disabled = true;
    byId("exportButton").disabled = true;
    setView("input");
    byId("proteinMode").click();
    byId("pdbInput").value = result.pdbId;
    activeStructureKey = result.structureKey;
    activeStructureSource = "fetch";
    populateChains(result.chains);
    byId("downloadPdbButton").disabled = false;
    byId("pdbStatus").textContent = `Loaded PDB ${result.pdbId} with ${result.chains.length} chain(s). Choose a chain or all chains, then analyze.`;
    setStatus("Select the PDB chain(s) to include in the analysis.");
  } catch (error) {
    byId("pdbStatus").textContent = error.message;
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
    if (activeStructureKey) setStructureSelectionEnabled(true);
  }
}

function setStructureSelectionEnabled(enabled) {
  const select = byId("chainSelect");
  const button = byId("analyzeChainButton");
  const clearButton = byId("clearStructureButton");
  if (!select || !button || !clearButton) {
    throw new Error("The shared chain-selection controls are unavailable.");
  }
  select.disabled = !enabled;
  button.disabled = !enabled;
  clearButton.disabled = !enabled;
}

function populateChains(chains) {
  const select = byId("chainSelect");
  if (!select) {
    throw new Error("The chain-selection dropdown is unavailable.");
  }
  select.replaceChildren();
  const allOption = node("option", "", `All chains · ${(chains || []).reduce((total, chain) => total + chain.length, 0)} aa`);
  allOption.value = "__all__";
  allOption.selected = true;
  select.append(allOption);
  (chains || []).forEach((chain) => {
    const option = node("option", "", `Chain ${chain.id} · ${chain.length} aa`);
    option.value = chain.id;
    select.append(option);
  });
  setStructureSelectionEnabled(Array.isArray(chains) && chains.length > 0);
}

async function analyzeSelectedChain() {
  const select = byId("chainSelect");
  const button = byId("analyzeChainButton");
  if (!select || !button || select.disabled || !activeStructureKey) {
    setStatus("Fetch or upload a PDB/CIF structure before choosing chains.", "error");
    return;
  }
  setBusy(button, true, "Analyzing…");
  try {
    const chainId = select.value;
    const result = chainId === "__all__"
      ? await invoke("analyzeAllChains", activeStructureKey)
      : await invoke("analyzeChain", activeStructureKey, chainId);
    if (!result.ok) {
      setStatus(result.error, "error");
      return;
    }
    byId("sequenceInput").value = result.analysis.sequence;
    byId("proteinName").value = result.analysis.name;
    const sourceName = result.analysis.structureName || result.analysis.pdbId || "PDB/CIF file";
    const status = `Analyzed ${chainId === "__all__" ? "all chains" : `chain ${chainId}`} from ${sourceName}.`;
    byId(activeStructureSource === "fetch" ? "pdbStatus" : "uploadPdbStatus").textContent = status;
    displayAnalysis(result.analysis);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
    button.disabled = !select || select.options.length <= 1;
  }
}

async function uploadPdb() {
  if (webMode) {
    const file = await chooseFile(".pdb,.ent,.cif,.mmcif");
    if (!file) return;
    try {
      const result = await invoke("uploadStructure", file.name, await file.text());
      showUploadedStructure(result);
    } catch (error) {
      byId("uploadPdbStatus").textContent = error.message;
      setStatus(error.message, "error");
    }
    return;
  }
  try {
    const result = await invoke("openPdb");
    if (result.cancelled) return;
    if (!result.ok) {
      byId("uploadPdbStatus").textContent = result.error;
      setStatus(result.error, "error");
      return;
    }
    activeStructureKey = result.structureKey;
    activeStructureSource = "upload";
    currentAnalysis = null;
    visibleCategories = [];
    byId("sequenceInput").value = "";
    byId("proteinName").value = "";
    byId("dataNav").disabled = true;
    byId("exportButton").disabled = true;
    setView("input");
    byId("proteinMode").click();
    byId("downloadPdbButton").disabled = true;
    populateChains(result.chains);
    byId("uploadPdbStatus").textContent =
      `Loaded ${result.structureName} with ${result.chains.length} chain(s). Choose a chain or all chains, then analyze.`;
    setStatus("Select the uploaded PDB chain(s) to include in the analysis.");
  } catch (error) {
    byId("uploadPdbStatus").textContent = error.message;
    setStatus(error.message, "error");
  }
}

function showUploadedStructure(result) {
  if (!result.ok) {
    byId("uploadPdbStatus").textContent = result.error;
    setStatus(result.error, "error");
    return;
  }
  activeStructureKey = result.structureKey;
  activeStructureSource = "upload";
  currentAnalysis = null;
  visibleCategories = [];
  byId("sequenceInput").value = "";
  byId("proteinName").value = "";
  byId("dataNav").disabled = true;
  byId("exportButton").disabled = true;
  setView("input");
  byId("proteinMode").click();
  byId("downloadPdbButton").disabled = true;
  populateChains(result.chains);
  byId("uploadPdbStatus").textContent =
    `Loaded ${result.structureName} with ${result.chains.length} chain(s). Choose a chain or all chains, then analyze.`;
  setStatus("Select the uploaded PDB chain(s) to include in the analysis.");
}

function chooseFile(accept) {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.addEventListener("change", () => resolve(input.files?.[0] || null), { once: true });
    input.click();
  });
}

async function clearStructure() {
  const button = byId("clearStructureButton");
  setBusy(button, true, "Clearing…");
  try {
    const result = await invoke("clearPdb");
    if (!result.ok) {
      setStatus(result.error || "Unable to clear the loaded structure.", "error");
      return;
    }
    activeStructureKey = "";
    activeStructureSource = "";
    byId("pdbInput").value = "";
    byId("chainSelect").replaceChildren(
      Object.assign(node("option", "", "All chains"), {
        value: "__all__",
        selected: true,
      }),
    );
    setStructureSelectionEnabled(false);
    byId("downloadPdbButton").disabled = true;
    byId("pdbStatus").textContent = "No structure loaded.";
    byId("uploadPdbStatus").textContent = "No structure file uploaded.";
    if (currentAnalysis?.context === "structure") {
      currentAnalysis = null;
      visibleCategories = [];
      byId("sequenceInput").value = "";
      byId("proteinName").value = "";
      byId("dataNav").disabled = true;
      byId("exportButton").disabled = true;
      setView("input");
    }
    setStatus("Loaded PDB/CIF structure cleared.");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(button, false);
    button.disabled = !activeStructureKey;
  }
}

async function downloadPdb() {
  if (webMode) {
    window.location.assign("/api/download-pdb");
    return;
  }
  try {
    const result = await invoke("downloadPdb");
    if (result.ok) {
      byId("pdbStatus").textContent = result.message;
      setStatus(result.message, "success");
    } else if (result.error) {
      byId("pdbStatus").textContent = result.error;
      setStatus(result.error, "error");
    }
  } catch (error) {
    byId("pdbStatus").textContent = error.message;
    setStatus(error.message, "error");
  }
}

async function openFasta() {
  if (webMode) {
    const file = await chooseFile(".fasta,.fa,.faa,.txt");
    if (!file) return;
    byId("sequenceInput").value = await file.text();
    byId("proteinName").value = file.name.replace(/\.[^.]+$/, "");
    setStatus(`Loaded ${byId("proteinName").value}. Select Analyze sequence to continue.`);
    return;
  }
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
  if (webMode) {
    const file = await chooseFile(".md");
    if (!file) return;
    try {
      const result = await invoke("importAnalysis", await file.text());
      if (result.ok) displayAnalysis(result.analysis);
      else showToast(result.error, true);
    } catch (error) {
      showToast(error.message, true);
    }
    return;
  }
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
  if (webMode) {
    window.location.assign(`/api/export-analysis?name=${encodeURIComponent(currentAnalysis.name)}`);
    return;
  }
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
    if (webMode) return;
    invoke("closeWindow").catch((error) => showToast(error.message, true));
  });
  byId("windowDragRegion").addEventListener("pointerdown", (event) => {
    if (webMode) return;
    if (event.button !== 0 || event.target.closest("button, a, input, select")) return;
    invoke("startWindowMove").catch((error) => showToast(error.message, true));
  });
  document.addEventListener("pointerdown", (event) => {
    if (webMode) return;
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
  byId("clearStructureButton").addEventListener("click", clearStructure);
  byId("downloadPdbButton").addEventListener("click", downloadPdb);
  byId("uploadPdbButton").addEventListener("click", uploadPdb);
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
    byId("heavyInput").value = "";
    byId("lightInput").value = "";
    currentAnalysis = null;
    visibleCategories = [];
    byId("dataNav").disabled = true;
    byId("exportButton").disabled = true;
    setView("input");
    setStatus("Sequence inputs cleared.");
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
      else if (webMode && result.url) window.open(result.url, "_blank", "noopener");
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
    webMode = true;
    byId("windowCloseButton").hidden = true;
    byId("startMaximized").closest(".setting-row").hidden = true;
    byId("fullScreenSetting").closest(".setting-row").hidden = true;
    byId("windowSettingsLegend").textContent = "Text and references";
    fetch("/api/state")
      .then((response) => response.json())
      .then((state) => {
        appSettings = state;
        applyTheme(appSettings.themeMode, appSettings.effectiveTheme);
      })
      .catch((error) => setStatus(`Unable to connect to the Flask server: ${error.message}`, "error"));
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
