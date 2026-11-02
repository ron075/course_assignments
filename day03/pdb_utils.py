from __future__ import annotations

import re
import shlex
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

THREE_TO_AA = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLU": "E",
    "GLN": "Q",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
}


def fetch_pdb_text(pdb_id: str) -> str:
    identifier = pdb_id.strip().upper()
    if not identifier:
        raise ValueError("A PDB ID is required.")
    if len(identifier) != 4:
        raise ValueError("PDB IDs should be four characters long, such as 1ABC.")

    url = f"https://files.rcsb.org/download/{identifier}.pdb"
    request = Request(url, headers={"User-Agent": "ProteinAnalysisStudio/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Unable to retrieve PDB {identifier}: {exc}") from exc


def parse_pdb_chains(pdb_text: str) -> Dict[str, str]:
    if any(
        line.startswith("data_") or line.startswith("_entity_poly.")
        for line in pdb_text.splitlines()
    ):
        return _parse_mmcif_chains(pdb_text)

    chains: Dict[str, str] = {}
    for line in pdb_text.splitlines():
        if not line.startswith("SEQRES"):
            continue
        chain_id = line[11:12].strip()
        if not chain_id:
            continue
        residues = line[19:].split()
        for residue in residues:
            aa = THREE_TO_AA.get(residue)
            if aa is not None:
                chains.setdefault(chain_id, "")
                chains[chain_id] += aa

    if chains:
        return chains

    atom_chains: Dict[str, str] = {}
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM") or len(line) < 30:
            continue
        if line[12:16].strip() != "CA":
            continue
        chain_id = line[21:22].strip()
        residue = line[17:20].strip()
        aa = THREE_TO_AA.get(residue)
        if aa is None:
            continue
        atom_chains.setdefault(chain_id, "")
        atom_chains[chain_id] += aa

    return atom_chains


def _mmcif_tokens(cif_text: str) -> List[str]:
    tokens: List[str] = []
    lines = cif_text.splitlines()
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]
        if line.startswith(";"):
            value_lines = [line[1:]]
            line_index += 1
            while line_index < len(lines) and not lines[line_index].startswith(";"):
                value_lines.append(lines[line_index])
                line_index += 1
            tokens.append("\n".join(value_lines))
        else:
            try:
                tokens.extend(shlex.split(line, comments=True, posix=True))
            except ValueError as exc:
                raise ValueError(f"Malformed mmCIF text: {exc}") from exc
        line_index += 1
    return tokens


def _mmcif_loops(cif_text: str) -> List[tuple[List[str], List[List[str]]]]:
    tokens = _mmcif_tokens(cif_text)
    loops: List[tuple[List[str], List[List[str]]]] = []
    index = 0
    while index < len(tokens):
        if tokens[index].lower() != "loop_":
            index += 1
            continue
        index += 1
        headers: List[str] = []
        while index < len(tokens) and tokens[index].startswith("_"):
            headers.append(tokens[index].lower())
            index += 1
        if not headers:
            continue

        values: List[str] = []
        while index < len(tokens):
            token = tokens[index]
            row_boundary = len(values) % len(headers) == 0
            if row_boundary and (
                token.lower() in {"loop_", "stop_"}
                or token.lower().startswith(("data_", "save_"))
                or token.startswith("_")
            ):
                break
            values.append(token)
            index += 1
        rows = [
            values[offset : offset + len(headers)]
            for offset in range(0, len(values) - len(values) % len(headers), len(headers))
        ]
        loops.append((headers, rows))
    return loops


def _one_letter_sequence(raw_sequence: str) -> str:
    sequence = re.sub(r"\([^)]*\)", "", raw_sequence).upper()
    allowed = set(THREE_TO_AA.values()) | set("BZJX")
    return "".join(residue for residue in sequence if residue in allowed)


def _parse_mmcif_chains(cif_text: str) -> Dict[str, str]:
    chains: Dict[str, str] = {}
    for headers, rows in _mmcif_loops(cif_text):
        strand_column = "_entity_poly.pdbx_strand_id"
        sequence_column = "_entity_poly.pdbx_seq_one_letter_code_can"
        if strand_column not in headers or sequence_column not in headers:
            continue
        strand_index = headers.index(strand_column)
        sequence_index = headers.index(sequence_column)
        for row in rows:
            sequence = _one_letter_sequence(row[sequence_index])
            if not sequence or row[strand_index] in {".", "?"}:
                continue
            for chain_id in row[strand_index].split(","):
                chain_id = chain_id.strip()
                if chain_id:
                    chains.setdefault(chain_id, sequence)
        if chains:
            return chains

    return _parse_mmcif_atom_site(cif_text)


def _parse_mmcif_atom_site(cif_text: str) -> Dict[str, str]:
    for headers, rows in _mmcif_loops(cif_text):
        if not any(header.startswith("_atom_site.") for header in headers):
            continue
        columns = {header: index for index, header in enumerate(headers)}
        atom_column = columns.get("_atom_site.auth_atom_id", columns.get("_atom_site.label_atom_id"))
        residue_column = columns.get("_atom_site.auth_comp_id", columns.get("_atom_site.label_comp_id"))
        chain_column = columns.get("_atom_site.auth_asym_id", columns.get("_atom_site.label_asym_id"))
        sequence_column = columns.get("_atom_site.auth_seq_id", columns.get("_atom_site.label_seq_id"))
        insertion_column = columns.get("_atom_site.pdbx_pdb_ins_code")
        model_column = columns.get("_atom_site.pdbx_pdb_model_num")
        if None in (atom_column, residue_column, chain_column, sequence_column):
            continue

        chains: Dict[str, str] = {}
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            if row[atom_column] != "CA":
                continue
            if model_column is not None and row[model_column] not in {"1", ".", "?"}:
                continue
            chain_id = row[chain_column]
            residue_key = row[sequence_column]
            insertion_code = row[insertion_column] if insertion_column is not None else ""
            key = (chain_id, residue_key, insertion_code)
            if key in seen:
                continue
            amino_acid = THREE_TO_AA.get(row[residue_column].upper())
            if amino_acid is None:
                continue
            seen.add(key)
            chains.setdefault(chain_id, "")
            chains[chain_id] += amino_acid
        return chains
    return {}
