from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import threading
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from pdb_utils import parse_pdb_chains
from protein_analysis import normalize_sequence


PROJECT_ROOT = Path(__file__).resolve().parent
TESTS_DIR = PROJECT_ROOT / "tests"
CONFIG_PATH = TESTS_DIR / "online_validation.json"
STATE_PATH = TESTS_DIR / "test_run_state.json"
JUNIT_PATH = TESTS_DIR / "test-results.xml"
HTML_PATH = PROJECT_ROOT / "test-report.html"
MAX_UPLOAD_CHARACTERS = 5_000_000
STRUCTURE_SUFFIXES = {".pdb", ".ent", ".cif", ".mmcif"}
SEQUENCE_SUFFIXES = {".fa", ".fasta", ".faa", ".txt"}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "sequence": "",
        "sequence_file": "",
        "pdb_id": "",
        "chain_id": "",
        "structure_file": "",
        "service_email": "",
    }


def _default_state() -> dict[str, Any]:
    return {
        "running": False,
        "running_mode": "",
        "last_run_at": "",
        "last_run_mode": "",
        "results": {},
        "logs": "",
    }


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default.copy()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _nonempty_sequence(text: str, label: str, issues: list[str]) -> bool:
    sequence, invalid = normalize_sequence(text)
    if not sequence:
        issues.append(f"{label} must contain at least one valid amino-acid residue.")
        return False
    if invalid:
        issues.append(
            f"{label} contains invalid symbols: {', '.join(invalid)}."
        )
        return False
    return True


class TestRunner:
    """Runs pytest asynchronously and keeps the latest result for each test."""

    __test__ = False

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._fallback_state: dict[str, Any] | None = None

    def status(self) -> dict[str, object]:
        with self._lock:
            try:
                state = _read_json(STATE_PATH, _default_state())
            except ValueError as exc:
                if self._fallback_state is None:
                    return {"ok": False, "error": str(exc)}
                state = self._fallback_state
            fallback = self._fallback_state
            if fallback and fallback.get("run_id") == state.get("run_id"):
                state = fallback
            try:
                config = _read_json(CONFIG_PATH, _default_config())
            except ValueError as exc:
                return {"ok": False, "error": str(exc)}
            stored_results = state.get("results", {})
            if not isinstance(stored_results, dict):
                return {"ok": False, "error": "Test run state has invalid results data."}
            results = list(stored_results.values())
            return {
                "ok": True,
                "running": bool(state.get("running")),
                "runningMode": state.get("running_mode", ""),
                "lastRunAt": state.get("last_run_at", ""),
                "lastRunMode": state.get("last_run_mode", ""),
                "results": results,
                "logs": state.get("logs", ""),
                "lastError": state.get("last_error", ""),
                "inputs": {
                    "sequence": config.get("sequence", ""),
                    "pdbId": config.get("pdb_id", ""),
                    "chainId": config.get("chain_id", ""),
                    "structureFile": config.get("structure_file", ""),
                    "sequenceFile": config.get("sequence_file", ""),
                    "serviceEmail": config.get("service_email", ""),
                },
            }

    def start(
        self,
        mode: str,
        settings_json: str,
        file_name: str = "",
        file_content: str = "",
        clear_file: bool = False,
    ) -> dict[str, object]:
        if mode not in {"offline", "online", "all"}:
            return {"ok": False, "error": "Choose offline, online, or all tests."}
        try:
            values = json.loads(settings_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid testing inputs: {exc.msg}"}
        if not isinstance(values, dict):
            return {"ok": False, "error": "Testing inputs must be an object."}

        with self._lock:
            try:
                state = _read_json(STATE_PATH, _default_state())
                previous = _read_json(CONFIG_PATH, _default_config())
            except ValueError as exc:
                return {"ok": False, "error": str(exc)}
            if state.get("running"):
                return {"ok": False, "error": "A test run is already in progress."}

            config, staged_file, issues = self._validated_config(
                mode,
                values,
                previous,
                file_name,
                file_content,
                clear_file,
            )
            if issues:
                return {"ok": False, "issues": issues}
            if not importlib.util.find_spec("pytest") or not importlib.util.find_spec(
                "pytest_html"
            ):
                return {
                    "ok": False,
                    "error": "Install testing dependencies first: "
                    "python -m pip install -r requirements-dev.txt",
                }

            if staged_file:
                target, content = staged_file
                try:
                    target.write_text(content, encoding="utf-8")
                except OSError as exc:
                    return {"ok": False, "error": f"Unable to save test input file: {exc}"}
            try:
                _write_json_atomic(CONFIG_PATH, config)
            except OSError as exc:
                return {"ok": False, "error": f"Unable to save testing inputs: {exc}"}

            run_id = uuid.uuid4().hex
            state.update(
                {
                    "running": True,
                    "running_mode": mode,
                    "run_id": run_id,
                    "logs": "",
                    "last_error": "",
                }
            )
            try:
                _write_json_atomic(STATE_PATH, state)
            except OSError as exc:
                return {"ok": False, "error": f"Unable to save test run state: {exc}"}
            self._fallback_state = state
            self._thread = threading.Thread(
                target=self._run_tests,
                args=(mode, run_id),
                name=f"protein-analysis-tests-{run_id[:8]}",
                daemon=True,
            )
            try:
                self._thread.start()
            except RuntimeError as exc:
                state.update(
                    {
                        "running": False,
                        "running_mode": "",
                        "last_error": f"Unable to start test process: {exc}",
                    }
                )
                self._fallback_state = state
                try:
                    _write_json_atomic(STATE_PATH, state)
                except OSError:
                    pass
                return {"ok": False, "error": state["last_error"]}
            return {"ok": True, "runId": run_id, "mode": mode}

    def _validated_config(
        self,
        mode: str,
        values: dict[str, Any],
        previous: dict[str, Any],
        file_name: str,
        file_content: str,
        clear_file: bool,
    ) -> tuple[dict[str, Any], tuple[Path, str] | None, list[str]]:
        issues: list[str] = []
        config = _default_config()
        for key in ("sequence", "pdb_id", "chain_id", "structure_file",
                    "sequence_file", "service_email"):
            old_value = previous.get(key, "")
            new_value = values.get(
                {
                    "pdb_id": "pdbId",
                    "chain_id": "chainId",
                    "service_email": "serviceEmail",
                    "structure_file": "structureFile",
                    "sequence_file": "sequenceFile",
                }.get(key, key),
                old_value,
            )
            if not isinstance(new_value, str):
                issues.append(f"{key} must be text.")
                continue
            config[key] = new_value.strip() if key != "sequence" else new_value

        staged_file = None
        if clear_file:
            config["structure_file"] = ""
            config["sequence_file"] = ""
        elif file_name:
            if not isinstance(file_content, str) or not file_content.strip():
                issues.append("The selected file is empty or could not be read.")
            elif len(file_content) > MAX_UPLOAD_CHARACTERS:
                issues.append("The selected file is larger than the 5 MB limit.")
            else:
                suffix = Path(file_name).suffix.lower()
                if suffix in STRUCTURE_SUFFIXES:
                    chains = parse_pdb_chains(file_content)
                    if not chains:
                        issues.append(
                            "The selected structure file contains no protein chains."
                        )
                    else:
                        chain_id = config["chain_id"]
                        if chain_id and chain_id not in chains:
                            issues.append(
                                f"Chain {chain_id!r} is not present in the selected file."
                            )
                        stored = TESTS_DIR / f"online_test_structure{suffix}"
                        config["structure_file"] = str(stored)
                        config["sequence_file"] = ""
                        staged_file = (stored, file_content)
                elif suffix in SEQUENCE_SUFFIXES:
                    sequence, invalid = normalize_sequence(file_content)
                    if not sequence:
                        issues.append(
                            "The selected sequence file has no valid amino-acid sequence."
                        )
                    if invalid:
                        issues.append(
                            "The selected sequence file contains invalid symbols: "
                            + ", ".join(invalid)
                            + "."
                        )
                    stored = TESTS_DIR / f"online_test_sequence{suffix}"
                    config["sequence_file"] = str(stored)
                    config["structure_file"] = ""
                    staged_file = (stored, file_content)
                else:
                    issues.append(
                        "Choose a PDB, ENT, CIF, mmCIF, FASTA, or text file."
                    )

        sequence = config["sequence"]
        if sequence.strip():
            _nonempty_sequence(sequence, "Sequence", issues)

        pdb_id = config["pdb_id"]
        if pdb_id and not re.fullmatch(r"[A-Za-z0-9]{4}", pdb_id):
            issues.append("PDB ID must contain exactly four letters or digits.")
        if config["chain_id"] and len(config["chain_id"]) > 32:
            issues.append("Chain ID must be 32 characters or fewer.")
        if (
            mode in {"online", "all"}
            and config["service_email"]
            and not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                config["service_email"],
            )
        ):
            issues.append("EMBL-EBI contact email must be a valid email address.")

        for key, label in (
            ("sequence_file", "Saved sequence file"),
            ("structure_file", "Saved structure file"),
        ):
            configured_path = config[key]
            if configured_path and not (staged_file and staged_file[0] == Path(configured_path)):
                path = Path(configured_path)
                if not path.is_file():
                    issues.append(f"{label} was not found: {path.name}.")
                elif key == "sequence_file":
                    try:
                        text = path.read_text(encoding="utf-8-sig")
                    except (OSError, UnicodeError) as exc:
                        issues.append(f"{label} could not be read: {exc}")
                    else:
                        _nonempty_sequence(text, label, issues)
                else:
                    try:
                        text = path.read_text(encoding="utf-8", errors="replace")
                    except OSError as exc:
                        issues.append(f"{label} could not be read: {exc}")
                    else:
                        chains = parse_pdb_chains(text)
                        if not chains:
                            issues.append(f"{label} contains no protein chains.")
                        elif config["chain_id"] and config["chain_id"] not in chains:
                            issues.append(
                                f"Chain {config['chain_id']!r} is not present in {label.lower()}."
                            )

        config["enabled"] = mode in {"online", "all"}
        return config, staged_file, issues

    def _run_tests(self, mode: str, run_id: str) -> None:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-v",
            f"--junitxml={JUNIT_PATH}",
            f"--html={HTML_PATH}",
            "--self-contained-html",
        ]
        if mode == "offline":
            command.extend(["-m", "not online"])
        elif mode == "online":
            command.extend(["-m", "online", "--run-online"])
        else:
            command.append("--run-online")

        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            results = self._parse_junit_results()
            logs = (completed.stdout + "\n" + completed.stderr).strip()
            failure = "" if completed.returncode == 0 else (
                f"pytest exited with code {completed.returncode}."
            )
            if not results and completed.returncode != 0:
                failure += " No per-test results were available."
            self._finish_run(run_id, mode, results, logs, failure)
        except (OSError, ET.ParseError, ValueError) as exc:
            self._finish_run(
                run_id,
                mode,
                [],
                "",
                f"Unable to execute or read pytest results: {exc}",
            )

    def _parse_junit_results(self) -> list[dict[str, Any]]:
        if not JUNIT_PATH.is_file():
            return []
        root = ET.parse(JUNIT_PATH).getroot()
        results = []
        for case in root.findall(".//testcase"):
            properties = {
                item.get("name", ""): item.get("value", "")
                for item in case.findall("./properties/property")
            }
            outcome = "passed"
            details = ""
            for tag, status in (
                ("failure", "failed"),
                ("error", "failed"),
                ("skipped", "skipped"),
            ):
                element = case.find(tag)
                if element is not None:
                    outcome = status
                    details = "\n".join(
                        part
                        for part in (
                            element.get("message", ""),
                            (element.text or "").strip(),
                        )
                        if part
                    )
                    break
            case_info = self._json_property(properties.get("case_info", ""))
            comparisons = self._json_property(
                properties.get("case_comparisons", "")
            )
            if not isinstance(comparisons, list):
                comparisons = []
            links = []
            for comparison in comparisons:
                if isinstance(comparison, dict) and comparison.get("reference_url"):
                    links.append(str(comparison["reference_url"]))
            system_output = case.findtext("system-out", default="").strip()
            if system_output and not details:
                details = system_output[-3000:]
            class_name = case.get("classname", "")
            test_name = case.get("name", "")
            test_id = f"{class_name}::{test_name}"
            results.append(
                {
                    "id": test_id,
                    "name": test_name,
                    "suite": class_name,
                    "group": properties.get("test_group", "offline"),
                    "result": outcome,
                    "duration": float(case.get("time", "0") or 0),
                    "link": links[0] if links else "",
                    "case": case_info if isinstance(case_info, dict) else {},
                    "comparisons": comparisons,
                    "notes": details,
                    "runAt": _now(),
                }
            )
        return results

    @staticmethod
    def _json_property(value: str) -> Any:
        if not value:
            return {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _merge_results(
        previous: dict[str, Any],
        results: list[dict[str, Any]],
        mode: str,
    ) -> dict[str, Any]:
        if not results:
            return previous
        merged = {
            key: value
            for key, value in previous.items()
            if mode != "all"
            and isinstance(value, dict)
            and value.get("group", "offline") != mode
        }
        for result in results:
            merged[result["id"]] = result
        return merged

    def _finish_run(
        self,
        run_id: str,
        mode: str,
        results: list[dict[str, Any]],
        logs: str,
        error: str,
    ) -> None:
        with self._lock:
            try:
                state = _read_json(STATE_PATH, _default_state())
                if state.get("run_id") != run_id:
                    return
                previous_results = state.get("results", {})
                if not isinstance(previous_results, dict):
                    previous_results = {}
                updated_results = self._merge_results(
                    previous_results, results, mode
                )
                state.update(
                    {
                        "running": False,
                        "running_mode": "",
                        "last_run_at": _now(),
                        "last_run_mode": mode,
                        "results": updated_results,
                        "logs": logs[-12000:],
                        "last_error": error,
                    }
                )
                _write_json_atomic(STATE_PATH, state)
                self._fallback_state = state
            except (OSError, ValueError) as exc:
                fallback = self._fallback_state or _default_state()
                previous_results = fallback.get("results", {})
                if not isinstance(previous_results, dict):
                    previous_results = {}
                updated_results = self._merge_results(
                    previous_results, results, mode
                )
                fallback.update(
                    {
                        "running": False,
                        "running_mode": "",
                        "last_run_at": _now(),
                        "last_run_mode": mode,
                        "results": updated_results,
                        "last_error": (
                            f"Test results could not be saved to disk: {exc}"
                        ),
                        "logs": logs[-12000:],
                    }
                )
                self._fallback_state = fallback
                return
