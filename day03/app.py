from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, Sequence

from PySide6.QtCore import QSettings, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from pdb_utils import fetch_pdb_text, parse_pdb_chains
from protein_analysis import (
    AA_NAMES,
    AA_TO_THREE,
    ExtendedMetrics,
    HYDROPHOBICITY,
    ProteinStats,
    calculate_extended_metrics,
    calculate_protein_stats,
    hydrophobicity_profile,
    normalize_sequence,
)
from reporting import build_analysis_markdown, export_report, read_analysis_markdown


class AnalysisBridge:
    """Python operations exposed to the trusted, local web interface."""

    def __init__(self, window: WebAnalyzerWindow) -> None:
        from PySide6.QtCore import QObject

        class BridgeObject(QObject):
            systemThemeChanged = Signal(str)

            def __init__(self, owner: AnalysisBridge) -> None:
                super().__init__(window)
                self.owner = owner

            @Slot(result=str)
            def getInitialState(self) -> str:
                return self.owner._json(self.owner.initial_state())

            @Slot(str, str, str, result=str)
            def analyzeSequence(self, sequence: str, name: str, context: str) -> str:
                return self.owner._json(
                    self.owner.analyzeSequence(sequence, name, context)
                )

            @Slot(str, result=str)
            def fetchPdb(self, pdb_id: str) -> str:
                return self.owner._json(self.owner.fetchPdb(pdb_id))

            @Slot(str, str, result=str)
            def analyzeChain(self, pdb_id: str, chain_id: str) -> str:
                return self.owner._json(self.owner.analyzeChain(pdb_id, chain_id))

            @Slot(str, result=str)
            def analyzeAllChains(self, pdb_id: str) -> str:
                return self.owner._json(self.owner.analyzeAllChains(pdb_id))

            @Slot(str, str, str, result=str)
            def analyzeAntibody(self, heavy: str, light: str, antibody_type: str) -> str:
                return self.owner._json(
                    self.owner.analyzeAntibody(heavy, light, antibody_type)
                )

            @Slot(result=str)
            def openFasta(self) -> str:
                return self.owner._json(self.owner.openFasta())

            @Slot(result=str)
            def openAnalysis(self) -> str:
                return self.owner._json(self.owner.openAnalysis())

            @Slot(str, result=str)
            def exportReport(self, name: str) -> str:
                return self.owner._json(self.owner.exportReport(name))

            @Slot(str, result=str)
            def exportAnalysis(self, name: str) -> str:
                return self.owner._json(self.owner.exportAnalysis(name))

            @Slot(str, result=str)
            def saveSettings(self, settings_json: str) -> str:
                return self.owner._json(self.owner.saveSettings(settings_json))

            @Slot(str, result=str)
            def setTheme(self, mode: str) -> str:
                return self.owner._json(self.owner.setTheme(mode))

            @Slot(str, result=str)
            def openReference(self, reference: str) -> str:
                return self.owner._json(self.owner.openReference(reference))

            @Slot(result=bool)
            def toggleMaximized(self) -> bool:
                return self.owner.window.toggleMaximized()

            @Slot(result=bool)
            def toggleFullScreen(self) -> bool:
                return self.owner.window.toggleFullScreen()

            @Slot(result=str)
            def closeWindow(self) -> str:
                self.owner.window.close()
                return self.owner._json({"ok": True})

            @Slot(result=str)
            def startWindowMove(self) -> str:
                return self.owner._json(self.owner.window.startSystemMove())

            @Slot(str, result=str)
            def startWindowResize(self, edge: str) -> str:
                return self.owner._json(self.owner.window.startSystemResize(edge))

        self.window = window
        self.settings = window.settings
        self.last_stats: ProteinStats | None = None
        self.last_analysis: dict[str, object] | None = None
        self.last_name = "Protein"
        self.last_context = ""
        self.pdb_chains: Dict[str, str] = {}
        self.active_pdb_chains: Dict[str, str] | None = None
        self.current_pdb_id = ""
        self.bridge_object = BridgeObject(self)
        QApplication.instance().styleHints().colorSchemeChanged.connect(
            self._on_system_color_scheme_changed
        )

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    def initial_state(self) -> dict[str, object]:
        categories = {
            key: self._setting_enabled(f"categories/{key}", True)
            for key in WebAnalyzerWindow.CATEGORY_LABELS
        }
        categories["overview"] = True
        return {
            "themeMode": self.settings.value("theme_mode", "Dark"),
            "effectiveTheme": self._effective_theme(),
            "fontSize": self._font_size(),
            "startMaximized": self._setting_enabled("start_maximized", True),
            "fullScreen": self._setting_enabled("full_screen", False),
            "enableReferenceLinks": self._setting_enabled(
                "enable_reference_links", False
            ),
            "categories": categories,
            "categoryLabels": WebAnalyzerWindow.CATEGORY_LABELS,
        }

    def analyzeSequence(
        self, sequence: str, name: str, context: str
    ) -> dict[str, object]:
        cleaned, invalid = normalize_sequence(sequence)
        if not cleaned:
            return {"ok": False, "error": "Enter a valid protein sequence first."}
        try:
            stats = calculate_protein_stats(sequence)
            metrics = calculate_extended_metrics(sequence)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if context not in {"protein", "structure"}:
            context = "protein"
        if context != "structure":
            self.active_pdb_chains = None
            self.current_pdb_id = ""
        return self._record_analysis(stats, metrics, name, context, invalid)

    def _record_analysis(
        self,
        stats: ProteinStats,
        metrics: ExtendedMetrics,
        name: str,
        context: str,
        invalid: Sequence[str] = (),
    ) -> dict[str, object]:
        self.last_stats = stats
        self.last_name = name.strip() or "Protein"
        self.last_context = context
        payload = self._protein_payload(stats, metrics, self.last_name, context)
        payload["invalidCharacters"] = list(invalid)
        if context == "structure" and self.active_pdb_chains:
            chain_sequences = sorted(self.active_pdb_chains.items())
        else:
            chain_sequences = [("Sequence", stats.sequence)]
        payload["analysisChains"] = (
            [chain_id for chain_id, _sequence in chain_sequences]
            if context == "structure"
            else []
        )
        residue_details = []
        position = 0
        for chain_id, sequence in chain_sequences:
            for residue_number, residue in enumerate(sequence, start=1):
                position += 1
                residue_details.append(
                    {
                        "position": position,
                        "residueNumber": residue_number,
                        "chain": chain_id,
                        "residue": residue,
                        "fullName": AA_NAMES.get(residue, "Ambiguous residue"),
                        "abbreviation": AA_TO_THREE.get(residue, "UNK"),
                        "value": HYDROPHOBICITY.get(residue, 0.0),
                    }
                )
        payload["residueDetails"] = residue_details
        payload["pdbId"] = self.current_pdb_id if context == "structure" else ""
        payload["pdbChains"] = [
            {"id": chain_id, "length": len(chain)}
            for chain_id, chain in sorted(self.pdb_chains.items())
        ] if context == "structure" else []
        self.last_analysis = payload
        return {"ok": True, "analysis": payload}

    @staticmethod
    def _protein_payload(
        stats: ProteinStats,
        metrics: dict[str, object],
        name: str,
        context: str,
    ) -> dict[str, object]:
        composition = [
            {
                "residue": residue,
                "fullName": AA_NAMES.get(residue, "Ambiguous residue"),
                "abbreviation": AA_TO_THREE.get(residue, "UNK"),
                "count": count,
                "percent": count / stats.length * 100,
                "hydrophobicityValue": HYDROPHOBICITY.get(residue, 0.0),
            }
            for residue, count in sorted(stats.composition.items())
            if residue in AA_NAMES
        ]
        chemistry = [
            ["Positive residues (K/R/H)", metrics["positive_residues"]],
            ["Negative residues (D/E)", metrics["negative_residues"]],
            ["Basic residues", f'{metrics["basic_residue_percent"]:.2f}%'],
            ["Acidic residues", f'{metrics["acidic_residue_percent"]:.2f}%'],
            ["Aliphatic index", f'{metrics["aliphatic_index"]:.2f}'],
            [
                "Shannon entropy (standard residues)",
                f'{metrics["shannon_entropy_bits"]:.3f} bits/residue',
            ],
            ["Cysteines", metrics["cysteine_count"]],
            [
                "Potential disulfide pairs (upper bound)",
                metrics["potential_disulfide_pairs"],
            ],
        ]

        def display_positions(values: Sequence[int]) -> str:
            return ", ".join(str(value) for value in values) if values else "None detected"

        def display_regions(values: Sequence[Sequence[int]]) -> str:
            return ", ".join(f"{start}-{end}" for start, end in values) or "None detected"

        features = [
            [
                "N-linked glycosylation sequons (N-X-S/T, X ≠ P; 1-based start)",
                display_positions(metrics["n_glycosylation_sequon_positions"]),
            ],
            [
                "Trypsin cleavage positions (after K/R; 1-based)",
                display_positions(metrics["trypsin_cleavage_positions"]),
            ],
            [
                f'Hydrophobic windows (Kyte-Doolittle, window {metrics["hydrophobicity_window_size"]}, mean ≥ 1.6)',
                display_regions(metrics["hydrophobic_regions"]),
            ],
            [
                "Transmembrane-like hydrophobic regions (19 aa, heuristic)",
                display_regions(metrics["transmembrane_regions"]),
            ],
            [
                "Serine/threonine-rich regions (10 aa, ≥ 50%; heuristic)",
                display_regions(metrics["serine_threonine_rich_regions"]),
            ],
            [
                "Low-complexity regions (12 aa, ≥ 60% one residue; heuristic)",
                display_regions(metrics["low_complexity_regions"]),
            ],
            [
                "Potential phosphorylation residues (S/T/Y; not kinase-specific)",
                display_positions(metrics["phosphorylation_candidate_positions"]),
            ],
            [
                "Cysteine positions",
                display_positions(metrics["cysteine_positions"]),
            ],
            [
                "N-terminal signal-peptide cleavage candidates (heuristic -3/-1 rule)",
                display_positions(metrics["signal_peptide_cleavage_candidates"]),
            ],
        ]
        return {
            "context": context,
            "name": name,
            "sequence": stats.sequence,
            "molecularWeight": stats.molecular_weight,
            "cards": [
                ["Length", f"{stats.length} aa"],
                ["Molecular weight", f"{stats.molecular_weight:.2f} Da"],
                ["Theoretical pI", f"{stats.theoretical_pI:.2f}"],
                ["GRAVY", f"{stats.gravy:.3f}"],
                ["Aromaticity", f"{stats.aromaticity:.1%}"],
                ["Extinction coefficient", f"{stats.extinction_coefficient:.0f}"],
            ],
            "overview": stats.table_rows(),
            "composition": composition,
            "hydrophobicity": hydrophobicity_profile(stats.sequence, window_size=7),
            "chemistry": chemistry,
            "charge": [
                [f"{ph:g}", f"{charge:.3f}"]
                for ph, charge in metrics["charge_profile"]
            ],
            "features": features,
            "cleavageSites": metrics["cleavage_sites"],
            "signalPeptideCleavageCandidates": metrics[
                "signal_peptide_cleavage_candidates"
            ],
            "structure": context == "structure",
            "metrics": metrics,
        }

    def fetchPdb(self, pdb_id: str) -> dict[str, object]:
        identifier = pdb_id.strip().upper()
        try:
            pdb_text = fetch_pdb_text(identifier)
            chains = parse_pdb_chains(pdb_text)
        except (RuntimeError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        if not chains:
            return {"ok": False, "error": "No protein chain data was found in that structure."}
        self.pdb_chains = chains
        self.current_pdb_id = identifier
        self.active_pdb_chains = None
        self.last_stats = None
        self.last_analysis = None
        self.last_context = ""
        first_chain = sorted(chains)[0]
        return {
            "ok": True,
            "pdbId": identifier,
            "selectedChain": first_chain,
            "chains": [
                {"id": chain_id, "length": len(sequence)}
                for chain_id, sequence in sorted(chains.items())
            ],
        }

    def analyzeChain(self, pdb_id: str, chain_id: str) -> dict[str, object]:
        if pdb_id.strip().upper() != self.current_pdb_id:
            return {"ok": False, "error": "Fetch this PDB structure before selecting a chain."}
        sequence = self.pdb_chains.get(chain_id)
        if sequence is None:
            return {"ok": False, "error": "Select an available protein chain."}
        self.active_pdb_chains = {chain_id: sequence}
        return self.analyzeSequence(
            sequence, f"PDB {pdb_id.strip().upper()} chain {chain_id}", "structure"
        )

    def analyzeAllChains(self, pdb_id: str) -> dict[str, object]:
        if pdb_id.strip().upper() != self.current_pdb_id or not self.pdb_chains:
            return {"ok": False, "error": "Fetch this PDB structure before analyzing its chains."}
        self.active_pdb_chains = dict(self.pdb_chains)
        sequence = "".join(
            chain for _chain_id, chain in sorted(self.active_pdb_chains.items())
        )
        identifier = self.current_pdb_id
        return self.analyzeSequence(
            sequence, f"PDB {identifier} all chains", "structure"
        )

    def analyzeAntibody(
        self, heavy: str, light: str, antibody_type: str
    ) -> dict[str, object]:
        heavy_sequence, heavy_invalid = normalize_sequence(heavy)
        light_sequence, light_invalid = normalize_sequence(light)
        if not heavy_sequence and not light_sequence:
            return {
                "ok": False,
                "error": "Enter at least one heavy- or light-chain sequence.",
            }

        rows: list[list[object]] = []
        total_length = 0
        total_mass = 0.0
        for label, sequence in (
            ("Heavy chain", heavy_sequence),
            ("Light chain", light_sequence),
        ):
            if not sequence:
                continue
            stats = calculate_protein_stats(sequence)
            rows.append([label, stats.length, f"{stats.molecular_weight:.2f} Da"])
            total_length += stats.length
            total_mass += stats.molecular_weight
        rows.append(
            ["Entered chains total", total_length, f"{total_mass:.2f} Da"]
        )
        invalid = sorted(set(heavy_invalid + light_invalid))
        invalid_note = f' Ignored symbols: {", ".join(invalid)}.' if invalid else ""
        summary = (
            f"{antibody_type} sequence summary · heavy {len(heavy_sequence)} aa · "
            f"light {len(light_sequence)} aa · total {total_length} aa · "
            f"approximate chain-sum mass {total_mass:.2f} Da.{invalid_note}"
        )
        self.last_stats = None
        self.last_context = "antibody"
        self.last_name = f"{antibody_type} antibody"
        self.active_pdb_chains = None
        self.current_pdb_id = ""
        analysis = {
            "name": self.last_name,
            "ok": True,
            "context": "antibody",
            "antibodyType": antibody_type,
            "heavySequence": heavy_sequence,
            "lightSequence": light_sequence,
            "summary": summary,
            "rows": rows,
            "invalidCharacters": invalid,
        }
        self.last_analysis = analysis
        return {"ok": True, "analysis": analysis}

    def openFasta(self) -> dict[str, object]:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Import protein sequence",
            "",
            "FASTA / text files (*.fasta *.fa *.faa *.txt);;All files (*)",
        )
        if not path:
            return {"ok": False, "cancelled": True}
        try:
            contents = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "contents": contents, "name": Path(path).stem}

    def openAnalysis(self) -> dict[str, object]:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Import analysis",
            "",
            "Protein Analysis Studio Markdown (*.md);;All files (*)",
        )
        if not path:
            return {"ok": False, "cancelled": True}
        try:
            imported = read_analysis_markdown(path)
            context = imported["context"]
            if context == "antibody":
                heavy = imported.get("heavySequence")
                light = imported.get("lightSequence")
                antibody_type = imported.get("antibodyType", "Antibody")
                if not isinstance(heavy, str) or not isinstance(light, str):
                    raise ValueError("The antibody sequences are missing from this file.")
                result = self.analyzeAntibody(heavy, light, str(antibody_type))
            else:
                sequence = imported.get("sequence")
                name = imported.get("name")
                if not isinstance(sequence, str) or not isinstance(name, str):
                    raise ValueError("The protein sequence or name is missing.")
                cleaned_sequence, invalid_symbols = normalize_sequence(sequence)
                if invalid_symbols or cleaned_sequence != sequence:
                    raise ValueError("The stored protein sequence is invalid.")
                if context == "structure":
                    chains = imported.get("analysisChains")
                    details = imported.get("residueDetails")
                    pdb_id = imported.get("pdbId")
                    if (
                        not isinstance(chains, list)
                        or not chains
                        or not all(isinstance(chain, str) for chain in chains)
                        or len(set(chains)) != len(chains)
                        or chains != sorted(chains)
                        or not isinstance(details, list)
                        or not isinstance(pdb_id, str)
                        or not re.fullmatch(r"[A-Z0-9]{4}", pdb_id)
                    ):
                        raise ValueError("The structure metadata is incomplete.")
                    grouped = {chain: [] for chain in chains}
                    for detail in details:
                        if not isinstance(detail, dict):
                            raise ValueError("The residue metadata is malformed.")
                        chain = detail.get("chain")
                        residue = detail.get("residue")
                        if chain not in grouped or not isinstance(residue, str):
                            raise ValueError("The residue metadata is malformed.")
                        grouped[chain].append(residue)
                    chain_sequences = {
                        chain: "".join(residues)
                        for chain, residues in grouped.items()
                    }
                    if "".join(chain_sequences[key] for key in sorted(chain_sequences)) != sequence:
                        raise ValueError("The stored chain sequences do not match the protein sequence.")
                    self.pdb_chains = chain_sequences
                    self.active_pdb_chains = chain_sequences.copy()
                    self.current_pdb_id = pdb_id
                result = self.analyzeSequence(sequence, name, str(context))
            if not result.get("ok"):
                return result
            return {"ok": True, "analysis": result["analysis"]}
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            return {"ok": False, "error": str(exc)}

    def exportAnalysis(self, name: str) -> dict[str, object]:
        if self.last_analysis is None:
            return {"ok": False, "error": "Run an analysis before exporting it."}
        safe_name = re.sub(r"[^\w.-]+", "_", name.strip(), flags=re.UNICODE) or "Protein"
        path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export analysis",
            f"{safe_name}.md",
            "Markdown analysis (*.md)",
        )
        if not path:
            return {"ok": False, "cancelled": True}
        if Path(path).suffix.lower() != ".md":
            path += ".md"
        try:
            Path(path).write_text(
                build_analysis_markdown(self.last_analysis), encoding="utf-8"
            )
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "message": f"Analysis exported to {path}"}

    def exportReport(self, name: str) -> dict[str, object]:
        if self.last_stats is None:
            return {
                "ok": False,
                "error": "Report export is available for protein sequence analyses.",
            }
        safe_name = re.sub(r"[^\w.-]+", "_", name.strip(), flags=re.UNICODE) or "Protein"
        path, selected_filter = QFileDialog.getSaveFileName(
            self.window,
            "Export analysis report",
            f"{safe_name}.html",
            "HTML report (*.html);;JSON data (*.json);;CSV table (*.csv);;Text report (*.txt)",
        )
        if not path:
            return {"ok": False, "cancelled": True}
        if Path(path).suffix.lower() not in {".html", ".htm", ".json", ".csv", ".txt"}:
            suffix = {
                "JSON data (*.json)": ".json",
                "CSV table (*.csv)": ".csv",
                "Text report (*.txt)": ".txt",
            }.get(selected_filter, ".html")
            path += suffix
        try:
            export_report(path, self.last_stats, self.last_name)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "message": f"Report exported to {path}"}

    def saveSettings(self, settings_json: str) -> dict[str, object]:
        try:
            values = json.loads(settings_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid settings: {exc.msg}"}
        if not isinstance(values, dict):
            return {"ok": False, "error": "Settings must be an object."}
        font_size = values.get("fontSize", self._font_size())
        if type(font_size) is not int or not 8 <= font_size <= 24:
            return {"ok": False, "error": "Font size must be from 8 to 24."}
        start_maximized = values.get("startMaximized", True)
        if not isinstance(start_maximized, bool):
            return {"ok": False, "error": "Startup window preference must be true or false."}
        full_screen = values.get("fullScreen", False)
        if not isinstance(full_screen, bool):
            return {"ok": False, "error": "Full-screen preference must be true or false."}
        enable_reference_links = values.get(
            "enableReferenceLinks",
            self._setting_enabled("enable_reference_links", False),
        )
        if not isinstance(enable_reference_links, bool):
            return {"ok": False, "error": "Reference links must be true or false."}
        categories = values.get("categories", {})
        if not isinstance(categories, dict):
            return {"ok": False, "error": "Result categories must be an object."}
        if any(
            key not in WebAnalyzerWindow.CATEGORY_LABELS
            or not isinstance(enabled, bool)
            for key, enabled in categories.items()
        ):
            return {"ok": False, "error": "Each result category must have a valid boolean setting."}
        self.settings.setValue("font_size", font_size)
        self.settings.setValue("start_maximized", start_maximized)
        self.settings.setValue("full_screen", full_screen)
        self.settings.setValue("enable_reference_links", enable_reference_links)
        for key in WebAnalyzerWindow.CATEGORY_LABELS:
            if key == "overview":
                continue
            if key in categories:
                self.settings.setValue(
                    f"categories/{key}", bool(categories[key])
                )
        self.window.applyWindowMode(full_screen, start_maximized)
        return {"ok": True, "settings": self.initial_state()}

    def openReference(self, reference: str) -> dict[str, object]:
        if not self._setting_enabled("enable_reference_links", False):
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
        url = references.get(reference)
        if reference.startswith("pdb:"):
            identifier = reference[4:].upper()
            if (
                not re.fullmatch(r"[A-Z0-9]{4}", identifier)
                or identifier != self.current_pdb_id
            ):
                return {"ok": False, "error": "The PDB reference is no longer available."}
            url = f"https://www.rcsb.org/structure/{identifier}"
        if url is None:
            return {"ok": False, "error": "This reference is not available."}
        if not QDesktopServices.openUrl(QUrl(url)):
            return {"ok": False, "error": "The reference could not be opened in a browser."}
        return {"ok": True}

    def setTheme(self, mode: str) -> dict[str, object]:
        if mode not in {"Dark", "Light", "System"}:
            return {"ok": False, "error": "Choose Dark, Light, or System theme."}
        self.settings.setValue("theme_mode", mode)
        return {
            "ok": True,
            "themeMode": mode,
            "effectiveTheme": self._effective_theme(),
        }

    def _setting_enabled(self, key: str, default: bool) -> bool:
        value = self.settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _font_size(self) -> int:
        try:
            size = int(self.settings.value("font_size", "12"))
        except (TypeError, ValueError):
            return 12
        return min(24, max(8, size))

    def _effective_theme(self) -> str:
        mode = self.settings.value("theme_mode", "Dark")
        if mode in {"Dark", "Light"}:
            return str(mode).lower()
        scheme = QApplication.instance().styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Light:
            return "light"
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        window_color = QApplication.instance().palette().window().color()
        return "dark" if window_color.lightness() < 128 else "light"

    def _on_system_color_scheme_changed(self, _scheme) -> None:
        if self.settings.value("theme_mode", "Dark") == "System":
            self.bridge_object.systemThemeChanged.emit(self._effective_theme())


class WebAnalyzerWindow(QMainWindow):
    CATEGORY_LABELS = {
        "overview": "Overview",
        "composition": "Composition",
        "hydrophobicity": "Hydrophobicity",
        "chemistry": "Chemistry & charge",
        "features": "Sequence features",
        "cleavage": "Cleavage",
        "antibody": "Antibody",
    }

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("ProteinAnalysisStudio", "Desktop")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Protein Analysis Studio")
        self.resize(1480, 920)
        self.setMinimumSize(980, 660)

        self.web_view = QWebEngineView(self)
        self.web_view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.setCentralWidget(self.web_view)
        self.bridge = AnalysisBridge(self)
        self.web_channel = QWebChannel(self.web_view.page())
        self.web_channel.registerObject("bridge", self.bridge.bridge_object)
        self.web_view.page().setWebChannel(self.web_channel)
        app_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        page_path = (app_root / "web" / "index.html").resolve()
        self.web_view.load(QUrl.fromLocalFile(str(page_path)))

        shortcut = QShortcut(QKeySequence("F11"), self)
        shortcut.activated.connect(self.toggleMaximized)
        if self.bridge._setting_enabled("full_screen", False):
            self.showFullScreen()
        elif self.bridge._setting_enabled("start_maximized", True):
            self.showMaximized()

    def toggleMaximized(self) -> bool:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        return self.isMaximized()

    def toggleFullScreen(self) -> bool:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        return self.isFullScreen()

    def applyWindowMode(self, full_screen: bool, start_maximized: bool) -> None:
        if full_screen:
            self.showFullScreen()
        elif start_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def startSystemMove(self) -> bool:
        window_handle = self.windowHandle()
        return window_handle.startSystemMove() if window_handle is not None else False

    def startSystemResize(self, edge_name: str) -> bool:
        edge_flags = {
            "left": Qt.Edge.LeftEdge,
            "right": Qt.Edge.RightEdge,
            "top": Qt.Edge.TopEdge,
            "bottom": Qt.Edge.BottomEdge,
            "top-left": Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
            "top-right": Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            "bottom-left": Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
            "bottom-right": Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
        }
        edges = edge_flags.get(edge_name)
        window_handle = self.windowHandle()
        if edges is None or window_handle is None:
            return False
        return window_handle.startSystemResize(edges)

def main() -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("Protein Analysis Studio")
    app.setOrganizationName("ProteinAnalysisStudio")
    window = WebAnalyzerWindow()
    window.show()
    return app.exec()
