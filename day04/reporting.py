from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from protein_analysis import ProteinStats, calculate_extended_metrics


METHOD_NOTES = [
    "Molecular weight uses average residue masses plus one terminal water molecule.",
    "Theoretical pI and charge use a Henderson-Hasselbalch model with the pKa constants listed in protein_analysis.py; values are estimates and sequence-context effects are not modeled.",
    "GRAVY and sliding-window hydrophobicity use the Kyte-Doolittle scale (Kyte and Doolittle, Journal of Molecular Biology 157, 1982).",
    "Aliphatic index uses the formula described by Ikai (Journal of Biochemistry 88, 1980).",
    "Atomic composition uses the neutral polypeptide formula, including terminal water; exact counts are omitted when ambiguous residues occur.",
    "Extinction coefficients at 280 nm in water use 5500 for tryptophan, 1490 for tyrosine, and 125 per cystine; reduced and paired-cysteine assumptions are reported separately.",
    "Estimated half-life uses the N-end rule and the identity of the unmodified N-terminal residue; it is a model-organism estimate, not a measured protein lifetime.",
    "Instability index uses the dipeptide weights described by Guruprasad, Reddy, and Pandit (Protein Engineering 4, 1990); values above 40 predict possible instability.",
    "N-linked glycosylation output identifies N-X-S/T sequence motifs (X is not proline); it does not predict or confirm glycosylation.",
    "Potential disulfide pairs are a cysteine-count upper bound, not observed bonds.",
    "The amino-acid formula and instability index are omitted if ambiguous residues prevent exact calculations. Ambiguous residues are excluded from Shannon entropy and ionizable-residue counts, and contribute zero to hydrophobicity.",
]

ANALYSIS_DATA_START = "<!-- PROTEIN_ANALYSIS_STUDIO_DATA_START -->"
ANALYSIS_DATA_END = "<!-- PROTEIN_ANALYSIS_STUDIO_DATA_END -->"


def build_analysis_markdown(analysis: Dict[str, object]) -> str:
    """Create a readable Markdown report with an embedded round-trip payload."""
    context = analysis.get("context")
    if context not in {"protein", "structure", "antibody"}:
        raise ValueError("The analysis has an unsupported context.")
    name = str(analysis.get("name", "Protein"))
    lines = [
        f"# {name}",
        "",
        f"**Protein Analysis Studio · {str(context).title()} analysis**",
        "",
    ]
    if context == "antibody":
        lines.extend(
            [
                str(analysis.get("summary", "")),
                "",
                "| Component | Copies | Total residues | Total molecular weight |",
                "|:--|--:|--:|--:|",
            ]
        )
        for row in analysis.get("rows", []):
            lines.append("| " + " | ".join(str(value) for value in row) + " |")
    else:
        lines.extend(
            [
                f"**Sequence length:** {len(str(analysis.get('sequence', '')))} residues",
                "",
                "## Summary",
                "",
                "| Metric | Value |",
                "|:--|:--|",
            ]
        )
        for row in analysis.get("overview", []):
            lines.append("| " + " | ".join(str(value) for value in row) + " |")
        lines.extend(
            [
                "",
                "## Sequence",
                "",
                "```text",
                str(analysis.get("sequence", "")),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Methods and limitations",
            "",
            "- Cleavage and sequence-feature matches are heuristic sequence-derived candidates, not experimentally validated results.",
            "- This report embeds its analysis data so it can be imported back into Protein Analysis Studio.",
            "",
            ANALYSIS_DATA_START,
            "```json",
            json.dumps(
                {"schema_version": 1, "analysis": analysis},
                indent=2,
                ensure_ascii=False,
            ),
            "```",
            ANALYSIS_DATA_END,
            "",
        ]
    )
    return "\n".join(lines)


def read_analysis_markdown(path: str | Path) -> Dict[str, object]:
    destination = Path(path)
    text = destination.read_text(encoding="utf-8-sig")
    start = text.find(ANALYSIS_DATA_START)
    end = text.find(ANALYSIS_DATA_END, start + len(ANALYSIS_DATA_START))
    if start < 0 or end < 0:
        raise ValueError("This Markdown file has no embedded analysis data.")
    block = text[start + len(ANALYSIS_DATA_START) : end].strip()
    if not block.startswith("```json") or not block.endswith("```"):
        raise ValueError("The embedded analysis data block is malformed.")
    try:
        payload = json.loads(block[len("```json") : -3].strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid embedded analysis data: {exc.msg}") from exc
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
    ):
        raise ValueError("Unsupported analysis file version.")
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("The Markdown file does not contain a valid analysis.")
    context = analysis.get("context")
    if not isinstance(context, str) or context not in {
        "protein",
        "structure",
        "antibody",
    }:
        raise ValueError("The analysis has an unsupported context.")
    return analysis


def build_report(stats: ProteinStats, name: str = "Protein") -> Dict[str, object]:
    return {
        "protein_name": name,
        "sequence": stats.sequence,
        "statistics": asdict(stats),
        "extended_metrics": calculate_extended_metrics(stats.sequence),
        "methods_and_limitations": METHOD_NOTES,
    }


def export_report(
    path: str | Path, stats: ProteinStats, name: str = "Protein"
) -> None:
    destination = Path(path)
    suffix = destination.suffix.lower()
    report = build_report(stats, name)
    if suffix == ".json":
        _write_json(destination, report)
    elif suffix == ".csv":
        _write_csv(destination, report)
    elif suffix == ".txt":
        _write_text(destination, report)
    elif suffix in {".html", ".htm"}:
        _write_html(destination, report)
    else:
        raise ValueError("Choose a JSON, CSV, TXT, or HTML report file.")


def _write_json(destination: Path, report: Dict[str, object]) -> None:
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _metric_rows(report: Dict[str, object]):
    stats = report["statistics"]
    extended = report["extended_metrics"]
    assert isinstance(stats, dict) and isinstance(extended, dict)
    rows = [
        (label, value)
        for label, value in stats.items()
        if label not in {"sequence", "composition"}
    ]
    rows.extend(
        (label.replace("_", " ").title(), value)
        for label, value in extended.items()
        if label not in {"hydrophobicity_profile", "charge_profile"}
    )
    rows.append(
        (
            "Hydrophobicity profile",
            json.dumps(extended["hydrophobicity_profile"]),
        )
    )
    rows.append(("Charge profile", json.dumps(extended["charge_profile"])))
    return rows


def _write_csv(destination: Path, report: Dict[str, object]) -> None:
    stats = report["statistics"]
    assert isinstance(stats, dict)
    with destination.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["Section", "Item", "Value"])
        writer.writerow(["Protein", "Name", report["protein_name"]])
        writer.writerow(["Protein", "Sequence", report["sequence"]])
        for label, value in _metric_rows(report):
            writer.writerow(["Statistics", label, value])
        composition = stats["composition"]
        assert isinstance(composition, dict)
        for residue, count in composition.items():
            writer.writerow(["Composition", residue, count])
        writer.writerow(["Methods", "Notes", ""])
        for note in report["methods_and_limitations"]:
            writer.writerow(["Methods", "Note", note])


def _write_text(destination: Path, report: Dict[str, object]) -> None:
    lines = [
        str(report["protein_name"]),
        "=" * len(str(report["protein_name"])),
        "",
        "Sequence",
        str(report["sequence"]),
        "",
        "Statistics",
    ]
    lines.extend(f"{label}: {value}" for label, value in _metric_rows(report))
    lines.extend(["", "Amino acid composition"])
    stats = report["statistics"]
    assert isinstance(stats, dict) and isinstance(stats["composition"], dict)
    lines.extend(
        f"{residue}: {count}"
        for residue, count in stats["composition"].items()
    )
    lines.extend(["", "Methods and limitations"])
    lines.extend(f"- {note}" for note in report["methods_and_limitations"])
    destination.write_text("\n".join(lines), encoding="utf-8")


def _write_html(destination: Path, report: Dict[str, object]) -> None:
    rows = "".join(
        "<tr><th>{}</th><td>{}</td></tr>".format(
            html.escape(str(label)), html.escape(str(value))
        )
        for label, value in _metric_rows(report)
    )
    notes = "".join(
        f"<li>{html.escape(str(note))}</li>"
        for note in report["methods_and_limitations"]
    )
    sequence = html.escape(str(report["sequence"]))
    name = html.escape(str(report["protein_name"]))
    document = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{name} - Protein Analysis</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:980px;margin:40px auto;padding:0 20px;color:#182230}}
h1,h2{{color:#214c82}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #d5deea;padding:9px;text-align:left}} th{{width:35%;background:#eef4fb}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6fa;padding:16px;border-radius:8px}}
</style></head>
<body><h1>{name} — Protein Analysis</h1><h2>Sequence</h2><pre>{sequence}</pre>
<h2>Metrics</h2><table>{rows}</table><h2>Methods and limitations</h2><ul>{notes}</ul>
</body></html>"""
    destination.write_text(document, encoding="utf-8")
