"""Similarity matching for product names using fuzzy matching and keyword matching."""

from functools import lru_cache
from typing import List, Dict, Optional, Tuple
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
    "kerala",
    "india",
    "indian",
    "special",
    "spl",
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


def _minimum_overlap(query_token_count: int) -> int:
    if query_token_count <= 1:
        return 1
    if query_token_count == 2:
        return 2
    return 2


def _overlap_count(query: str, candidate: str) -> int:
    q = _tokens(query)
    c = _tokens(candidate)
    return len(q & c)


@lru_cache(maxsize=8)
def _all_products_cached(total_count: int) -> tuple[tuple[str, Dict], ...]:
    del total_count  # only used as cache key invalidator
    products = db.get_all_products(limit=20000)
    return tuple((p["name"], p) for p in products if p.get("name"))


def _get_all_products() -> tuple[tuple[str, Dict], ...]:
    return _all_products_cached(db.get_total_count())


def fuzzy_match(query: str, candidates: List[str], threshold: int = 80) -> List[tuple]:
    """
    Perform fuzzy matching between query and candidates.
    Returns list of (name, score) tuples sorted by score (descending).
    """
    results = []
    q_tokens = _tokens(query)
    min_overlap = _minimum_overlap(len(q_tokens))
    for candidate in candidates:
        score = fuzz.token_set_ratio(query.lower(), candidate.lower())
        overlap = _overlap_count(query, candidate)
        # Guard against false positives caused by common commercial tokens.
        if score >= threshold and overlap >= min_overlap:
            results.append((candidate, score))
    
    return sorted(results, key=lambda x: x[1], reverse=True)


def keyword_match(query: str, candidates: List[str]) -> List[str]:
    """
    Match based on keyword overlap.
    Returns list of candidate names that share keywords with query.
    """
    query_words = _tokens(query)
    min_overlap = _minimum_overlap(len(query_words))
    results = []
    
    for candidate in candidates:
        candidate_words = _tokens(candidate)
        overlap = query_words & candidate_words
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
    
    # Get all products for fuzzy matching from cache (fast path for bulk lookups).
    products = _get_all_products()
    all_names = [name for name, _ in products]
    product_by_name = {name: row for name, row in products}
    
    # Try fuzzy match
    fuzzy_results = fuzzy_match(query, all_names, threshold)
    if fuzzy_results:
        best_match_name = fuzzy_results[0][0]
        best_match_score = fuzzy_results[0][1]
        product = product_by_name.get(best_match_name)
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
        product = product_by_name.get(ranked[0])
        if product:
            return {**product, 'match_type': 'keyword', 'confidence': 50}
    
    return None
