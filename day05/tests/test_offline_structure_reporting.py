import csv
import json

import pytest

import pdb_utils
import reporting
from pdb_utils import (
    _mmcif_loops,
    _mmcif_tokens,
    _one_letter_sequence,
    _parse_mmcif_atom_site,
    _parse_mmcif_chains,
    fetch_pdb_text,
    parse_pdb_chains,
)
from protein_analysis import calculate_protein_stats
from reporting import (
    build_analysis_markdown,
    build_report,
    export_report,
    read_analysis_markdown,
)


@pytest.mark.case(
    represents="Protein chains parsed from PDB SEQRES records",
    category="structure",
    expected={"A": "ACD"},
)
def test_parse_pdb_chains_reads_seqres_records(case_report):
    pdb_text = "SEQRES   1 A    3  ALA CYS ASP\n"
    expected = {"A": "ACD"}
    actual = parse_pdb_chains(pdb_text)
    case_report(
        represents="Chain ID to one-letter sequence mapping",
        expected=expected,
        actual=actual,
        raw_input="One PDB SEQRES record",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Tokenization and loop rows in mmCIF text",
    category="structure",
    expected=[["_atom_site.label_atom_id", "_atom_site.label_comp_id"], ["CA", "ALA"]],
)
def test_mmcif_tokenizer_and_loop_parser(case_report):
    cif_text = """data_demo
loop_
_atom_site.label_atom_id
_atom_site.label_comp_id
CA ALA
"""
    tokens = _mmcif_tokens(cif_text)
    loops = _mmcif_loops(cif_text)
    expected = [
        ["_atom_site.label_atom_id", "_atom_site.label_comp_id"],
        ["CA", "ALA"],
    ]
    actual = [loops[0][0], loops[0][1][0]]
    case_report(
        represents="mmCIF tokens grouped into named columns and a single row",
        expected=expected,
        actual=actual,
        raw_input="Two-column atom_site loop with one row",
    )
    assert "loop_" in tokens
    assert actual == expected


@pytest.mark.case(
    represents="One-letter sequence cleanup and unsupported-character removal",
    category="structure",
    expected="ACDBZJX",
)
def test_one_letter_sequence_keeps_supported_residue_codes(case_report):
    expected = "ACDBZJX"
    actual = _one_letter_sequence("A C D (modification) B Z J X ?")
    case_report(
        represents="Supported one-letter amino-acid sequence",
        expected=expected,
        actual=actual,
        raw_input="A C D (modification) B Z J X ?",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Canonical polymer-entity sequence and author chain IDs from mmCIF",
    category="structure",
    expected={"A": "ACD", "B": "ACD"},
)
def test_parse_mmcif_chains_uses_polymer_entity_sequence(case_report):
    cif_text = """data_demo
loop_
_entity_poly.pdbx_strand_id
_entity_poly.pdbx_seq_one_letter_code_can
A,B ACD
"""
    expected = {"A": "ACD", "B": "ACD"}
    actual = _parse_mmcif_chains(cif_text)
    case_report(
        represents="Chain-to-sequence mapping from the polymer-entity loop",
        expected=expected,
        actual=actual,
        raw_input="Two author chains share canonical sequence ACD",
    )
    assert actual == expected


@pytest.mark.case(
    represents="CA atom-site parsing with duplicate atoms removed",
    category="structure",
    expected={"A": "AC"},
)
def test_parse_mmcif_atom_site_deduplicates_residue_atoms(case_report):
    cif_text = """data_demo
loop_
_atom_site.auth_atom_id
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_seq_id
_atom_site.pdbx_pdb_model_num
CA ALA A 1 1
CA ALA A 1 1
CA CYS A 2 1
CA ASP A 3 2
"""
    expected = {"A": "AC"}
    actual = _parse_mmcif_atom_site(cif_text)
    case_report(
        represents="First-model CA residues with duplicate residue keys removed",
        expected=expected,
        actual=actual,
        raw_input="Three residues, duplicate ALA atom, and a second model",
    )
    assert actual == expected


@pytest.mark.case(
    represents="PDB ID validation, URL normalization, and response decoding",
    category="connectivity",
    expected={"id": "1ABC", "text": "PDB response"},
)
def test_fetch_pdb_text_validates_identifier_and_uses_rcsb_download_api(
    monkeypatch, case_report
):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def read():
            return b"PDB response"

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(pdb_utils, "urlopen", fake_urlopen)
    actual_text = fetch_pdb_text(" 1abc ")
    request, timeout = requests[0]
    actual = {"id": request.full_url.rsplit("/", 1)[-1][:4], "text": actual_text}
    expected = {"id": "1ABC", "text": "PDB response"}
    case_report(
        represents="Normalized PDB download request and decoded response",
        expected=expected,
        actual=actual,
        reference_name="RCSB file-download API request contract",
        reference_url="https://www.rcsb.org/docs/programmatic-access/file-download-services",
        raw_input="PDB ID 1abc",
    )
    assert timeout == 20
    assert actual == expected


@pytest.mark.case(
    represents="Readable Markdown export and schema-checked round trip",
    category="reporting",
    expected={"context": "protein", "sequence": "ACD", "name": "Example"},
)
def test_markdown_builder_and_reader_round_trip_analysis(tmp_path, case_report):
    analysis = {
        "context": "protein",
        "name": "Example",
        "sequence": "ACD",
        "overview": [["Length", "3"]],
    }
    text = build_analysis_markdown(analysis)
    path = tmp_path / "analysis.md"
    path.write_text(text, encoding="utf-8")
    actual = read_analysis_markdown(path)
    expected = analysis
    case_report(
        represents="Markdown content imported back into the original analysis mapping",
        expected=expected,
        actual=actual,
        raw_input="Small protein analysis Markdown report",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Report object assembled from protein statistics and extended metrics",
    category="reporting",
    expected={"protein_name": "Example", "sequence": "ACD", "length": 3},
)
def test_build_report_contains_statistics_and_methods(case_report):
    stats = calculate_protein_stats("ACD")
    report = build_report(stats, "Example")
    actual = {
        "protein_name": report["protein_name"],
        "sequence": report["sequence"],
        "length": report["statistics"]["length"],
    }
    expected = {"protein_name": "Example", "sequence": "ACD", "length": 3}
    case_report(
        represents="Named report with sequence and calculated length",
        expected=expected,
        actual=actual,
        raw_input="ACD",
    )
    assert actual == expected
    assert "extended_metrics" in report
    assert report["methods_and_limitations"]


@pytest.mark.case(
    represents="Metric row selection excludes raw sequence and composition fields",
    category="reporting",
    expected=["length", "molecular_weight", "Hydrophobicity profile", "Charge profile"],
)
def test_metric_rows_selects_reportable_statistics(case_report):
    report = build_report(calculate_protein_stats("ACD"))
    rows = reporting._metric_rows(report)
    labels = [label for label, _value in rows]
    actual = [
        label
        for label in labels
        if label in {"length", "molecular_weight", "Hydrophobicity profile", "Charge profile"}
    ]
    expected = ["length", "molecular_weight", "Hydrophobicity profile", "Charge profile"]
    case_report(
        represents="Visible report metric labels",
        expected=expected,
        actual=actual,
    )
    assert actual == expected
    assert "sequence" not in labels
    assert "composition" not in labels


@pytest.mark.case(
    represents="Supported report formats and explicit unsupported-format error",
    category="reporting",
    expected=[".json", ".csv", ".txt", ".html"],
)
@pytest.mark.parametrize("suffix", [".json", ".csv", ".txt", ".html"])
def test_export_report_writes_supported_formats(tmp_path, suffix, case_report):
    path = tmp_path / f"report{suffix}"
    export_report(path, calculate_protein_stats("ACD"), "Example")
    content = path.read_text(encoding="utf-8-sig")
    expected = suffix[1:]
    actual = {
        ".json": lambda: json.loads(content)["protein_name"],
        ".csv": lambda: next(csv.reader(content.splitlines()))[0],
        ".txt": lambda: content.splitlines()[0],
        ".html": lambda: "<html" in content.lower(),
    }[suffix]()
    case_report(
        represents=f"{suffix} report is created and readable",
        expected="Example" if suffix != ".html" else True,
        actual=actual,
        raw_input={"suffix": suffix},
    )
    assert path.is_file()
    if suffix == ".html":
        assert actual is True
    elif suffix == ".csv":
        assert actual == "Section"
    else:
        assert actual == "Example"


@pytest.mark.case(
    represents="Unsupported report file extension is rejected",
    category="reporting",
    expected="ValueError",
)
def test_export_report_rejects_unsupported_extension(tmp_path, case_report):
    with pytest.raises(ValueError, match="Choose a JSON"):
        export_report(tmp_path / "report.pdf", calculate_protein_stats("ACD"))
    case_report(
        represents="PDF is not a supported report output",
        expected="ValueError",
        actual="ValueError raised",
        raw_input="report.pdf",
    )
