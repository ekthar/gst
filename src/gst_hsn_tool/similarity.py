"""
Similarity matching for product names using fuzzy matching and keyword matching.
"""

from typing import List, Dict, Optional
from fuzzywuzzy import fuzz
from . import db


def fuzzy_match(query: str, candidates: List[str], threshold: int = 80) -> List[tuple]:
    """
    Perform fuzzy matching between query and candidates.
    Returns list of (name, score) tuples sorted by score (descending).
    """
    results = []
    for candidate in candidates:
        score = fuzz.token_set_ratio(query.lower(), candidate.lower())
        if score >= threshold:
            results.append((candidate, score))
    
    return sorted(results, key=lambda x: x[1], reverse=True)


def keyword_match(query: str, candidates: List[str]) -> List[str]:
    """
    Match based on keyword overlap.
    Returns list of candidate names that share keywords with query.
    """
    query_words = set(query.lower().split())
    results = []
    
    for candidate in candidates:
        candidate_words = set(candidate.lower().split())
        if query_words & candidate_words:  # If there's any overlap
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
        # Return the first keyword match
        product = db.get_product(keyword_results[0])
        if product:
            return {**product, 'match_type': 'keyword', 'confidence': 50}
    
    return None
