import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pytest

from conftest import load_online_config
from pdb_utils import _one_letter_sequence, parse_pdb_chains
from protein_analysis import (
    AA_TO_THREE,
    calculate_extended_metrics,
    calculate_protein_stats,
    normalize_sequence,
)


PEPSTATS_URL = "https://www.ebi.ac.uk/jdispatcher/seqstats/emboss_pepstats"
PEPSTATS_API_URL = "https://www.ebi.ac.uk/Tools/services/rest/emboss_pepstats"
RCSB_API_URL = "https://data.rcsb.org/rest/v1/core"
RCSB_DOC_URL = "https://www.rcsb.org/docs/programmatic-access/web-apis-overview"
SCANPROSITE_API_URL = (
    "https://prosite.expasy.org/cgi-bin/prosite/scanprosite/PSScan.cgi"
)
SCANPROSITE_DOC_URL = "https://prosite.expasy.org/scanprosite/scanprosite_doc.html"
PROTPARAM_URL = "https://web.expasy.org/protparam/"
PEPTIDE_CUTTER_URL = "https://web.expasy.org/peptide_cutter/"
PEPTIDE_CUTTER_FORM_URL = (
    "https://web.expasy.org/cgi-bin/peptide_cutter/peptidecutter.pl"
)


class _PageTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.form_action = None
        self.has_sequence_input = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form" and self.form_action is None:
            self.form_action = attributes.get("action")
        if tag == "textarea" and attributes.get("name") == "sequence":
            self.has_sequence_input = True

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())


def _protparam_summary(page):
    parser = _PageTextParser()
    parser.feed(page)
    text = re.sub(r"\s+", " ", " ".join(parser.parts))

    def required(pattern, label, flags=0):
        match = re.search(pattern, text, flags)
        if not match:
            raise ValueError(f"ProtParam output is missing {label}.")
        return match

    length = int(required(r"Number of amino acids:\s*(\d+)", "sequence length").group(1))
    molecular_weight = float(
        required(r"Molecular weight:\s*([\d.]+)", "molecular weight").group(1)
    )
    theoretical_pI = float(
        required(r"Theoretical pI:\s*([\d.]+)", "theoretical pI").group(1)
    )

    composition_section = required(
        r"Amino acid composition:\s*(.*?)\s*Total number of negatively charged residues\b",
        "amino-acid composition",
        re.IGNORECASE,
    ).group(1)
    composition = {
        letter: int(count)
        for letter, count in re.findall(
            r"[A-Z][a-z]{2}\s+\(([A-Z])\)\s+(\d+)\s+[\d.]+%",
            composition_section,
        )
        if letter in AA_TO_THREE
    }
    if set(composition) != set(AA_TO_THREE):
        raise ValueError("ProtParam output is missing standard amino-acid counts.")

    atom_counts = {}
    for element_name, symbol in (
        ("Carbon", "C"),
        ("Hydrogen", "H"),
        ("Nitrogen", "N"),
        ("Oxygen", "O"),
        ("Sulfur", "S"),
    ):
        atom_counts[symbol] = int(
            required(
                rf"{element_name}\s+{symbol}\s+(\d+)",
                f"{element_name.lower()} atom count",
            ).group(1)
        )

    extinction_values = {
        assumption.lower(): float(value)
        for value, assumption in re.findall(
            r"Ext\. coefficient\s+(\d+)\s+Abs.*?assuming "
            r"(all pairs of Cys residues form cystines|all Cys residues are reduced)",
            text,
            re.IGNORECASE,
        )
    }
    if set(extinction_values) != {
        "all pairs of cys residues form cystines",
        "all cys residues are reduced",
    }:
        raise ValueError("ProtParam output is missing an extinction coefficient.")
    half_lives = required(
        r"estimated half-life is:\s*(.+?)\s*\(mammalian reticulocytes, in vitro\)\.\s*"
        r"(.+?)\s*\(yeast, in vivo\)\.\s*(.+?)\s*\(Escherichia coli, in vivo\)\.",
        "half-life estimates",
        re.IGNORECASE,
    )
    instability = required(
        r"instability index \(II\) is computed to be\s*([\d.]+)\s*"
        r"This classifies the protein as\s*(stable|unstable)",
        "instability index",
        re.IGNORECASE,
    )
    aliphatic_index = float(
        required(r"Aliphatic index:\s*([\d.]+)", "aliphatic index").group(1)
    )
    gravy = float(
        required(
            r"Grand average of hydropathicity \(GRAVY\):\s*([-+]?[\d.]+)",
            "GRAVY score",
            re.IGNORECASE,
        ).group(1)
    )
    return {
        "length": length,
        "molecular_weight": molecular_weight,
        "theoretical_pI": theoretical_pI,
        "composition": composition,
        "atomic_composition": atom_counts,
        "extinction_coefficient_oxidized": extinction_values[
            "all pairs of cys residues form cystines"
        ],
        "extinction_coefficient_reduced": extinction_values[
            "all cys residues are reduced"
        ],
        "estimated_half_life": tuple(
            value.strip() for value in half_lives.groups()
        ),
        "instability_index": float(instability.group(1)),
        "stability_classification": instability.group(2).title(),
        "aliphatic_index": aliphatic_index,
        "gravy": gravy,
    }


def _run_protparam(sequence):
    page_request = urllib.request.Request(
        PROTPARAM_URL,
        headers={"User-Agent": "ProteinAnalysisStudioTests/1.0"},
    )
    with urllib.request.urlopen(page_request, timeout=30) as response:
        form_page = response.read().decode("utf-8", errors="replace")
    form_parser = _PageTextParser()
    form_parser.feed(form_page)
    if not form_parser.form_action or not form_parser.has_sequence_input:
        raise ValueError("The linked ProtParam page no longer exposes its sequence form.")

    form_url = urljoin(PROTPARAM_URL, form_parser.form_action)
    request = urllib.request.Request(
        form_url,
        data=urllib.parse.urlencode(
            {"sequence": sequence, "mandatory": ""}
        ).encode("ascii"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ProteinAnalysisStudioTests/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result_page = response.read().decode("utf-8", errors="replace")
    return _protparam_summary(result_page)


def _run_peptide_cutter(sequence):
    fields = [
        ("protein", sequence),
        ("enzyme_number", "less_enzymes"),
        ("enzyme", "ArgC"),
        ("enzyme", "AspN"),
        ("enzyme", "Ch_hi"),
        ("enzyme", "CNBr"),
        ("enzyme", "Glu"),
        ("enzyme", "LysC"),
        ("enzyme", "Tryps"),
        ("alphtable", "alphtable"),
        ("cleave_number", "all"),
    ]
    request = urllib.request.Request(
        PEPTIDE_CUTTER_FORM_URL,
        data=urllib.parse.urlencode(fields).encode("ascii"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ProteinAnalysisStudioTests/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", errors="replace")
    parser = _PageTextParser()
    parser.feed(page)
    if "Software error:" in " ".join(parser.parts):
        raise RuntimeError("PeptideCutter reported a server-side software error.")

    reference_names = {
        "Arg-C proteinase": "Arg-C",
        "Asp-N endopeptidase": "Asp-N",
        "CNBr": "CNBr",
        "Chymotrypsin-high specificity (C-term to [FYW], not before P)": "Chymotrypsin",
        "Glutamyl endopeptidase": "Glu-C",
        "LysC": "Lys-C",
        "Trypsin": "Trypsin",
    }
    try:
        index = parser.parts.index("Cleavage in your sequence:") + 1
    except ValueError as exc:
        raise ValueError("PeptideCutter output has no cleavage results section.") from exc

    results = {}
    while index + 2 < len(parser.parts):
        name = parser.parts[index]
        app_name = reference_names.get(name)
        if app_name is None:
            index += 1
            continue
        try:
            count = int(parser.parts[index + 1])
            positions = [
                int(value)
                for value in parser.parts[index + 2].split()
            ]
        except ValueError as exc:
            raise ValueError(
                f"PeptideCutter returned malformed positions for {name}."
            ) from exc
        if len(positions) != count:
            raise ValueError(
                f"PeptideCutter returned an inconsistent cleavage count for {name}."
            )
        results[app_name] = positions
        index += 3

    if set(results) != set(reference_names.values()):
        raise ValueError("PeptideCutter output is missing selected enzyme results.")
    return results


@pytest.mark.case(
    represents="Relevant values are parsed from the linked ProtParam calculator output",
    category="testing",
    expected="Length, mass, composition, atom counts, and analysis values are extracted",
)
def test_protparam_html_parser_extracts_relevant_fields(case_report):
    composition = " ".join(
        f"{AA_TO_THREE[letter].title()} ({letter}) 1 5.0%"
        for letter in AA_TO_THREE
    )
    page = f"""
        <pre>
        <strong>Number of amino acids:</strong> 20
        <strong>Theoretical pI:</strong> 8.57
        <strong>Molecular weight:</strong> 2400.00
        <strong>Amino acid composition:</strong> {composition}
        <strong>Total number of negatively charged residues (Asp + Glu):</strong> 2
        <strong>Atomic composition:</strong> Carbon C 100 Hydrogen H 200
        Nitrogen N 20 Oxygen O 30 Sulfur S 2
        <strong>Extinction coefficients:</strong>
        Ext. coefficient 2000 Abs 1.0, assuming all pairs of Cys residues form cystines
        Ext. coefficient 1900 Abs 0.9, assuming all Cys residues are reduced
        <strong>Estimated half-life:</strong>
        The estimated half-life is: 5.5 hours (mammalian reticulocytes, in vitro).
        3 min (yeast, in vivo). 2 min (Escherichia coli, in vivo).
        <strong>Instability index:</strong>
        The instability index (II) is computed to be 59.72
        This classifies the protein as unstable.
        <strong>Aliphatic index:</strong> 82.63
        <strong>Grand average of hydropathicity (GRAVY):</strong>-0.300
        </pre>
    """
    result = _protparam_summary(page)
    expected_composition = {letter: 1 for letter in AA_TO_THREE}
    expected = {
        "length": 20,
        "molecular_weight": 2400.0,
        "theoretical_pI": 8.57,
        "composition": expected_composition,
        "atomic_composition": {"C": 100, "H": 200, "N": 20, "O": 30, "S": 2},
        "extinction_coefficient_oxidized": 2000.0,
        "extinction_coefficient_reduced": 1900.0,
        "estimated_half_life": ("5.5 hours", "3 min", "2 min"),
        "instability_index": 59.72,
        "aliphatic_index": 82.63,
        "gravy": -0.3,
    }
    actual = {key: result[key] for key in expected}
    case_report(
        represents="Parsed, relevant ProtParam result fields",
        expected=expected,
        actual=actual,
        reference_name="ProtParam parser fixture",
    )
    assert actual == expected


def _read_json_url(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _pepstats_summary(text):
    molecular = re.search(
        r"Molecular weight\s*=\s*([\d.]+)\s+Residues\s*=\s*(\d+)", text
    )
    average_weight = re.search(
        r"Average Residue Weight\s*=\s*([\d.]+)", text
    )
    charge = re.search(r"\bCharge\s*=\s*([-+]?[\d.]+)", text)
    isoelectric = re.search(r"Isoelectric Point\s*=\s*([\d.]+)", text)
    extinction = re.search(
        r"A280 Molar Extinction Coefficients\s*=\s*([\d.]+)\s*\(reduced\)"
        r"\s*([\d.]+)\s*\(cystine bridges\)",
        text,
    )
    composition = {
        letter: int(count)
        for letter, count in re.findall(
            r"^\s*([ACDEFGHIKLMNPQRSTVWY])\s*=.*?\s+(\d+)\s+[\d.]+\s+[\d.]+\s*$",
            text,
            flags=re.MULTILINE,
        )
    }
    if not all((molecular, average_weight, charge, isoelectric, extinction)) or len(composition) != 20:
        raise ValueError("Pepstats output is missing expected summary fields.")
    return {
        "molecular_weight": float(molecular.group(1)),
        "length": int(molecular.group(2)),
        "average_residue_weight": float(average_weight.group(1)),
        "charge_at_ph_7": float(charge.group(1)),
        "theoretical_pI": float(isoelectric.group(1)),
        "extinction_coefficient_reduced": float(extinction.group(1)),
        "extinction_coefficient_cystine_bridges": float(extinction.group(2)),
        "composition": composition,
    }


def _run_pepstats(sequence, email):
    parameters = urllib.parse.urlencode(
        {
            "email": email,
            "sequence": sequence,
            "termini": "true",
            "mono": "false",
        }
    ).encode("ascii")
    request = urllib.request.Request(
        f"{PEPSTATS_API_URL}/run/",
        data=parameters,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        job_id = response.read().decode("utf-8").strip()
    if not job_id:
        raise ValueError("Pepstats did not return a job identifier.")

    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        with urllib.request.urlopen(
            f"{PEPSTATS_API_URL}/status/{urllib.parse.quote(job_id)}", timeout=30
        ) as response:
            status = response.read().decode("utf-8").strip().upper()
        if status == "FINISHED":
            break
        if status in {"ERROR", "FAILURE", "NOT_FOUND"}:
            raise RuntimeError(f"Pepstats job {job_id} ended with status {status}.")
        if status != "RUNNING":
            raise RuntimeError(f"Pepstats returned unexpected job status {status!r}.")
        time.sleep(2)
    else:
        raise TimeoutError("Pepstats job did not finish within five minutes.")

    result_types = _read_json_url(f"{PEPSTATS_API_URL}/resulttypes/{job_id}")
    result_type = next(
        (
            item["identifier"]
            for item in result_types
            if item.get("identifier") in {"out", "pepstats"}
        ),
        None,
    )
    if result_type is None:
        raise ValueError("Pepstats did not provide its documented text output.")
    with urllib.request.urlopen(
        f"{PEPSTATS_API_URL}/result/{job_id}/{result_type}", timeout=45
    ) as response:
        output = response.read().decode("utf-8", errors="replace")
    return _pepstats_summary(output)


def _config_sequence(config):
    sequence = config.get("sequence", "")
    if sequence:
        raw_sequence = sequence
    else:
        path = config.get("sequence_file", "")
        if not path:
            pytest.skip("No direct sequence or saved sequence file is configured.")
        raw_sequence = Path(path).read_text(encoding="utf-8-sig")
    cleaned, invalid = normalize_sequence(raw_sequence)
    if not cleaned or invalid:
        pytest.fail("Configured online sequence is empty or contains invalid symbols.")
    return cleaned


@pytest.fixture(scope="session")
def online_config():
    return load_online_config()


@pytest.fixture(scope="session")
def pepstats_result(online_config):
    email = online_config.get("service_email", "").strip()
    if not email:
        pytest.skip(
            "EMBL-EBI Pepstats requires a valid contact email; configure "
            "service_email in tests/online_validation.json."
        )
    return _run_pepstats(_config_sequence(online_config), email)


@pytest.fixture(scope="session")
def protparam_result(online_config):
    return _run_protparam(_config_sequence(online_config))


@pytest.fixture(scope="session")
def pepstats_comparison(online_config, pepstats_result):
    app_result = calculate_protein_stats(_config_sequence(online_config))
    return pepstats_result, app_result


@pytest.fixture(scope="session")
def protparam_comparison(online_config, protparam_result):
    app_result = calculate_protein_stats(_config_sequence(online_config))
    return protparam_result, app_result


@pytest.mark.online
@pytest.mark.case(
    represents="Protein molecular weight compared with the linked ExPASy ProtParam calculator",
    category="properties",
    expected="Molecular weight matches ProtParam's displayed value",
)
def test_online_protparam_molecular_weight(protparam_comparison, case_report):
    reference, app = protparam_comparison
    expected = round(reference["molecular_weight"], 2)
    actual = app.molecular_weight
    case_report(
        represents="Molecular weight in daltons",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert reference["length"] == app.length
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Average residue mass derived from ExPASy ProtParam molecular weight",
    category="properties",
    expected="ProtParam molecular weight less terminal water, divided by residue count",
)
def test_online_protparam_average_residue_weight(protparam_comparison, case_report):
    reference, app = protparam_comparison
    expected = round(
        (reference["molecular_weight"] - 18.01528) / reference["length"], 2
    )
    actual = app.average_residue_mass
    case_report(
        represents="Average residue weight in daltons",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Standard amino-acid counts compared with ExPASy ProtParam",
    category="composition",
    expected="Exact counts for all 20 standard amino acids",
)
def test_online_protparam_amino_acid_composition(protparam_comparison, case_report):
    reference, app = protparam_comparison
    expected = reference["composition"]
    actual = {residue: app.composition[residue] for residue in expected}
    case_report(
        represents="Residue counts (ambiguous residue classes excluded)",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Basic and acidic residue counts and percentages from ProtParam composition",
    category="composition",
    expected="Counts and percentages derived from the external 20-residue composition",
)
def test_online_residue_class_counts_match_protparam_composition(
    online_config, protparam_result, case_report
):
    app = calculate_extended_metrics(_config_sequence(online_config))
    counts = protparam_result["composition"]
    length = protparam_result["length"]
    expected = {
        "positive_residues": counts["K"] + counts["R"] + counts["H"],
        "negative_residues": counts["D"] + counts["E"],
        "basic_residue_percent": 100
        * (counts["K"] + counts["R"] + counts["H"])
        / length,
        "acidic_residue_percent": 100 * (counts["D"] + counts["E"]) / length,
    }
    actual = {
        "positive_residues": app["positive_residues"],
        "negative_residues": app["negative_residues"],
        "basic_residue_percent": app["basic_residue_percent"],
        "acidic_residue_percent": app["acidic_residue_percent"],
    }
    case_report(
        represents="Charged residue counts and percentages derived from Pepstats counts",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam composition",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Aliphatic index and sequence entropy compared with ProtParam",
    category="properties",
    expected="Aliphatic index matches ProtParam; entropy is derived from its external counts",
)
def test_online_aliphatic_index_and_entropy_use_protparam_composition(
    online_config, protparam_result, case_report
):
    from math import log2

    app = calculate_extended_metrics(_config_sequence(online_config))
    counts = protparam_result["composition"]
    length = protparam_result["length"]
    expected_aliphatic = round(protparam_result["aliphatic_index"], 2)
    known_count = sum(counts.values())
    expected_entropy = -sum(
        (count / known_count) * log2(count / known_count)
        for count in counts.values()
        if count and known_count
    )
    expected = {
        "aliphatic_index": expected_aliphatic,
        "shannon_entropy_bits": round(expected_entropy, 4),
    }
    actual = {
        "aliphatic_index": round(app["aliphatic_index"], 2),
        "shannon_entropy_bits": round(app["shannon_entropy_bits"], 4),
    }
    case_report(
        represents="Independent formulas applied to externally reported residue counts",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator and composition",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Aromaticity, unique-residue count, and cysteine pairs from ProtParam composition",
    category="properties",
    expected="Derived protein statistics match values calculated from external amino-acid counts",
)
def test_online_derived_statistics_match_protparam_composition(
    online_config, protparam_result, case_report
):
    app_stats = calculate_protein_stats(_config_sequence(online_config))
    counts = protparam_result["composition"]
    length = protparam_result["length"]
    expected = {
        "aromaticity": round(
            (counts["F"] + counts["W"] + counts["Y"]) / length, 4
        ),
        "unique_residues": sum(count > 0 for count in counts.values()),
        "cysteine_count": counts["C"],
        "potential_disulfide_pairs": counts["C"] // 2,
    }
    actual = {
        "aromaticity": app_stats.aromaticity,
        "unique_residues": app_stats.unique_residues,
        "cysteine_count": app_stats.composition["C"],
        "potential_disulfide_pairs": app_stats.composition["C"] // 2,
    }
    case_report(
        represents="Application statistics derived from the externally reported residue counts",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam composition",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Charge at pH 7 compared with EMBOSS Pepstats",
    category="charge",
    expected="Matching charge rounded to Pepstats' reported 0.1 precision",
)
def test_online_pepstats_charge_at_neutral_ph(pepstats_comparison, case_report):
    reference, app = pepstats_comparison
    expected = round(reference["charge_at_ph_7"], 1)
    actual = round(app.charge_at_ph_7, 1)
    case_report(
        represents="Net charge at pH 7",
        expected=expected,
        actual=actual,
        reference_name="EMBOSS Pepstats API",
        reference_url=PEPSTATS_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Theoretical isoelectric point compared with ExPASy ProtParam",
    category="charge",
    expected="Theoretical pI matches ProtParam's displayed value",
)
def test_online_protparam_theoretical_isoelectric_point(
    protparam_comparison, case_report
):
    reference, app = protparam_comparison
    expected = round(reference["theoretical_pI"], 2)
    actual = round(app.theoretical_pI, 2)
    case_report(
        represents="Theoretical isoelectric point in pH units",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Oxidized extinction coefficient compared with ExPASy ProtParam",
    category="properties",
    expected="Cystine-bridge A280 coefficient matches in M^-1 cm^-1",
)
def test_online_protparam_extinction_coefficient(protparam_comparison, case_report):
    reference, app = protparam_comparison
    expected = reference["extinction_coefficient_oxidized"]
    actual = app.extinction_coefficient
    case_report(
        represents="A280 extinction coefficient for the application’s oxidized model",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


def _rcsb_chain_sequence(pdb_id, chain_id):
    entry = _read_json_url(f"{RCSB_API_URL}/entry/{pdb_id}")
    entity_ids = entry["rcsb_entry_container_identifiers"]["polymer_entity_ids"]
    entity_matches = []
    for entity_id in entity_ids:
        entity = _read_json_url(f"{RCSB_API_URL}/polymer_entity/{pdb_id}/{entity_id}")
        identifiers = entity["rcsb_polymer_entity_container_identifiers"]
        author_chains = identifiers.get("auth_asym_ids", [])
        asym_chains = identifiers.get("asym_ids", [])
        if chain_id in author_chains:
            asym_id = asym_chains[author_chains.index(chain_id)]
            entity_matches.append((True, entity_id, asym_id, entity))
        elif chain_id in asym_chains:
            entity_matches.append((False, entity_id, chain_id, entity))
    for _is_author_match, entity_id, asym_id, entity in sorted(
        entity_matches, key=lambda match: not match[0]
    ):
        instance = _read_json_url(
            f"{RCSB_API_URL}/polymer_entity_instance/{pdb_id}/{asym_id}"
        )
        mapped_entity_id = instance[
            "rcsb_polymer_entity_instance_container_identifiers"
        ]["entity_id"]
        if str(mapped_entity_id) != str(entity_id):
            raise ValueError("RCSB chain mapping returned inconsistent entity IDs.")
        return _one_letter_sequence(
            entity["entity_poly"]["pdbx_seq_one_letter_code_can"]
        )
    raise ValueError(f"RCSB entry {pdb_id} has no polymer chain {chain_id!r}.")


@pytest.mark.online
@pytest.mark.case(
    represents="Selected uploaded PDB chain sequence compared with RCSB Data API",
    category="structure",
    expected="Exact match to the RCSB canonical polymer-entity sequence",
)
def test_online_uploaded_structure_chain_matches_rcsb(online_config, case_report):
    pdb_id = online_config.get("pdb_id", "").strip().upper()
    chain_id = online_config.get("chain_id", "").strip()
    structure_path = Path(online_config.get("structure_file", ""))
    if not pdb_id:
        pytest.skip("No PDB ID is configured for the structure comparison.")
    if not chain_id:
        pytest.skip("No chain ID is configured for the structure comparison.")
    if not structure_path.is_file():
        pytest.skip("No uploaded PDB/mmCIF structure file is configured.")

    chains = parse_pdb_chains(
        structure_path.read_text(encoding="utf-8", errors="replace")
    )
    if chain_id not in chains:
        pytest.fail(f"Configured chain {chain_id!r} is missing from the structure file.")
    expected = _rcsb_chain_sequence(pdb_id, chain_id)
    actual = chains[chain_id]
    case_report(
        represents=f"Full one-letter sequence for PDB {pdb_id}, chain {chain_id}",
        expected=expected,
        actual=actual,
        reference_name="RCSB PDB Data API",
        reference_url=RCSB_DOC_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Application PDB download and chain parsing compared with RCSB Data API",
    category="structure",
    expected="Exact match for the fetched PDB chain's one-letter sequence",
)
def test_online_fetched_pdb_chain_matches_rcsb(online_config, case_report):
    from pdb_utils import fetch_pdb_text

    pdb_id = online_config.get("pdb_id", "").strip().upper()
    chain_id = online_config.get("chain_id", "").strip()
    if not pdb_id:
        pytest.skip("No PDB ID is configured for the download test.")
    if not chain_id:
        pytest.skip("No chain ID is configured for the download test.")
    downloaded = fetch_pdb_text(pdb_id)
    chains = parse_pdb_chains(downloaded)
    if chain_id not in chains:
        pytest.fail(f"Downloaded PDB {pdb_id} has no chain {chain_id!r}.")
    expected = _rcsb_chain_sequence(pdb_id, chain_id)
    actual = chains[chain_id]
    case_report(
        represents=f"Fetched PDB {pdb_id}, chain {chain_id} sequence",
        expected=expected,
        actual=actual,
        reference_name="RCSB PDB Data API and file-download service",
        reference_url=RCSB_DOC_URL,
    )
    assert actual == expected


def _scanprosite_sequon_positions(sequence):
    parameters = urllib.parse.urlencode(
        {"seq": sequence, "sig": "N-{P}-[ST]", "output": "xml"}
    )
    request = urllib.request.Request(
        f"{SCANPROSITE_API_URL}?{parameters}",
        headers={"User-Agent": "ProteinAnalysisStudioTests/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        root = ET.fromstring(response.read())
    matches = [
        match
        for match in root.iter()
        if match.tag.rsplit("}", 1)[-1] == "match"
    ]
    return sorted(
        int(child.text)
        for match in matches
        for child in match
        if child.tag.rsplit("}", 1)[-1] == "start" and child.text
    )


@pytest.mark.online
@pytest.mark.case(
    represents="N-X-S/T sequon start positions compared with ScanProsite",
    category="features",
    expected="Exact 1-based positions for N-X-S/T motifs where X is not proline",
)
def test_online_glycosylation_sequons_match_scanprosite(online_config, case_report):
    sequence = _config_sequence(online_config)
    app_result = calculate_extended_metrics(sequence)
    expected = _scanprosite_sequon_positions(sequence)
    actual = app_result["n_glycosylation_sequon_positions"]
    case_report(
        represents="1-based N-linked sequon start positions; occupancy is not predicted",
        expected=expected,
        actual=actual,
        reference_name="ScanProsite custom-pattern REST API",
        reference_url=SCANPROSITE_DOC_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="N-terminal half-life estimates compared with the linked ProtParam calculator",
    category="properties",
    expected="Exact mammalian, yeast, and E. coli N-end-rule values for the first residue",
)
def test_online_half_life_matches_protparam_calculator(
    online_config, protparam_result, case_report
):
    sequence = _config_sequence(online_config)
    metrics = calculate_extended_metrics(sequence)
    residue = metrics["n_terminal_residue"]
    expected = protparam_result["estimated_half_life"]
    actual = tuple(metrics["estimated_half_life"])
    case_report(
        represents=f"N-end-rule estimate for N-terminal residue {residue}",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Instability index compared with the linked ProtParam calculator",
    category="properties",
    expected="Instability index rounded to ProtParam's displayed precision",
)
def test_online_instability_index_matches_protparam(
    online_config, protparam_result, case_report
):
    metrics = calculate_extended_metrics(_config_sequence(online_config))
    expected = round(protparam_result["instability_index"], 2)
    actual = round(metrics["instability_index"], 2)
    case_report(
        represents="Instability index",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="GRAVY hydropathy compared with the linked ProtParam calculator",
    category="hydrophobicity",
    expected="Mean Kyte-Doolittle hydropathy rounded to ProtParam's 0.001 precision",
)
def test_online_gravy_matches_protparam(online_config, protparam_result, case_report):
    app = calculate_protein_stats(_config_sequence(online_config))
    expected = round(protparam_result["gravy"], 3)
    actual = app.gravy
    case_report(
        represents="Grand average of hydropathicity (GRAVY)",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam calculator",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Sliding-window hydropathy profile compared with an EMBOSS reference",
    category="hydrophobicity",
    expected="Skipped until the REST output is verified against the app's seven-residue means",
)
def test_online_hydrophobicity_profile_requires_machine_readable_result():
    pytest.skip(
        "The linked DOI documents the Kyte-Doolittle scale, and EMBL-EBI offers "
        "Pepwindow REST, but a valid contact email is missing and its returned "
        "profile format has not been verified against the application's 7-residue means. "
        "The separate GRAVY comparison uses the linked ProtParam calculator."
    )


@pytest.mark.online
@pytest.mark.case(
    represents="Neutral-polypeptide atom counts compared with the linked ProtParam calculator",
    category="properties",
    expected="Exact carbon, hydrogen, nitrogen, oxygen, and sulfur counts",
)
def test_online_atomic_composition_matches_protparam(
    online_config, protparam_result, case_report
):
    metrics = calculate_extended_metrics(_config_sequence(online_config))
    expected = protparam_result["atomic_composition"]
    actual = metrics["atomic_composition"]
    case_report(
        represents="Atomic composition of the neutral polypeptide, including terminal water",
        expected=expected,
        actual=actual,
        reference_name="ExPASy ProtParam web form (no documented REST API)",
        reference_url=PROTPARAM_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Protease cleavage positions compared with linked ExPASy PeptideCutter",
    category="cleavage",
    expected="Exact 1-based cleavage-boundary positions for the seven shared enzymes",
)
def test_online_protease_cleavage_matches_peptide_cutter(
    online_config, case_report
):
    sequence = _config_sequence(online_config)
    metrics = calculate_extended_metrics(sequence)
    expected = _run_peptide_cutter(sequence)
    enzyme_names = ("Arg-C", "Asp-N", "CNBr", "Chymotrypsin", "Glu-C", "Lys-C", "Trypsin")
    actual = {name: metrics["cleavage_sites"][name] for name in enzyme_names}
    case_report(
        represents="1-based cleavage boundaries for shared enzyme rules",
        expected=expected,
        actual=actual,
        reference_name="ExPASy PeptideCutter web form (no documented REST API)",
        reference_url=PEPTIDE_CUTTER_URL,
    )
    assert actual == expected


@pytest.mark.online
@pytest.mark.case(
    represents="Antibody regions compared with a reference supporting protein-chain segmentation",
    category="antibody",
    expected="Skipped: linked ProtParam reference does not analyze Fc/Fab regions",
)
def test_online_antibody_regions_require_matching_protein_api():
    pytest.skip(
        "The linked ProtParam calculator reports sequence-wide properties, not antibody "
        "regions. IMGT/V-QUEST accepts nucleotide input; no documented protein-sequence "
        "API validates the application's Fc/Fab segmentation."
    )


@pytest.mark.online
@pytest.mark.case(
    represents="Signal-peptide cleavage compared with a tool using equivalent semantics",
    category="features",
    expected="Skipped: linked PeptideCutter does not predict signal-peptide processing",
)
def test_online_signal_peptide_heuristic_requires_comparable_predictor():
    pytest.skip(
        "The linked PeptideCutter calculates protease cleavage, not signal-peptide "
        "processing. Phobius has an API, but its signal-peptide/topology predictions "
        "are not equivalent to this application's -3/-1 cleavage heuristic."
    )
