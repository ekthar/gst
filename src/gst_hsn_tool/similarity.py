"""
Similarity matching for product names using fuzzy matching and keyword matching.
"""

from typing import List, Dict, Optional
from fuzzywuzzy import fuzz
from . import db


STOP_TOKENS = {
    "rs",
    "mrp",
    "pcs",
    "pc",
    "ml",
    "gm",
    "g",
    "kg",
    "small",
    "big",
    "pack",
    "set",
    "inch",
    "cm",
    "mm",
    "nos",
}


def _tokens(text: str) -> set[str]:
    parts = [p.strip().lower() for p in text.replace("-", " ").replace("/", " ").split()]
    return {p for p in parts if len(p) > 2 and not p.isdigit() and p not in STOP_TOKENS}


def _overlap_score(query: str, candidate: str) -> float:
    q = _tokens(query)
    c = _tokens(candidate)
    if not q or not c:
        return 0.0
    inter = len(q & c)
    return inter / max(1, len(q))


def fuzzy_match(query: str, candidates: List[str], threshold: int = 80) -> List[tuple]:
    """
    Perform fuzzy matching between query and candidates.
    Returns list of (name, score) tuples sorted by score (descending).
    """
    results = []
    for candidate in candidates:
        score = fuzz.token_set_ratio(query.lower(), candidate.lower())
        overlap = _overlap_score(query, candidate)
        # Guard against false positives caused by common commercial tokens.
        if score >= threshold and overlap >= 0.5:
            results.append((candidate, score))
    
    return sorted(results, key=lambda x: x[1], reverse=True)


def keyword_match(query: str, candidates: List[str]) -> List[str]:
    """
    Match based on keyword overlap.
    Returns list of candidate names that share keywords with query.
    """
    query_words = _tokens(query)
    results = []
    
    for candidate in candidates:
        candidate_words = _tokens(candidate)
        overlap = query_words & candidate_words
        # Require stronger overlap to avoid mapping many rows to one wrong product.
        min_overlap = 1 if len(query_words) <= 2 else 2
        if len(overlap) >= min_overlap:
            results.append(candidate)
    
    return results


def find_similar_in_db(query: str, threshold: int = 80) -> Optional[Dict]:
    """
    Search database for similar products.
    Returns the best match if confidence is high, else None.
    
    Matching strategy:
    1. Exact match (100% confidence)
    2. Fuzzy match (80%+ confidence)
    3. Keyword match (fallback)
    """
    # Try exact match first
    product = db.get_product(query)
    if product:
        return {**product, 'match_type': 'exact', 'confidence': 100}
    
    # Get all products for fuzzy matching
    all_products = db.get_all_products(limit=10000)
    all_names = [p['name'] for p in all_products]
    
    # Try fuzzy match
    fuzzy_results = fuzzy_match(query, all_names, threshold)
    if fuzzy_results:
        best_match_name = fuzzy_results[0][0]
        best_match_score = fuzzy_results[0][1]
        product = db.get_product(best_match_name)
        if product:
            return {**product, 'match_type': 'fuzzy', 'confidence': best_match_score}
    
    # Try keyword match as fallback
    keyword_results = keyword_match(query, all_names)
    if keyword_results:
        # Pick best candidate by token overlap, then fuzzy score.
        ranked = sorted(
            keyword_results,
            key=lambda n: (_overlap_score(query, n), fuzz.token_set_ratio(query.lower(), n.lower())),
            reverse=True,
        )
        product = db.get_product(ranked[0])
        if product:
            return {**product, 'match_type': 'keyword', 'confidence': 50}
    
    return None
