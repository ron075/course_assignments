import json
import xml.etree.ElementTree as ET

import pytest

import test_runner
from reporting import build_analysis_markdown
from test_online_analysis import _pepstats_summary
from test_runner import TestRunner
from web_app import FlaskAnalysisService, create_app


PDB_TEXT = "SEQRES   1 A    3  ALA CYS ASP\n"


@pytest.mark.case(
    represents="Sequence analysis returns a normalized protein result",
    category="application",
    expected={"ok": True, "name": "Demo", "sequence": "ACD", "length": 3},
)
def test_flask_service_analyzes_sequence_and_reports_core_properties(case_report):
    service = FlaskAnalysisService()
    result = service.analyzeSequence(" acd ", " Demo ", "protein")
    analysis = result["analysis"]
    actual = {
        "ok": result["ok"],
        "name": analysis["name"],
        "sequence": analysis["sequence"],
        "length": analysis["metrics"]["total_atoms"] is not None
        and len(analysis["sequence"]),
    }
    expected = {"ok": True, "name": "Demo", "sequence": "ACD", "length": 3}
    case_report(
        represents="Normalized sequence, chosen name, and residue count",
        expected=expected,
        actual=actual,
        raw_input={"sequence": " acd ", "name": " Demo "},
    )
    assert actual == expected
    assert analysis["metrics"]["formula"] == "C10H17N3O6S"
    assert service.last_stats.length == 3


@pytest.mark.case(
    represents="Empty and invalid sequence analysis errors",
    category="validation",
    expected="Both inputs return a user-readable validation error",
)
@pytest.mark.parametrize("sequence", ["", "123"])
def test_flask_service_rejects_sequence_without_valid_residues(sequence, case_report):
    result = FlaskAnalysisService().analyzeSequence(sequence, "Bad", "protein")
    expected = False
    actual = result["ok"]
    case_report(
        represents="Analysis is not started when no valid amino-acid residues exist",
        expected=expected,
        actual=actual,
        raw_input=sequence,
    )
    assert actual is expected
    assert result["error"]


@pytest.mark.case(
    represents="Custom antibody chain multiplicities and aggregate sequence",
    category="antibody",
    expected={"sequence": "ACACD", "length": 5, "rows": 2},
)
def test_antibody_analysis_applies_chain_counts_to_aggregate(case_report):
    result = FlaskAnalysisService().analyzeAntibody(
        "AC", "D", "Custom", heavy_count=2, light_count=1
    )
    analysis = result["analysis"]
    actual = {
        "sequence": analysis["sequence"],
        "length": len(analysis["sequence"]),
        "rows": len(analysis["rows"]),
    }
    expected = {"sequence": "ACACD", "length": 5, "rows": 2}
    case_report(
        represents="Aggregated sequence, residue count, and chain summary rows",
        expected=expected,
        actual=actual,
        raw_input={"heavy": "AC", "light": "D", "heavy_count": 2, "light_count": 1},
    )
    assert actual == expected
    assert analysis["rows"][0][1:] == [2, 4, "384.46 Da"]
    assert result["ok"] is True


@pytest.mark.case(
    represents="Antibody class and chain-count validation",
    category="validation",
    expected="Unsupported class and invalid chain count are rejected",
)
def test_antibody_analysis_rejects_invalid_class_and_counts(case_report):
    service = FlaskAnalysisService()
    class_error = service.analyzeAntibody("AC", "D", "IgX")
    count_error = service.analyzeAntibody("AC", "D", "Custom", 1.5, 1)
    actual = {
        "class_rejected": class_error["ok"] is False,
        "count_rejected": count_error["ok"] is False,
    }
    expected = {"class_rejected": True, "count_rejected": True}
    case_report(
        represents="Antibody type and copy counts must be supported",
        expected=expected,
        actual=actual,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Structure upload, selected-chain analysis, and clear operation",
    category="structure",
    expected={"selected": "A", "sequence": "ACD", "cleared": True},
)
def test_structure_upload_analyze_chain_and_clear(case_report):
    service = FlaskAnalysisService()
    uploaded = service.uploadStructure("demo.pdb", PDB_TEXT)
    analyzed = service.analyzeChain(uploaded["structureKey"], "A")
    analysis = analyzed["analysis"]
    cleared = service.clearPdb()
    actual = {
        "selected": uploaded["selectedChain"],
        "sequence": analysis["sequence"],
        "cleared": cleared["cleared"],
    }
    expected = {"selected": "A", "sequence": "ACD", "cleared": True}
    case_report(
        represents="Uploaded chain selection, sequence analysis, and state reset",
        expected=expected,
        actual=actual,
        raw_input="One PDB SEQRES record for chain A",
    )
    assert actual == expected
    assert analyzed["ok"] is True
    assert service.current_structure_key == ""


@pytest.mark.case(
    represents="Invalid structure keys and chain IDs do not start analysis",
    category="validation",
    expected="Both chain-selection errors are reported",
)
def test_structure_chain_selection_requires_loaded_key_and_available_chain(case_report):
    service = FlaskAnalysisService()
    service.uploadStructure("demo.pdb", PDB_TEXT)
    stale = service.analyzeChain("stale", "A")
    missing = service.analyzeChain(service.current_structure_key, "Z")
    actual = {"stale_key_rejected": not stale["ok"], "missing_chain_rejected": not missing["ok"]}
    expected = {"stale_key_rejected": True, "missing_chain_rejected": True}
    case_report(
        represents="Structure key and chain ID are validated before calculation",
        expected=expected,
        actual=actual,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Analysis Markdown import reruns the saved sequence analysis",
    category="reporting",
    expected={"name": "Imported", "sequence": "ACD"},
)
def test_service_import_analysis_validates_and_reanalyzes_markdown(case_report):
    markdown = build_analysis_markdown(
        {"context": "protein", "name": "Imported", "sequence": "ACD", "overview": []}
    )
    result = FlaskAnalysisService().importAnalysis(markdown)
    actual = {
        "name": result["analysis"]["name"],
        "sequence": result["analysis"]["sequence"],
    }
    expected = {"name": "Imported", "sequence": "ACD"}
    case_report(
        represents="Imported report produces a fresh analysis with the saved name",
        expected=expected,
        actual=actual,
    )
    assert result["ok"] is True
    assert actual == expected


@pytest.mark.case(
    represents="Settings, theme, and reference-link validation",
    category="settings",
    expected={"fontSize": 16, "themeMode": "Light", "referenceAvailable": True},
)
def test_service_settings_theme_and_reference_preferences(case_report):
    service = FlaskAnalysisService()
    settings = service.saveSettings(
        json.dumps(
            {
                "fontSize": 16,
                "categories": {"overview": False},
                "enableReferenceLinks": True,
            }
        )
    )
    theme = service.setTheme("Light")
    reference = service.openReference("protparam")
    actual = {
        "fontSize": settings["settings"]["fontSize"],
        "themeMode": theme["themeMode"],
        "referenceAvailable": reference["url"].startswith("https://"),
    }
    expected = {"fontSize": 16, "themeMode": "Light", "referenceAvailable": True}
    case_report(
        represents="Valid settings persist, theme changes, and enabled reference resolves",
        expected=expected,
        actual=actual,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Flask home page, state, analysis, and useful HTTP errors",
    category="web",
    expected={
        "home": 200,
        "state": 200,
        "analysis": 200,
        "unknown": 404,
        "bad_args": 400,
    },
)
def test_flask_routes_validate_operations_and_return_status_codes(case_report):
    client = create_app().test_client()
    actual = {
        "home": client.get("/").status_code,
        "state": client.get("/api/state").status_code,
        "analysis": client.post(
            "/api/analyzeSequence", json={"args": ["ACD", "Route", "protein"]}
        ).status_code,
        "unknown": client.post("/api/noSuchOperation", json={"args": []}).status_code,
        "bad_args": client.post(
            "/api/analyzeSequence", json={"args": "not a list"}
        ).status_code,
    }
    expected = {
        "home": 200,
        "state": 200,
        "analysis": 200,
        "unknown": 404,
        "bad_args": 400,
    }
    case_report(
        represents="HTTP status for state, analysis, unknown operation, and malformed arguments",
        expected=expected,
        actual=actual,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Flask report downloads require a successful prior analysis",
    category="web",
    expected={"download_before_analysis": 400, "export_after_analysis": 200},
)
def test_flask_report_routes_enforce_analysis_precondition(case_report):
    client = create_app().test_client()
    before = client.get("/api/export-analysis").status_code
    client.post("/api/analyzeSequence", json={"args": ["ACD", "Route", "protein"]})
    after = client.get("/api/export-analysis?name=Route").status_code
    actual = {"download_before_analysis": before, "export_after_analysis": after}
    expected = {"download_before_analysis": 400, "export_after_analysis": 200}
    case_report(
        represents="Export endpoint rejects an empty state and serves Markdown after analysis",
        expected=expected,
        actual=actual,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Testing runner config validates identifier, sequence, and service email",
    category="testing",
    expected="All malformed test inputs produce specific validation issues",
)
def test_runner_config_reports_invalid_sequence_id_and_email(case_report):
    runner = TestRunner()
    _config, _file, issues = runner._validated_config(
        "online",
        {
            "sequence": "AC*",
            "pdbId": "bad",
            "serviceEmail": "not-an-email",
        },
        {},
        "",
        "",
        False,
    )
    actual = {
        "sequence_issue": any("Sequence contains invalid symbols" in item for item in issues),
        "pdb_id_issue": any("PDB ID must contain exactly four" in item for item in issues),
        "email_issue": any("valid email address" in item for item in issues),
    }
    expected = {"sequence_issue": True, "pdb_id_issue": True, "email_issue": True}
    case_report(
        represents="Invalid sequence symbols, PDB ID format, and EMBL email",
        expected=expected,
        actual=actual,
        raw_input="Malformed input samples",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Testing runner stages supported sequence and structure uploads",
    category="testing",
    expected={"sequence_file": True, "structure_file": True, "chain": "A"},
)
def test_runner_config_stages_valid_sequence_and_structure_files(case_report):
    runner = TestRunner()
    seq_config, seq_file, seq_issues = runner._validated_config(
        "online", {}, {}, "input.fasta", ">demo\nACD", False
    )
    pdb_config, pdb_file, pdb_issues = runner._validated_config(
        "offline", {}, {}, "input.pdb", PDB_TEXT, False
    )
    actual = {
        "sequence_file": seq_file is not None and not seq_issues and not seq_config["structure_file"],
        "structure_file": pdb_file is not None and not pdb_issues and not pdb_config["sequence_file"],
        "chain": sorted(__import__("pdb_utils").parse_pdb_chains(pdb_file[1]))[0],
    }
    expected = {"sequence_file": True, "structure_file": True, "chain": "A"}
    case_report(
        represents="FASTA and PDB uploads validate and stage in the matching input slot",
        expected=expected,
        actual=actual,
        raw_input="FASTA with ACD and PDB SEQRES chain A",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Testing runner reads and atomically writes JSON state",
    category="testing",
    expected={"loaded": {"ready": True}, "written": True},
)
def test_runner_json_helpers_load_write_and_reject_invalid_json(tmp_path, case_report):
    path = tmp_path / "state.json"
    test_runner._write_json_atomic(path, {"ready": True})
    actual = {
        "loaded": test_runner._read_json(path, {}),
        "written": path.is_file(),
    }
    expected = {"loaded": {"ready": True}, "written": True}
    case_report(
        represents="Temporary JSON state is atomically written and read back",
        expected=expected,
        actual=actual,
    )
    assert actual == expected
    path.write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="Unable to read"):
        test_runner._read_json(path, {})


@pytest.mark.case(
    represents="Testing runner parses JUnit result metadata and outcomes",
    category="testing",
    expected={"result": "failed", "group": "online", "category": "charge"},
)
def test_runner_junit_parser_extracts_case_and_comparison_properties(tmp_path, monkeypatch, case_report):
    junit = tmp_path / "results.xml"
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    case = ET.SubElement(suite, "testcase", name="charge", classname="tests.test_online", time="0.5")
    properties = ET.SubElement(case, "properties")
    for name, value in (
        ("test_group", "online"),
        ("case_info", json.dumps({"represents": "Charge", "category": "charge"})),
        ("case_comparisons", json.dumps([{"represents": "Charge", "expected": 1, "actual": 2, "reference_url": "https://api.example"}])),
    ):
        ET.SubElement(properties, "property", name=name, value=value)
    ET.SubElement(case, "failure", message="different actual result")
    ET.ElementTree(root).write(junit, encoding="utf-8", xml_declaration=True)
    monkeypatch.setattr(test_runner, "JUNIT_PATH", junit)
    result = TestRunner()._parse_junit_results()[0]
    actual = {
        "result": result["result"],
        "group": result["group"],
        "category": result["case"]["category"],
    }
    expected = {"result": "failed", "group": "online", "category": "charge"}
    case_report(
        represents="JUnit outcome and online test metadata become dashboard fields",
        expected=expected,
        actual=actual,
    )
    assert actual == expected
    assert result["link"] == "https://api.example"
    assert result["comparisons"][0]["expected"] == 1


@pytest.mark.case(
    represents="Testing runner merges only the group that was rerun",
    category="testing",
    expected={"kept_offline": True, "replaced_online": True},
)
def test_runner_merge_results_preserves_other_test_group(case_report):
    previous = {
        "offline": {"id": "offline", "group": "offline", "result": "passed"},
        "online": {"id": "online", "group": "online", "result": "failed"},
    }
    update = [{"id": "online", "group": "online", "result": "passed"}]
    merged = TestRunner._merge_results(previous, update, "online")
    actual = {
        "kept_offline": merged["offline"]["result"] == "passed",
        "replaced_online": merged["online"]["result"] == "passed",
    }
    expected = {"kept_offline": True, "replaced_online": True}
    case_report(
        represents="Rerunning online tests does not discard offline results",
        expected=expected,
        actual=actual,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Testing runner rejects unsupported test modes before starting",
    category="testing",
    expected={"ok": False, "error": "Choose offline, online, or all tests."},
)
def test_runner_start_rejects_unknown_mode(case_report):
    result = TestRunner().start("invalid", "{}", "", "", False)
    expected = {"ok": False, "error": "Choose offline, online, or all tests."}
    case_report(
        represents="Only offline, online, and all test modes may be started",
        expected=expected,
        actual=result,
        raw_input="invalid mode",
    )
    assert result == expected


@pytest.mark.case(
    represents="Relevant Pepstats text fields are parsed into typed values",
    category="testing",
    expected={
        "molecular_weight": 38590.16,
        "length": 360,
        "average_residue_weight": 107.195,
        "theoretical_pI": 6.3901,
        "standard_residue_counts": 20,
    },
)
def test_pepstats_output_parser_extracts_scientific_summary(case_report):
    output = """PEPSTATS of LACI_ECOLI from 1 to 360
Molecular weight = 38590.16        Residues = 360
Average Residue Weight = 107.195   Charge = 1.5
Isoelectric Point = 6.3901
A280 Molar Extinction Coefficients = 22920 (reduced) 23045 (cystine bridges)
Residue       Number   Mole%   DayhoffStat
A = Ala       44       12.222  1.421
B = Asx       0        0.000   0.000
C = Cys       3        0.833   0.287
D = Asp       17       4.722   0.859
E = Glu       15       4.167   0.694
F = Phe       4        1.111   0.309
G = Gly       22       6.111   0.728
H = His       7        1.944   0.972
I = Ile       18       5.000   1.111
J = ---        0       0.000   0.000
K = Lys       11       3.056   0.463
L = Leu       41       11.389  1.539
M = Met       10       2.778   1.634
N = Asn       12       3.333   0.775
O = ---        0       0.000   0.000
P = Pro       14       3.889   0.748
Q = Gln       28       7.778   1.994
R = Arg       19       5.278   1.077
S = Ser       32       8.889   1.270
T = Thr       19       5.278   0.865
U = ---        0       0.000   0.000
V = Val       34       9.444   1.431
W = Trp       2        0.556   0.427
X = Xaa        0       0.000   0.000
Y = Tyr        8       2.222   0.654
Z = Glx        0       0.000   0.000
"""
    summary = _pepstats_summary(output)
    actual = {
        "molecular_weight": summary["molecular_weight"],
        "length": summary["length"],
        "average_residue_weight": summary["average_residue_weight"],
        "theoretical_pI": summary["theoretical_pI"],
        "standard_residue_counts": len(summary["composition"]),
    }
    expected = {
        "molecular_weight": 38590.16,
        "length": 360,
        "average_residue_weight": 107.195,
        "theoretical_pI": 6.3901,
        "standard_residue_counts": 20,
    }
    case_report(
        represents="Pepstats output is reduced to mass, length, pI, and standard counts",
        expected=expected,
        actual=actual,
    )
    assert actual == expected

