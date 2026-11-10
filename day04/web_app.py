from __future__ import annotations

import json
import re
import tempfile
import threading
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file, send_from_directory

from app import AnalysisBridge, WebAnalyzerWindow
from pdb_utils import parse_pdb_chains
from protein_analysis import normalize_sequence
from reporting import build_analysis_markdown, read_analysis_markdown


WEB_DIR = Path(__file__).resolve().parent / "web"


class FlaskAnalysisService(AnalysisBridge):
    """Use the desktop analysis operations without creating a Qt window."""

    def __init__(self) -> None:
        self.window = None
        self.settings: dict[str, Any] = {
            "theme_mode": "Dark",
            "font_size": 12,
            "start_maximized": True,
            "full_screen": False,
            "enable_reference_links": False,
            **{
                f"categories/{key}": True
                for key in WebAnalyzerWindow.CATEGORY_LABELS
            },
        }
        self.last_stats = None
        self.last_analysis = None
        self.last_name = "Protein"
        self.last_context = ""
        self.pdb_chains = {}
        self.active_pdb_chains = None
        self.current_pdb_id = ""
        self.current_structure_key = ""
        self.current_structure_name = ""
        self.current_pdb_text = ""
        self.downloadable_pdb_id = ""

    def initial_state(self) -> dict[str, object]:
        categories = {
            key: self.settings.get(f"categories/{key}", True)
            for key in WebAnalyzerWindow.CATEGORY_LABELS
        }
        categories["overview"] = True
        return {
            "themeMode": self.settings["theme_mode"],
            "effectiveTheme": str(self.settings["theme_mode"]).lower()
            if self.settings["theme_mode"] != "System"
            else "dark",
            "fontSize": self.settings["font_size"],
            "startMaximized": self.settings["start_maximized"],
            "fullScreen": self.settings["full_screen"],
            "enableReferenceLinks": self.settings["enable_reference_links"],
            "categories": categories,
            "categoryLabels": WebAnalyzerWindow.CATEGORY_LABELS,
        }

    def saveSettings(self, settings_json: str) -> dict[str, object]:
        try:
            values = json.loads(settings_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid settings: {exc.msg}"}
        if not isinstance(values, dict):
            return {"ok": False, "error": "Settings must be an object."}
        font_size = values.get("fontSize", self.settings["font_size"])
        categories = values.get("categories", {})
        if type(font_size) is not int or not 8 <= font_size <= 24:
            return {"ok": False, "error": "Font size must be from 8 to 24."}
        if not isinstance(categories, dict) or any(
            key not in WebAnalyzerWindow.CATEGORY_LABELS
            or not isinstance(enabled, bool)
            for key, enabled in categories.items()
        ):
            return {"ok": False, "error": "Result categories are invalid."}
        for field, key in (
            ("startMaximized", "start_maximized"),
            ("fullScreen", "full_screen"),
            ("enableReferenceLinks", "enable_reference_links"),
        ):
            value = values.get(field, self.settings[key])
            if not isinstance(value, bool):
                return {"ok": False, "error": f"{field} must be true or false."}
            self.settings[key] = value
        self.settings["font_size"] = font_size
        for key, enabled in categories.items():
            if key != "overview":
                self.settings[f"categories/{key}"] = enabled
        return {"ok": True, "settings": self.initial_state()}

    def setTheme(self, mode: str) -> dict[str, object]:
        if mode not in {"Dark", "Light", "System"}:
            return {"ok": False, "error": "Choose Dark, Light, or System theme."}
        self.settings["theme_mode"] = mode
        return {
            "ok": True,
            "themeMode": mode,
            "effectiveTheme": mode.lower() if mode != "System" else "dark",
        }

    def openReference(self, reference: str) -> dict[str, object]:
        if not self.settings["enable_reference_links"]:
            return {"ok": False, "error": "Enable reference links in Settings first."}
        references = {
            "protparam": "https://web.expasy.org/protparam/",
            "amino-acids": "https://iupac.qmul.ac.uk/AminoAcid/AA1n2.html",
            "hydrophobicity": "https://doi.org/10.1016/0022-2836(82)90515-0",
            "features": "https://prosite.expasy.org/",
            "glycosylation": "https://www.uniprot.org/help/glycosylation",
            "peptide-cutter": "https://web.expasy.org/peptide_cutter/",
            "n-end-rule": "https://web.expasy.org/protparam/protparam-doc.html",
        }
        if reference.startswith("pdb:"):
            identifier = reference[4:].upper()
            if identifier != self.current_pdb_id or not re.fullmatch(
                r"[A-Z0-9]{4}", identifier
            ):
                return {"ok": False, "error": "The PDB reference is no longer available."}
            url = f"https://www.rcsb.org/structure/{identifier}"
        else:
            url = references.get(reference)
        return {"ok": True, "url": url} if url else {
            "ok": False,
            "error": "This reference is not available.",
        }

    def uploadStructure(self, filename: str, pdb_text: str) -> dict[str, object]:
        chains = parse_pdb_chains(pdb_text)
        if not chains:
            return {"ok": False, "error": "No protein chain data was found in that file."}
        self.pdb_chains = chains
        self.current_pdb_id = ""
        self.current_structure_key = f"upload:{uuid.uuid4().hex}"
        self.current_structure_name = Path(filename).stem or "Uploaded PDB"
        self.current_pdb_text = pdb_text
        self.downloadable_pdb_id = ""
        self.active_pdb_chains = None
        self.last_stats = None
        self.last_analysis = None
        self.last_context = ""
        return {
            "ok": True,
            "structureKey": self.current_structure_key,
            "structureName": self.current_structure_name,
            "selectedChain": sorted(chains)[0],
            "chains": [
                {"id": chain_id, "length": len(sequence)}
                for chain_id, sequence in sorted(chains.items())
            ],
        }

    def importAnalysis(self, markdown: str) -> dict[str, object]:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".md", delete=False
            ) as file:
                file.write(markdown)
                path = Path(file.name)
            try:
                imported = read_analysis_markdown(path)
            finally:
                path.unlink(missing_ok=True)
            context = imported["context"]
            if context == "antibody":
                heavy = imported.get("heavySequence")
                light = imported.get("lightSequence")
                if not isinstance(heavy, str) or not isinstance(light, str):
                    raise ValueError("The antibody sequences are missing from this file.")
                result = self.analyzeAntibody(
                    heavy,
                    light,
                    str(imported.get("antibodyType", "Custom")),
                    imported.get("heavyCount"),
                    imported.get("lightCount"),
                )
            else:
                sequence = imported.get("sequence")
                name = imported.get("name")
                if not isinstance(sequence, str) or not isinstance(name, str):
                    raise ValueError("The protein sequence or name is missing.")
                cleaned, invalid = normalize_sequence(sequence)
                if invalid or cleaned != sequence:
                    raise ValueError("The stored protein sequence is invalid.")
                if context == "structure":
                    chains = imported.get("analysisChains")
                    details = imported.get("residueDetails")
                    pdb_id = imported.get("pdbId")
                    if (
                        not isinstance(chains, list)
                        or not chains
                        or not all(isinstance(chain, str) for chain in chains)
                        or not isinstance(details, list)
                        or not isinstance(pdb_id, str)
                        or not re.fullmatch(r"[A-Z0-9]{4}", pdb_id)
                    ):
                        raise ValueError("The structure metadata is incomplete.")
                    grouped = {chain: [] for chain in chains}
                    for detail in details:
                        chain = detail.get("chain") if isinstance(detail, dict) else None
                        residue = detail.get("residue") if isinstance(detail, dict) else None
                        if chain not in grouped or not isinstance(residue, str):
                            raise ValueError("The residue metadata is malformed.")
                        grouped[chain].append(residue)
                    chain_sequences = {
                        chain: "".join(residues) for chain, residues in grouped.items()
                    }
                    if "".join(chain_sequences[key] for key in sorted(chain_sequences)) != sequence:
                        raise ValueError("The stored chain sequences do not match the protein sequence.")
                    self.pdb_chains = chain_sequences
                    self.active_pdb_chains = chain_sequences.copy()
                    self.current_pdb_id = pdb_id
                    self.current_structure_key = pdb_id
                    self.current_structure_name = f"PDB {pdb_id}"
                    self.current_pdb_text = ""
                    self.downloadable_pdb_id = ""
                result = (
                    self.analyzeAllChains(self.current_structure_key)
                    if context == "structure"
                    else self.analyzeSequence(sequence, name, str(context))
                )
            return result
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            return {"ok": False, "error": str(exc)}


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")
    service = FlaskAnalysisService()
    lock = threading.RLock()

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/api/state")
    def state():
        with lock:
            return jsonify(service.initial_state())

    @app.post("/api/<method>")
    def call(method: str):
        body = request.get_json(silent=True) or {}
        args = body.get("args", [])
        if not isinstance(args, list):
            return jsonify({"ok": False, "error": "Request arguments must be a list."}), 400
        allowed = {
            "analyzeSequence": service.analyzeSequence,
            "analyzeAntibody": service.analyzeAntibody,
            "fetchPdb": service.fetchPdb,
            "analyzeChain": service.analyzeChain,
            "analyzeAllChains": service.analyzeAllChains,
            "clearPdb": service.clearPdb,
            "saveSettings": service.saveSettings,
            "setTheme": service.setTheme,
            "openReference": service.openReference,
            "uploadStructure": service.uploadStructure,
            "importAnalysis": service.importAnalysis,
        }
        if method in {"closeWindow", "startWindowMove", "startWindowResize"}:
            return jsonify({"ok": True})
        operation = allowed.get(method)
        if operation is None:
            return jsonify({"ok": False, "error": "Unknown operation."}), 404
        try:
            with lock:
                return jsonify(operation(*args))
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.get("/api/download-pdb")
    def download_pdb():
        with lock:
            if not service.downloadable_pdb_id or not service.current_pdb_text:
                return jsonify({"ok": False, "error": "Fetch a PDB structure before downloading it."}), 400
            return send_file(
                BytesIO(service.current_pdb_text.encode("utf-8")),
                mimetype="chemical/x-pdb",
                as_attachment=True,
                download_name=f"{service.downloadable_pdb_id}.pdb",
            )

    @app.get("/api/export-analysis")
    def export_analysis():
        with lock:
            if service.last_analysis is None:
                return jsonify({"ok": False, "error": "Run an analysis before exporting it."}), 400
            name = re.sub(
                r"[^\w.-]+", "_", request.args.get("name", "Protein"), flags=re.UNICODE
            ) or "Protein"
            report = build_analysis_markdown(service.last_analysis)
            return send_file(
                BytesIO(report.encode("utf-8")),
                mimetype="text/markdown",
                as_attachment=True,
                download_name=f"{name}.md",
            )

    return app