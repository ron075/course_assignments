from math import isclose

import pytest

from protein_analysis import (
    ProteinStats,
    _regions_above_threshold,
    _residue_mass,
    approximate_theoretical_pI,
    build_summary_table,
    calculate_extended_metrics,
    calculate_protein_stats,
    cleavage_sites,
    count_amino_acids,
    hydrophobicity_profile,
    net_charge_at_ph,
    normalize_sequence,
    residue_charge_at_ph,
)


@pytest.mark.case(
    represents="FASTA parsing, case folding, whitespace cleanup, and invalid symbols",
    category="sequence",
    expected={"sequence": "ACDE", "invalid_symbols": ["*", "?"]},
)
def test_normalize_sequence_cleans_fasta_and_reports_invalid_symbols(case_report):
    cleaned, invalid = normalize_sequence(">sample\nac dE\n*?")
    actual = {"sequence": cleaned, "invalid_symbols": invalid}
    expected = {"sequence": "ACDE", "invalid_symbols": ["*", "?"]}
    case_report(
        represents="Normalized sequence and distinct invalid symbols",
        expected=expected,
        actual=actual,
        raw_input="FASTA header, mixed case, whitespace, and invalid symbols",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Average residue-mass values for standard, ambiguous, and invalid symbols",
    category="properties",
    expected={
        "A": 71.0788,
        "H": 137.1411,
        "B": 114.5962,
        "X": 110.0,
        "?": 0.0,
    },
)
def test_residue_mass_uses_standard_ambiguous_and_unknown_values(case_report):
    letters = ("A", "H", "B", "X", "?")
    expected = {
        "A": 71.0788,
        "H": 137.1411,
        "B": 114.5962,
        "X": 110.0,
        "?": 0.0,
    }
    actual = {letter: _residue_mass(letter) for letter in letters}
    case_report(
        represents="Residue mass in daltons (B is the D/N mean; X uses its defined approximation)",
        expected=expected,
        actual=actual,
        raw_input=letters,
    )
    assert actual == pytest.approx(expected)


@pytest.mark.case(
    represents="Standard and supported ambiguous amino-acid counts",
    category="composition",
    expected={"A": 2, "B": 1, "J": 1, "X": 1},
)
def test_count_amino_acids_counts_supported_residues(case_report):
    counts = count_amino_acids("AABJX?")
    actual = {residue: counts.get(residue, 0) for residue in ("A", "B", "J", "X")}
    expected = {"A": 2, "B": 1, "J": 1, "X": 1}
    case_report(
        represents="Residue counts; invalid symbols are not included",
        expected=expected,
        actual=actual,
        raw_input="AABJX?",
    )
    assert actual == expected
    assert sum(counts.values()) == 5


@pytest.mark.case(
    represents="Kyte-Doolittle sliding-window means for ACD",
    category="hydrophobicity",
    expected=[2.15, -0.5],
)
def test_hydrophobicity_profile_calculates_fixed_window_means(case_report):
    expected = [2.15, -0.5]
    actual = hydrophobicity_profile("ACD", window_size=2)
    case_report(
        represents="Mean Kyte-Doolittle score for each consecutive two-residue window",
        expected=expected,
        actual=actual,
        raw_input={"sequence": "ACD", "window_size": 2},
    )
    assert actual == pytest.approx(expected)
    assert hydrophobicity_profile("ACD", window_size=4) == []


@pytest.mark.case(
    represents="Protease cleavage positions and proline exceptions",
    category="cleavage",
    expected={
        "Trypsin": [8],
        "Chymotrypsin": [4, 5],
        "Lys-C": [2],
        "Glu-C": [6],
        "Arg-C": [8],
        "Asp-N": [6],
        "CNBr": [],
    },
)
def test_cleavage_sites_apply_enzyme_rules(case_report):
    sequence = "AKPFWEDR"
    expected = {
        "Trypsin": [8],
        "Chymotrypsin": [4, 5],
        "Lys-C": [2],
        "Glu-C": [6],
        "Arg-C": [8],
        "Asp-N": [6],
        "CNBr": [],
    }
    actual = cleavage_sites(sequence)
    case_report(
        represents="1-based cleavage positions after the rule-specific residue",
        expected=expected,
        actual=actual,
        raw_input=sequence,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Inclusive sequence spans from consecutive qualifying windows",
    category="features",
    expected=[[2, 5], [5, 6]],
)
def test_threshold_windows_map_to_inclusive_regions(case_report):
    values = [0.0, 1.7, 1.8, 0.2, 1.9]
    expected = [[2, 5], [5, 6]]
    actual = [list(region) for region in _regions_above_threshold(values, 6, 3, 1.6)]
    case_report(
        represents="Residue spans represented by consecutive qualifying windows",
        expected=expected,
        actual=actual,
        raw_input={"profile": values, "sequence_length": 6, "window_size": 3},
    )
    assert actual == expected


@pytest.mark.case(
    represents="Neutral polypeptide formula and feature coordinates for NATKRPWYC",
    category="features",
    expected={
        "formula": "C51H75N15O13S",
        "sequons": [1],
        "trypsin": [4],
        "cysteine_positions": [9],
    },
)
def test_extended_metrics_formula_and_positions_are_sequence_based(case_report):
    metrics = calculate_extended_metrics("NATKRPWYC", window_size=3)
    expected = {
        "formula": "C51H75N15O13S",
        "sequons": [1],
        "trypsin": [4],
        "cysteine_positions": [9],
    }
    actual = {
        "formula": metrics["formula"],
        "sequons": metrics["n_glycosylation_sequon_positions"],
        "trypsin": metrics["trypsin_cleavage_positions"],
        "cysteine_positions": metrics["cysteine_positions"],
    }
    case_report(
        represents="Atomic formula and 1-based N-sequon, trypsin, and cysteine positions",
        expected=expected,
        actual=actual,
        raw_input={"sequence": "NATKRPWYC", "window_size": 3},
    )
    assert actual == expected
    assert metrics["atomic_composition"] == {"C": 51, "H": 75, "N": 15, "O": 13, "S": 1}


@pytest.mark.case(
    represents="Molecular weight, GRAVY, and composition for ACD",
    category="properties",
    expected={
        "length": 3,
        "molecular_weight": 307.32,
        "average_residue_mass": 96.44,
        "gravy": 0.267,
        "composition": {"A": 1, "C": 1, "D": 1},
    },
)
def test_protein_statistics_match_independent_residue_sums(case_report):
    stats = calculate_protein_stats("ACD")
    expected = {
        "length": 3,
        "molecular_weight": 307.32,
        "average_residue_mass": 96.44,
        "gravy": 0.267,
        "composition": {"A": 1, "C": 1, "D": 1},
    }
    actual = {
        "length": stats.length,
        "molecular_weight": stats.molecular_weight,
        "average_residue_mass": stats.average_residue_mass,
        "gravy": stats.gravy,
        "composition": {key: stats.composition[key] for key in ("A", "C", "D")},
    }
    case_report(
        represents="Residue mass plus terminal water, average mass, Kyte-Doolittle mean, and counts",
        expected=expected,
        actual=actual,
        raw_input="ACD",
    )
    assert actual == expected


@pytest.mark.case(
    represents="Protease-specific cleavage around proline and methionine",
    category="cleavage",
    expected={
        "Trypsin": [],
        "Chymotrypsin": [],
        "Lys-C": [1],
        "Glu-C": [],
        "Arg-C": [3],
        "Asp-N": [6],
        "CNBr": [6],
    },
)
def test_cleavage_sites_apply_reference_enzyme_exceptions(case_report):
    sequence = "KPRPWMD"
    expected = {
        "Trypsin": [],
        "Chymotrypsin": [],
        "Lys-C": [1],
        "Glu-C": [],
        "Arg-C": [3],
        "Asp-N": [6],
        "CNBr": [6],
    }
    actual = cleavage_sites(sequence)
    case_report(
        represents="Lys-C and Arg-C cut despite following proline; W-M blocks chymotrypsin",
        expected=expected,
        actual=actual,
        raw_input=sequence,
    )
    assert actual == expected


@pytest.mark.case(
    represents="Henderson-Hasselbalch side-chain, terminal, and peptide charge",
    category="charge",
    expected={"lysine_side_chain": 0.999, "lysine_peptide": 0.7591},
)
def test_charge_calculations_match_hand_computed_values(case_report):
    expected = {"lysine_side_chain": 0.999, "lysine_peptide": 0.7591}
    actual = {
        "lysine_side_chain": round(residue_charge_at_ph("K", 7), 4),
        "lysine_peptide": net_charge_at_ph("K", 7),
    }
    case_report(
        represents="Lysine side-chain charge and one-residue peptide charge at pH 7",
        expected=expected,
        actual=actual,
        raw_input={"sequence": "K", "pH": 7},
    )
    assert actual == expected
    assert net_charge_at_ph("D", 2) > 0
    assert net_charge_at_ph("D", 12) < 0


@pytest.mark.case(
    represents="Theoretical pI from the zero-charge point for lysine",
    category="charge",
    expected=8.75,
)
def test_theoretical_pi_uses_zero_charge_bracketing(case_report):
    expected = 8.75
    actual = approximate_theoretical_pI("K")
    case_report(
        represents="pH at which the model's net charge is zero",
        expected=expected,
        actual=actual,
        raw_input="K",
    )
    assert isclose(actual, expected, abs_tol=0.01)


@pytest.mark.case(
    represents="Empty sequences and nonpositive windows are rejected",
    category="validation",
    expected="ValueError for empty stats, empty metrics, and nonpositive profile window",
)
def test_analysis_rejects_empty_sequence_and_invalid_window(case_report):
    with pytest.raises(ValueError):
        calculate_protein_stats(" \n ")
    with pytest.raises(ValueError):
        calculate_extended_metrics("")
    with pytest.raises(ValueError):
        hydrophobicity_profile("ACD", window_size=0)
    with pytest.raises(ValueError):
        calculate_extended_metrics("ACD", window_size=0)
    case_report(
        represents="Empty inputs and zero-sized windows raise ValueError",
        expected="ValueError in all four cases",
        actual="ValueError in all four cases",
        raw_input={"sequence": "", "window_size": 0},
    )


@pytest.mark.case(
    represents="Protein statistics summary formatting",
    category="reporting",
    expected=[("Length", "2"), ("Molecular weight", "192.23 Da")],
)
def test_summary_rows_format_residue_count_and_mass(case_report):
    stats = ProteinStats(
        sequence="AC",
        length=2,
        molecular_weight=192.23,
        average_residue_mass=87.11,
        unique_residues=2,
        theoretical_pI=5.5,
        charge_at_ph_7=-0.25,
        gravy=2.15,
        aromaticity=0.0,
        extinction_coefficient=0.0,
        composition={"A": 1, "C": 1},
    )
    expected = [("Length", "2"), ("Molecular weight", "192.23 Da")]
    actual = build_summary_table(stats)[:2]
    case_report(
        represents="First rows in the human-readable protein summary table",
        expected=expected,
        actual=actual,
        raw_input={"length": 2, "molecular_weight": 192.23},
    )
    assert actual == expected
