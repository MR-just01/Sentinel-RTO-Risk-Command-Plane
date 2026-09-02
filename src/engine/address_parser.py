"""
Address quality scoring engine for Indian logistics and delivery text.
Extracts structural, lexical, and typographical risk signals.
"""
import re
import numpy as np
import pandas as pd


COMMON_LANDMARK_REGEX = re.compile(
    r"\b(near|opp|opposite|behind|beside|front|temple|mandir|hospital|tanki|school|road|marg|gali|nagar|colony|flat|house|plot|floor|sector)\b",
    re.IGNORECASE
)

DIGIT_EXTRACTOR = re.compile(r"\d+")


def calculate_vowel_consonant_ratio(text: str) -> float:
    """Detects random keyboard mashing/gibberish (e.g., 'asdfghjk')."""
    text_clean = re.sub(r"[^a-zA-Z]", "", text.lower())
    if not text_clean:
        return 0.0
    vowels = sum(1 for c in text_clean if c in "aeiou")
    return vowels / len(text_clean)


def extract_address_features(df: pd.DataFrame, address_col: str = "delivery_address") -> pd.DataFrame:
    """
    Transforms raw delivery text into a structured numerical feature matrix.
    """
    features = pd.DataFrame(index=df.index)

    # 1. Structural features
    features["addr_char_length"] = df[address_col].str.len().fillna(0)
    features["addr_word_count"] = df[address_col].apply(lambda x: len(str(x).split()))
    
    # 2. House / Flat digit existence check
    features["addr_has_digits"] = df[address_col].apply(
        lambda x: 1 if DIGIT_EXTRACTOR.search(str(x)) else 0
    )
    features["addr_digit_count"] = df[address_col].apply(
        lambda x: len(DIGIT_EXTRACTOR.findall(str(x)))
    )

    # 3. Landmark & locality regex indicators
    features["addr_landmark_keyword_count"] = df[address_col].apply(
        lambda x: len(COMMON_LANDMARK_REGEX.findall(str(x)))
    )
    features["addr_has_landmark"] = (features["addr_landmark_keyword_count"] > 0).astype(int)

    # 4. Gibberish & text irregularity metrics
    features["addr_vowel_ratio"] = df[address_col].apply(calculate_vowel_consonant_ratio)
    # Abnormal vowel ratio (either too few vowels or all vowels) flags monkey-typing
    features["addr_is_gibberish_flag"] = (
        (features["addr_vowel_ratio"] < 0.15) | (features["addr_vowel_ratio"] > 0.70)
    ).astype(int)

    # 5. Length penalty (too short addresses have ~60% higher RTO failure)
    features["addr_is_too_short"] = (features["addr_word_count"] < 4).astype(int)

    return features