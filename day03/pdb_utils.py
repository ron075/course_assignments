from __future__ import annotations

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
