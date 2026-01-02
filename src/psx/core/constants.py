"""PSX constants and sector definitions."""

from typing import Optional

# Official PSX sector names (as of 2025)
PSX_SECTORS = [
    "Automobile Assembler",
    "Automobile Parts & Accessories",
    "Cable & Electrical Goods",
    "Cement",
    "Chemical",
    "Close-End Mutual Fund",
    "Commercial Banks",
    "Engineering",
    "Exchange Traded Funds",
    "Fertilizer",
    "Food & Personal Care Products",
    "Glass & Ceramics",
    "Insurance",
    "Inv. Banks / Inv. Cos. / Securities Cos.",
    "Jute",
    "Leasing Companies",
    "Leather & Tanneries",
    "Miscellaneous",
    "Modarabas",
    "Oil & Gas Exploration Companies",
    "Oil & Gas Marketing Companies",
    "Paper, Board & Packaging",
    "Pharmaceuticals",
    "Power Generation & Distribution",
    "Property",
    "Real Estate Investment Trust",
    "Refinery",
    "Sugar & Allied Industries",
    "Synthetic & Rayon",
    "Technology & Communication",
    "Textile Composite",
    "Textile Spinning",
    "Textile Weaving",
    "Tobacco",
    "Transport",
    "Vanaspati & Allied Industries",
    "Woollen",
]

# Known sector peer mappings (major companies by sector)
# Used as fallback when DB has no peers for a sector
SECTOR_PEERS = {
    "Oil & Gas Exploration Companies": ["OGDC", "PPL", "MARI", "POL"],
    "Oil & Gas Marketing Companies": ["PSO", "SHEL", "APL", "HASCOL"],
    "Cement": ["LUCK", "DGKC", "MLCF", "KOHC", "FCCL", "ACPL", "CHCC", "THCCL", "PIOC", "DWAN"],
    "Commercial Banks": ["HBL", "UBL", "MCB", "NBP", "BAFL", "MEBL", "ABL"],
    "Fertilizer": ["ENGRO", "FFC", "FFBL", "FATIMA"],
    "Power Generation & Distribution": ["HUBC", "KAPCO", "NPL", "NCPL", "KEL"],
    "Automobile Assembler": ["INDU", "PSMC", "HCAR", "MTL"],
    "Pharmaceuticals": ["SEARL", "GLAXO", "HINOON", "ABOT", "FEROZ"],
    "Technology & Communication": ["TRG", "SYS", "NETSOL"],
    "Insurance": ["JSGCL", "PKGI", "AICL", "EFU"],
    "Inv. Banks / Inv. Cos. / Securities Cos.": ["LSECL", "JSIL", "AKDHL"],
    "Food & Personal Care Products": ["NESTLE", "UNITY", "COLG", "FCEPL"],
    "Textile Composite": ["NML", "NCL", "GATM", "ILP"],
    "Sugar & Allied Industries": ["ALNRS", "AGSML", "JDWS", "MLCF"],
    "Chemical": ["LOTCHEM", "ICI", "EPCL"],
    "Refinery": ["ATRL", "NRL", "BYCO", "PRL"],
    "Glass & Ceramics": ["GHGL", "TGCL"],
    "Modarabas": ["AMTM", "FTML", "SMBL"],
}


def normalize_sector(sector: Optional[str]) -> Optional[str]:
    """Normalize sector name to match PSX official list.

    Args:
        sector: Raw sector name from scraping

    Returns:
        Normalized sector name or original if no match
    """
    if not sector:
        return None

    sector_lower = sector.lower().strip()

    # Filter out invalid sector names
    if sector_lower in ["stock screener", "screener", ""]:
        return None

    # Try to match against official sectors
    for official in PSX_SECTORS:
        official_lower = official.lower()
        # Exact match
        if sector_lower == official_lower:
            return official
        # Partial match (sector is substring or vice versa)
        if sector_lower in official_lower or official_lower in sector_lower:
            return official

    # Common abbreviation mappings
    abbrev_map = {
        "investment banks": "Inv. Banks / Inv. Cos. / Securities Cos.",
        "inv. banks": "Inv. Banks / Inv. Cos. / Securities Cos.",
        "securities": "Inv. Banks / Inv. Cos. / Securities Cos.",
        "oil & gas exploration": "Oil & Gas Exploration Companies",
        "oil exploration": "Oil & Gas Exploration Companies",
        "oil & gas marketing": "Oil & Gas Marketing Companies",
        "oil marketing": "Oil & Gas Marketing Companies",
        "power generation": "Power Generation & Distribution",
        "banks": "Commercial Banks",
        "pharma": "Pharmaceuticals",
        "tech": "Technology & Communication",
        "textile": "Textile Composite",
    }

    for abbrev, full in abbrev_map.items():
        if abbrev in sector_lower:
            return full

    # Return original if no match found
    return sector


def get_sector_peers(sector: str) -> list[str]:
    """Get known peer symbols for a sector.

    Args:
        sector: Sector name

    Returns:
        List of peer symbols (may be empty if unknown sector)
    """
    normalized = normalize_sector(sector)
    if normalized:
        return SECTOR_PEERS.get(normalized, [])
    return SECTOR_PEERS.get(sector, [])
