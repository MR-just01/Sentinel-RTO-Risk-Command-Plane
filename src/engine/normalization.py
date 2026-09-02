"""
Address Canonicalization & Anti-Evasion Normalizer.
Standardizes Indian address tokens and generates phonetic fingerprints.
"""
import re
from typing import Dict

# Common Indian street / locality abbreviation mapping
EXPANSIONS: Dict[str, str] = {
    r"\brd\b": "road",
    r"\bstn\b": "station",
    r"\bnear\b": "nr",
    r"\bopp\b": "opposite",
    r"\bapt\b": "apartment",
    r"\bflt\b": "flat",
    r"\bblk\b": "block",
    r"\bsec\b": "sector",
    r"\bext\b": "extension",
    r"\bmkt\b": "market",
    r"\bcol\b": "colony",
    r"\bnst\b": "nagar",
    r"\bflr\b": "floor"
}


def clean_address(raw_address: str) -> str:
    """Normalizes address string by lowering case, removing punctuation, and expanding tokens."""
    if not raw_address or not isinstance(raw_address, str):
        return ""
    
    text = raw_address.lower().strip()
    # Strip non-alphanumeric except spaces
    text = re.sub(r"[^\w\s]", " ", text)
    
    # Expand standard abbreviations
    for pattern, replacement in EXPANSIONS.items():
        text = re.sub(pattern, replacement, text)
        
    # Collapse repetitive whitespaces
    return " ".join(text.split())


def calculate_entropy(text: str) -> float:
    """Calculates Shannon entropy to flag keyboard-mash / gibberish addresses."""
    import math
    from collections import Counter
    
    clean = text.replace(" ", "")
    if not clean:
        return 0.0
        
    counts = Counter(clean)
    length = len(clean)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def soundex_token(token: str) -> str:
    """Produces Soundex code for phonetic matching across misspelled names/localities."""
    if not token:
        return "0000"
    
    token = token.upper()
    mapping = {
        "BFPV": "1", "CGJKQSXZ": "2", "DT": "3",
        "L": "4", "MN": "5", "R": "6"
    }
    
    code = [token[0]]
    prev = ""
    for char in token[1:]:
        for keys, val in mapping.items():
            if char in keys:
                if val != prev:
                    code.append(val)
                    prev = val
                break
        else:
            prev = ""
            
    code_str = "".join(code).replace("0", "")
    return (code_str + "0000")[:4]


def phonetic_address_fingerprint(clean_text: str) -> str:
    """Generates an order-independent phonetic fingerprint for duplicate abuse clustering."""
    tokens = sorted(list(set(clean_text.split())))
    return "-".join(soundex_token(t) for t in tokens if len(t) > 2)