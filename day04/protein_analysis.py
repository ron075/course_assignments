from __future__ import annotations

from dataclasses import dataclass, field
from math import log2
from typing import Dict, List, Tuple, TypedDict

AA_NAMES = {
    "A": "Alanine",
    "R": "Arginine",
    "N": "Asparagine",
    "D": "Aspartic acid",
    "C": "Cysteine",
    "E": "Glutamic acid",
    "Q": "Glutamine",
    "G": "Glycine",
    "H": "Histidine",
    "I": "Isoleucine",
    "L": "Leucine",
    "K": "Lysine",
    "M": "Methionine",
    "F": "Phenylalanine",
    "P": "Proline",
    "S": "Serine",
    "T": "Threonine",
    "W": "Tryptophan",
    "Y": "Tyrosine",
    "V": "Valine",
}

AA_TO_THREE = {
    "A": "ALA",
    "R": "ARG",
    "N": "ASN",
    "D": "ASP",
    "C": "CYS",
    "E": "GLU",
    "Q": "GLN",
    "G": "GLY",
    "H": "HIS",
    "I": "ILE",
    "L": "LEU",
    "K": "LYS",
    "M": "MET",
    "F": "PHE",
    "P": "PRO",
    "S": "SER",
    "T": "THR",
    "W": "TRP",
    "Y": "TYR",
    "V": "VAL",
}

THREE_TO_AA = {value: key for key, value in AA_TO_THREE.items()}

RESIDUE_MASSES = {
    "A": 71.0788,
    "R": 156.1875,
    "N": 114.1038,
    "D": 115.0886,
    "C": 103.1388,
    "E": 129.1155,
    "Q": 128.1307,
    "G": 57.0519,
    "H": 137.1393,
    "I": 113.1594,
    "L": 113.1594,
    "K": 128.1741,
    "M": 131.1926,
    "F": 147.1766,
    "P": 97.1167,
    "S": 87.0782,
    "T": 101.1051,
    "W": 186.2132,
    "Y": 163.1760,
    "V": 99.1326,
}

AMBIGUOUS_RESIDUES = {
    "B": 0.5 * (RESIDUE_MASSES["D"] + RESIDUE_MASSES["N"]),
    "Z": 0.5 * (RESIDUE_MASSES["E"] + RESIDUE_MASSES["Q"]),
    "J": 0.5 * (RESIDUE_MASSES["I"] + RESIDUE_MASSES["L"]),
    "X": 110.0,
}

HYDROPHOBICITY = {
    "A": 1.8,
    "C": 2.5,
    "D": -3.5,
    "E": -3.5,
    "F": 2.8,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "K": -3.9,
    "L": 3.8,
    "M": 1.9,
    "N": -3.5,
    "P": -1.6,
    "Q": -3.5,
    "R": -4.5,
    "S": -0.8,
    "T": -0.7,
    "V": 4.2,
    "W": -0.9,
    "Y": -1.3,
}

AROMATIC_RESIDUES = {"F", "W", "Y"}
BASIC_RESIDUES = {"K": 10.5, "R": 12.5, "H": 6.0}
ACIDIC_RESIDUES = {"D": 3.9, "E": 4.1, "C": 8.3, "Y": 10.1}
TERMINUS_PKA = {"N": 8.0, "C": 3.1}
VALID_RESIDUES = set(AA_NAMES) | set(AMBIGUOUS_RESIDUES)

# Guruprasad et al. (1990) pair weights; unlisted pairs use the standard value 1.
_INSTABILITY_WEIGHT_EXCEPTIONS = """
AC 44.94 AD -7.49 AH -7.49 AP 20.26
CD 20.26 CH 33.60 CM 33.60 CL 20.26 CQ -6.54 CP 20.26 CT 33.60 CW 24.68 CV -6.54
EC 44.94 EE 33.60 ED 20.26 EI 20.26 EH -6.54 EQ 20.26 EP 20.26 ES 20.26 EW -14.03
DF -6.54 DK -7.49 DS 20.26 DR -6.54 DT -14.03
GA -7.49 GE -6.54 GG 13.34 GI -7.49 GK -7.49 GN -7.49 GT -7.49 GW 13.34 GY -7.49
FD 13.34 FK -14.03 FP 20.26 FY 33.601
IE 44.94 IH 13.34 IK -7.49 IL 20.26 IP -1.88 IV -7.49
HG -9.37 HF -9.37 HI 44.94 HK 24.68 HN 24.68 HP -1.88 HT -6.54 HW -1.88 HY 44.94
KG -7.49 KI -7.49 KM 33.60 KL -7.49 KQ 24.64 KP -6.54 KR 33.60 KV -7.49
MA 13.34 MH 58.28 MM -1.88 MQ -6.54 MP 44.94 MS 44.94 MR -6.54 MT -1.88 MY 24.68
LK -7.49 LQ 33.60 LP 20.26 LR 20.26 LW 24.68
NC -1.88 NG -14.03 NF -14.03 NI 44.94 NK 24.68 NQ -6.54 NP -1.88 NT -7.49 NW -9.37
QC -6.54 QE 20.26 QD 20.26 QF -6.54 QQ 20.26 QP 20.26 QS 44.94 QV -6.54 QY -6.54
PA 20.26 PC -6.54 PE 18.38 PD -6.54 PF 20.26 PM -6.54 PQ 20.26 PP 20.26 PS 20.26 PR -6.54 PW -1.88 PV 20.26
SC 33.60 SE 20.26 SQ 20.26 SP 44.94 SS 20.26 SR 20.26
RG -7.49 RH 20.26 RN 13.34 RQ 20.26 RP 20.26 RS 44.94 RR 58.28 RW 58.28 RY -6.54
TE 20.26 TG -7.49 TF 13.34 TN -14.03 TQ -6.54 TW -14.03
WA -14.03 WG -9.37 WH 24.68 WM 24.68 WL 13.34 WN 13.34 WT -14.03 WV -7.49
VD -14.03 VG -7.49 VK -1.88 VP 20.26 VT -7.49 VY -6.54
YA 24.68 YE -6.54 YD 24.68 YG -7.49 YH 13.34 YM 44.94 YP 13.34 YR -15.91 YT -7.49 YW -9.37 YY 13.34
"""
INSTABILITY_WEIGHT_EXCEPTIONS = {
    pair: float(value)
    for line in _INSTABILITY_WEIGHT_EXCEPTIONS.splitlines()
    for pair, value in zip(line.split()[::2], line.split()[1::2])
}

N_TERMINAL_HALF_LIFE = {
    "A": ("4.4 hours", ">20 hours", ">10 hours"),
    "R": ("1 hour", "2 min", "2 min"),
    "N": ("1.4 hours", "3 min", ">10 hours"),
    "D": ("1.1 hours", "3 min", ">10 hours"),
    "C": ("1.2 hours", ">20 hours", ">10 hours"),
    "Q": ("0.8 hours", "10 min", ">10 hours"),
    "E": ("1 hour", "30 min", ">10 hours"),
    "G": ("30 hours", ">20 hours", ">10 hours"),
    "H": ("3.5 hours", "10 min", ">10 hours"),
    "I": ("20 hours", "30 min", ">10 hours"),
    "L": ("5.5 hours", "3 min", "2 min"),
    "K": ("1.3 hours", "3 min", "2 min"),
    "M": ("30 hours", ">20 hours", ">10 hours"),
    "F": ("1.1 hours", "3 min", "2 min"),
    "P": (">20 hours", ">20 hours", "Unknown"),
    "S": ("1.9 hours", ">20 hours", ">10 hours"),
    "T": ("7.2 hours", ">20 hours", ">10 hours"),
    "W": ("2.8 hours", "3 min", "2 min"),
    "Y": ("2.8 hours", "10 min", "2 min"),
    "V": ("100 hours", ">20 hours", ">10 hours"),
}

FREE_AMINO_ACID_FORMULAS = {
    "A": {"C": 3, "H": 7, "N": 1, "O": 2},
    "R": {"C": 6, "H": 14, "N": 4, "O": 2},
    "N": {"C": 4, "H": 8, "N": 2, "O": 3},
    "D": {"C": 4, "H": 7, "N": 1, "O": 4},
    "C": {"C": 3, "H": 7, "N": 1, "O": 2, "S": 1},
    "E": {"C": 5, "H": 9, "N": 1, "O": 4},
    "Q": {"C": 5, "H": 10, "N": 2, "O": 3},
    "G": {"C": 2, "H": 5, "N": 1, "O": 2},
    "H": {"C": 6, "H": 9, "N": 3, "O": 2},
    "I": {"C": 6, "H": 13, "N": 1, "O": 2},
    "L": {"C": 6, "H": 13, "N": 1, "O": 2},
    "K": {"C": 6, "H": 14, "N": 2, "O": 2},
    "M": {"C": 5, "H": 11, "N": 1, "O": 2, "S": 1},
    "F": {"C": 9, "H": 11, "N": 1, "O": 2},
    "P": {"C": 5, "H": 9, "N": 1, "O": 2},
    "S": {"C": 3, "H": 7, "N": 1, "O": 3},
    "T": {"C": 4, "H": 9, "N": 1, "O": 3},
    "W": {"C": 11, "H": 12, "N": 2, "O": 2},
    "Y": {"C": 9, "H": 11, "N": 1, "O": 3},
    "V": {"C": 5, "H": 11, "N": 1, "O": 2},
}


@dataclass
class ProteinStats:
    sequence: str
    length: int
    molecular_weight: float
    average_residue_mass: float
    unique_residues: int
    theoretical_pI: float
    charge_at_ph_7: float
    gravy: float
    aromaticity: float
    extinction_coefficient: float
    composition: Dict[str, int]
    invalid_characters: List[str] = field(default_factory=list)

    def table_rows(self) -> List[Tuple[str, str]]:
        return [
            ("Length", str(self.length)),
            ("Molecular weight", f"{self.molecular_weight:.2f} Da"),
            ("Average residue mass", f"{self.average_residue_mass:.2f} Da"),
            ("Unique residues", str(self.unique_residues)),
            ("Theoretical pI", f"{self.theoretical_pI:.2f}"),
            ("Charge at pH 7", f"{self.charge_at_ph_7:.2f}"),
            ("GRAVY score", f"{self.gravy:.3f}"),
            ("Aromaticity", f"{self.aromaticity:.3%}"),
        ]


class ExtendedMetrics(TypedDict):
    formula: str | None
    atomic_composition: Dict[str, int] | None
    total_atoms: int | None
    extinction_coefficient_oxidized: float
    extinction_coefficient_reduced: float
    n_terminal_residue: str
    estimated_half_life: Tuple[str, str, str]
    instability_index: float | None
    stability_classification: str
    positive_residues: int
    negative_residues: int
    basic_residue_percent: float
    acidic_residue_percent: float
    cysteine_count: int
    potential_disulfide_pairs: int
    aliphatic_index: float
    shannon_entropy_bits: float
    n_glycosylation_sequon_positions: List[int]
    trypsin_cleavage_positions: List[int]
    cleavage_sites: Dict[str, List[int]]
    signal_peptide_cleavage_candidates: List[int]
    phosphorylation_candidate_positions: List[int]
    cysteine_positions: List[int]
    hydrophobicity_window_size: int
    hydrophobicity_profile: List[float]
    hydrophobic_regions: List[Tuple[int, int]]
    transmembrane_regions: List[Tuple[int, int]]
    serine_threonine_rich_regions: List[Tuple[int, int]]
    low_complexity_regions: List[Tuple[int, int]]
    charge_profile: List[Tuple[float, float]]
    invalid_characters: List[str]


def normalize_sequence(sequence: str) -> Tuple[str, List[str]]:
    sequence_lines = (
        line.strip()
        for line in sequence.splitlines()
        if not line.lstrip().startswith(">")
    )
    raw_sequence = "".join("".join(sequence_lines).upper().split())
    invalid = sorted({ch for ch in raw_sequence if ch not in VALID_RESIDUES})
    cleaned = "".join(ch for ch in raw_sequence if ch in VALID_RESIDUES)
    return cleaned, invalid


def _residue_mass(letter: str) -> float:
    if letter in RESIDUE_MASSES:
        return RESIDUE_MASSES[letter]
    if letter in AMBIGUOUS_RESIDUES:
        return AMBIGUOUS_RESIDUES[letter]
    return 0.0


def count_amino_acids(sequence: str) -> Dict[str, int]:
    counts = {residue: 0 for residue in sorted(AA_NAMES)}
    for residue in sequence:
        if residue in counts:
            counts[residue] += 1
        elif residue in AMBIGUOUS_RESIDUES:
            counts.setdefault(residue, 0)
            counts[residue] += 1
    return counts


def hydrophobicity_profile(sequence: str, window_size: int = 5) -> List[float]:
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    values: List[float] = []
    for idx in range(len(sequence) - window_size + 1):
        window = sequence[idx : idx + window_size]
        val = sum(HYDROPHOBICITY.get(residue, 0.0) for residue in window) / len(window)
        values.append(val)
    return values


def cleavage_sites(sequence: str) -> Dict[str, List[int]]:
    sites: Dict[str, List[int]] = {
        "Trypsin": [],
        "Chymotrypsin": [],
        "Lys-C": [],
        "Glu-C": [],
        "Arg-C": [],
        "Asp-N": [],
        "CNBr": [],
    }
    for index, residue in enumerate(sequence):
        next_residue = sequence[index + 1] if index + 1 < len(sequence) else ""
        cut_after = index + 1
        if residue in {"K", "R"} and next_residue != "P":
            sites["Trypsin"].append(cut_after)
        if residue in {"F", "W", "Y"} and next_residue != "P":
            sites["Chymotrypsin"].append(cut_after)
        if residue == "K" and next_residue != "P":
            sites["Lys-C"].append(cut_after)
        if residue == "E" and next_residue != "P":
            sites["Glu-C"].append(cut_after)
        if residue == "R" and next_residue != "P":
            sites["Arg-C"].append(cut_after)
        if residue == "D" and index > 0:
            sites["Asp-N"].append(index)
        if residue == "M":
            sites["CNBr"].append(cut_after)
    return sites


def signal_peptide_cleavage_candidates(sequence: str) -> List[int]:
    small_residues = {"A", "G", "S", "T", "V"}
    candidates = []
    for cut_after in range(12, min(35, len(sequence) - 1) + 1):
        minus_three = sequence[cut_after - 3]
        minus_one = sequence[cut_after - 1]
        hydrophobic_segment = sequence[max(0, cut_after - 12) : cut_after - 3]
        mean_hydrophobicity = sum(
            HYDROPHOBICITY.get(residue, 0.0) for residue in hydrophobic_segment
        ) / max(len(hydrophobic_segment), 1)
        if (
            minus_three in small_residues
            and minus_one in small_residues
            and mean_hydrophobicity >= 1.2
        ):
            candidates.append(cut_after)
    return candidates


def _regions_above_threshold(
    values: List[float], sequence_length: int, window_size: int, threshold: float
) -> List[Tuple[int, int]]:
    regions = []
    start = None
    for index, value in enumerate(values):
        if value >= threshold:
            if start is None:
                start = index + 1
        elif start is not None:
            regions.append((start, index + window_size - 1))
            start = None
    if start is not None:
        regions.append((start, sequence_length))
    return regions


def calculate_extended_metrics(
    sequence: str, window_size: int = 7
) -> ExtendedMetrics:
    cleaned, invalid = normalize_sequence(sequence)
    if not cleaned:
        raise ValueError("The sequence is empty or contains only invalid characters.")
    if window_size <= 0:
        raise ValueError("window_size must be positive.")

    counts = count_amino_acids(cleaned)
    length = len(cleaned)
    formula = None
    atomic_composition = None
    total_atoms = None
    if not any(residue in AMBIGUOUS_RESIDUES for residue in cleaned):
        atom_counts = {element: 0 for element in ("C", "H", "N", "O", "S")}
        for residue in cleaned:
            for element, count in FREE_AMINO_ACID_FORMULAS[residue].items():
                atom_counts[element] += count
            atom_counts["H"] -= 2
            atom_counts["O"] -= 1
        atom_counts["H"] += 2
        atom_counts["O"] += 1
        atomic_composition = atom_counts
        total_atoms = sum(atom_counts.values())
        formula = "".join(
            f"{element}{atom_counts[element] if atom_counts[element] != 1 else ''}"
            for element in ("C", "H", "N", "O", "S")
            if atom_counts[element]
        )

    positive = sum(counts.get(residue, 0) for residue in ("K", "R", "H"))
    negative = sum(counts.get(residue, 0) for residue in ("D", "E"))
    aliphatic_index = (
        100.0
        * (
            counts["A"]
            + 2.9 * counts["V"]
            + 3.9 * (counts["I"] + counts["L"])
        )
        / length
    )
    known_residue_count = sum(counts[residue] for residue in AA_NAMES)
    entropy = 0.0
    for residue in AA_NAMES:
        count = counts[residue]
        if count and known_residue_count:
            frequency = count / known_residue_count
            entropy -= frequency * log2(frequency)

    sequons = [
        index + 1
        for index in range(length - 2)
        if cleaned[index] == "N"
        and cleaned[index + 1] != "P"
        and cleaned[index + 2] in {"S", "T"}
    ]
    trypsin_sites = [
        index + 1
        for index, residue in enumerate(cleaned[:-1])
        if residue in {"K", "R"} and cleaned[index + 1] != "P"
    ]
    if cleaned[-1] in {"K", "R"}:
        trypsin_sites.append(length)

    cleavage_profile = cleavage_sites(cleaned)
    cleavage_profile["Trypsin"] = trypsin_sites
    profile = hydrophobicity_profile(cleaned, window_size)
    hydrophobic_regions = _regions_above_threshold(profile, length, window_size, 1.6)
    transmembrane_profile = hydrophobicity_profile(cleaned, window_size=19)
    transmembrane_regions = _regions_above_threshold(
        transmembrane_profile, length, 19, 1.6
    )
    serine_threonine_profile = [
        sum(residue in {"S", "T"} for residue in cleaned[index : index + 10]) / 10
        for index in range(max(0, length - 9))
    ]
    serine_threonine_regions = _regions_above_threshold(
        serine_threonine_profile, length, 10, 0.5
    )
    low_complexity_profile = [
        max(
            cleaned[index : index + 12].count(residue)
            for residue in set(cleaned[index : index + 12])
        ) / 12
        for index in range(max(0, length - 11))
    ]
    low_complexity_regions = _regions_above_threshold(
        low_complexity_profile, length, 12, 0.6
    )
    phosphorylation_positions = [
        index + 1
        for index, residue in enumerate(cleaned)
        if residue in {"S", "T", "Y"}
    ]
    instability_index = None
    stability_classification = "Unavailable for ambiguous residues"
    if all(residue in AA_NAMES for residue in cleaned):
        instability_index = 10.0 * sum(
            INSTABILITY_WEIGHT_EXCEPTIONS.get(cleaned[index : index + 2], 1.0)
            for index in range(length - 1)
        ) / length
        stability_classification = (
            "Stable" if instability_index < 40 else "Unstable"
        )
    n_terminal_residue = cleaned[0]
    estimated_half_life = N_TERMINAL_HALF_LIFE.get(
        n_terminal_residue, ("Unavailable", "Unavailable", "Unavailable")
    )

    charge_profile = [
        (ph, net_charge_at_ph(cleaned, ph))
        for ph in (0, 2, 4, 6, 7, 8, 10, 12, 14)
    ]

    return {
        "formula": formula,
        "atomic_composition": atomic_composition,
        "total_atoms": total_atoms,
        "extinction_coefficient_oxidized": float(
            5500 * counts["W"] + 1490 * counts["Y"] + 125 * (counts["C"] // 2)
        ),
        "extinction_coefficient_reduced": float(
            5500 * counts["W"] + 1490 * counts["Y"]
        ),
        "n_terminal_residue": n_terminal_residue,
        "estimated_half_life": estimated_half_life,
        "instability_index": instability_index,
        "stability_classification": stability_classification,
        "positive_residues": positive,
        "negative_residues": negative,
        "basic_residue_percent": 100.0 * positive / length,
        "acidic_residue_percent": 100.0 * negative / length,
        "cysteine_count": counts["C"],
        "potential_disulfide_pairs": counts["C"] // 2,
        "aliphatic_index": aliphatic_index,
        "shannon_entropy_bits": entropy,
        "n_glycosylation_sequon_positions": sequons,
        "trypsin_cleavage_positions": trypsin_sites,
        "cleavage_sites": cleavage_profile,
        "signal_peptide_cleavage_candidates": signal_peptide_cleavage_candidates(
            cleaned
        ),
        "phosphorylation_candidate_positions": phosphorylation_positions,
        "cysteine_positions": [
            index + 1 for index, residue in enumerate(cleaned) if residue == "C"
        ],
        "hydrophobicity_window_size": window_size,
        "hydrophobicity_profile": profile,
        "hydrophobic_regions": hydrophobic_regions,
        "transmembrane_regions": transmembrane_regions,
        "serine_threonine_rich_regions": serine_threonine_regions,
        "low_complexity_regions": low_complexity_regions,
        "charge_profile": charge_profile,
        "invalid_characters": invalid,
    }


def calculate_protein_stats(sequence: str) -> ProteinStats:
    cleaned, invalid = normalize_sequence(sequence)
    if not cleaned:
        raise ValueError("The sequence is empty or contains only whitespace.")

    composition = count_amino_acids(cleaned)
    total_residue_mass = sum(_residue_mass(residue) for residue in cleaned)
    molecular_weight = total_residue_mass + 18.01528
    average_residue_mass = total_residue_mass / len(cleaned)
    unique_residues = len({residue for residue in cleaned if residue in AA_NAMES})

    gravy = 0.0
    if cleaned:
        gravy = sum(HYDROPHOBICITY.get(residue, 0.0) for residue in cleaned if residue in HYDROPHOBICITY) / len(cleaned)

    aromatic_count = sum(1 for residue in cleaned if residue in AROMATIC_RESIDUES)
    aromaticity = aromatic_count / len(cleaned)

    try:
        theoretical_pI = approximate_theoretical_pI(cleaned)
    except ValueError:
        theoretical_pI = 7.0
    charge_at_ph_7 = net_charge_at_ph(cleaned, 7.0)

    extinction = (
        5500 * composition["W"]
        + 1490 * composition["Y"]
        + 125 * (composition["C"] // 2)
    )
    extinction = round(extinction, 2)

    return ProteinStats(
        sequence=cleaned,
        length=len(cleaned),
        molecular_weight=round(molecular_weight, 2),
        average_residue_mass=round(average_residue_mass, 2),
        unique_residues=unique_residues,
        theoretical_pI=round(theoretical_pI, 2),
        charge_at_ph_7=round(charge_at_ph_7, 2),
        gravy=round(gravy, 3),
        aromaticity=round(aromaticity, 4),
        extinction_coefficient=extinction,
        composition=composition,
        invalid_characters=invalid,
    )


def net_charge_at_ph(sequence: str, ph: float) -> float:
    if not sequence:
        charge = 1.0 / (1.0 + 10 ** (TERMINUS_PKA["N"] - ph))
        charge -= 1.0 / (1.0 + 10 ** (ph - TERMINUS_PKA["C"]))
        return round(charge, 4)
    return round(
        sum(
            residue_charge_at_ph(
                residue,
                ph,
                is_n_terminal=index == 0,
                is_c_terminal=index == len(sequence) - 1,
            )
            for index, residue in enumerate(sequence)
        ),
        4,
    )


def residue_charge_at_ph(
    residue: str,
    ph: float,
    is_n_terminal: bool = False,
    is_c_terminal: bool = False,
) -> float:
    """Estimate one residue's side-chain and optional terminal charge at a pH."""
    charge = 0.0
    positive_pka = BASIC_RESIDUES.get(residue)
    if positive_pka is not None:
        charge += 1.0 / (1.0 + 10 ** (ph - positive_pka))
    negative_pka = ACIDIC_RESIDUES.get(residue)
    if negative_pka is not None:
        charge -= 1.0 / (1.0 + 10 ** (negative_pka - ph))
    if is_n_terminal:
        charge += 1.0 / (1.0 + 10 ** (ph - TERMINUS_PKA["N"]))
    if is_c_terminal:
        charge -= 1.0 / (1.0 + 10 ** (TERMINUS_PKA["C"] - ph))
    return charge


def approximate_theoretical_pI(sequence: str) -> float:
    if not sequence:
        raise ValueError("Sequence is empty.")
    low, high = 0.0, 14.0
    low_charge = net_charge_at_ph(sequence, low)
    high_charge = net_charge_at_ph(sequence, high)
    if low_charge == 0:
        return low
    if high_charge == 0:
        return high
    if low_charge * high_charge > 0:
        return 7.0

    for _ in range(50):
        midpoint = (low + high) / 2
        midpoint_charge = net_charge_at_ph(sequence, midpoint)
        if midpoint_charge == 0:
            return round(midpoint, 3)
        if low_charge * midpoint_charge > 0:
            low, low_charge = midpoint, midpoint_charge
        else:
            high, high_charge = midpoint, midpoint_charge
    return round((low + high) / 2, 3)


def build_summary_table(stats: ProteinStats) -> List[Tuple[str, str]]:
    return stats.table_rows()
