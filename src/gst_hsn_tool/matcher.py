from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple

from gst_hsn_tool.config import TOP_K_CANDIDATES
from gst_hsn_tool.models import MatchCandidate
from gst_hsn_tool.utils import normalize_text


TOKEN_FIXES = {
    "cabdury": "cadbury",
    "cadburry": "cadbury",
    "cadbary": "cadbury",
    "dairyy": "dairy",
    "diary": "dairy",
    "mik": "milk",
    "mlk": "milk",
    "choco": "chocolate",
    "vanila": "vanilla",
    "clor": "color",
    "clr": "color",
    "envlop": "envelope",
    "envlope": "envelope",
    "pkt": "pack",
    "pcs": "pieces",
}

PHRASE_FIXES = {
    "c diary milk": "cadbury dairy milk chocolate",
    "cd milk": "cadbury dairy milk chocolate",
    "cad dairy milk": "cadbury dairy milk chocolate",
}

# Brand tokens are treated as optional/noisy because HSN descriptions are usually generic.
BRAND_TOKENS = {
    "cadbury",
    "camlin",
    "kores",
    "sunfeast",
    "bingo",
    "dathri",
    "dheedhi",
    "maruthi",
}

STOPWORDS = {
    "rs",
    "in",
    "with",
    "for",
    "and",
    "small",
    "big",
    "pieces",
    "piece",
    "pack",
    "set",
    "black",
    "white",
    "pink",
    "brown",
}

# Useful chapter hints for common retail terms.
KEYWORD_HSN4_HINTS = {
    "shampoo": "3305",
    "ink": "3215",
    "chalk": "9609",
    "envelope": "4817",
    "soap": "3401",
    "rice": "1006",
    "sugar": "1701",
    "egg": "0407",
    "coconut": "0801",
    "chocolate": "1806",
    "biscuit": "1905",
    "cover": "3924",
    "sticker": "4911",
    "mat": "5705",
    "tray": "3924",
    "dustpan": "3924",
    "dust": "3924",
    "pan": "3924",
    "plastic": "3924",
    "hairband": "9615",
    "ring": "7117",
    "stud": "7117",
}


def _base_score(match_type: str, fuzzy_score: float = 0) -> float:
    if match_type == "exact_description":
        return 92
    if match_type == "exact_alias":
        return 88
    if match_type == "hsn_prefix_expansion":
        return 78
    if match_type == "fuzzy_description":
        return max(45, min(86, fuzzy_score * 0.9))
    return 0


def _route_status(score: float) -> str:
    if score >= 90:
        return "auto_approved"
    if score >= 75:
        return "supervisor_review"
    return "manual_review"


def _row_to_candidate(
    row: dict,
    match_type: str,
    score: float,
    reason: str,
) -> MatchCandidate:
    return MatchCandidate(
        hsn8=str(row["hsn8"]),
        description=str(row["description"]),
        category=str(row.get("category", "")),
        rate=str(row.get("rate", "")),
        match_type=match_type,
        score=round(score, 2),
        reason=reason,
    )


def _fuzzy_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() * 100


def _normalize_token(token: str) -> str:
    token = TOKEN_FIXES.get(token, token)
    token = re.sub(r"\d+", "", token)

    if token.endswith("s") and len(token) > 4:
        token = token[:-1]

    unit_suffixes = ["ml", "gm", "kg", "cm"]
    for suffix in unit_suffixes:
        if token.endswith(suffix) and len(token) > len(suffix):
            token = token[: -len(suffix)]

    return token.strip()


def _prepare_query_text(text: str) -> str:
    normalized = normalize_text(text)
    if normalized in PHRASE_FIXES:
        normalized = PHRASE_FIXES[normalized]

    tokens = []
    for raw_token in normalized.split():
        token = _normalize_token(raw_token)
        if not token:
            continue
        if token in BRAND_TOKENS:
            continue
        if token in STOPWORDS:
            continue
        tokens.append(token)

    # Common FMCG phrasing where brand-heavy dairy-milk text usually means chocolate products.
    if "dairy" in tokens and "milk" in tokens:
        tokens.append("chocolate")

    return " ".join(tokens)


def _tokenize(text: str) -> Set[str]:
    return {t for t in text.split() if t}


class HsnMatcher:
    def __init__(self, hsn_rows: List[dict]) -> None:
        self.hsn_rows = hsn_rows
        self.desc_index: Dict[str, List[dict]] = {}
        self.alias_index: Dict[str, List[dict]] = {}
        self.hsn4_index: Dict[str, List[dict]] = {}
        self.hsn6_index: Dict[str, List[dict]] = {}
        self.token_index: Dict[str, Set[int]] = {}
        self.row_tokens: Dict[int, Set[str]] = {}
        self._build_indexes()

    def _build_indexes(self) -> None:
        for idx, row in enumerate(self.hsn_rows):
            desc_norm = _prepare_query_text(row.get("description_norm", ""))
            self.desc_index.setdefault(desc_norm, []).append(row)

            for alias in row.get("aliases_norm", []):
                alias_norm = _prepare_query_text(alias)
                self.alias_index.setdefault(alias_norm, []).append(row)

            self.hsn4_index.setdefault(row.get("hsn4", ""), []).append(row)
            self.hsn6_index.setdefault(row.get("hsn6", ""), []).append(row)

            tokens = _tokenize(desc_norm)
            self.row_tokens[idx] = tokens
            for token in tokens:
                self.token_index.setdefault(token, set()).add(idx)

    def _exact_candidates(self, desc_norm: str, category_norm: str) -> List[MatchCandidate]:
        if len(desc_norm.split()) < 2:
            return []

        out: List[MatchCandidate] = []
        for row in self.desc_index.get(desc_norm, []):
            score = _base_score("exact_description")
            if category_norm and category_norm == row.get("category_norm", ""):
                score += 5
            out.append(_row_to_candidate(row, "exact_description", score, "Exact description match"))

        for row in self.alias_index.get(desc_norm, []):
            score = _base_score("exact_alias")
            if category_norm and category_norm == row.get("category_norm", ""):
                score += 5
            out.append(_row_to_candidate(row, "exact_alias", score, "Alias match"))
        return out

    def _prefix_candidates(self, client_hsn_norm: str) -> List[MatchCandidate]:
        if len(client_hsn_norm) == 4:
            matched = self.hsn4_index.get(client_hsn_norm, [])
        elif len(client_hsn_norm) == 6:
            matched = self.hsn6_index.get(client_hsn_norm, [])
        else:
            matched = []

        out: List[MatchCandidate] = []
        for row in matched[:TOP_K_CANDIDATES]:
            out.append(
                _row_to_candidate(
                    row,
                    "hsn_prefix_expansion",
                    _base_score("hsn_prefix_expansion"),
                    f"Expanded {len(client_hsn_norm)}-digit HSN to 8-digit candidates",
                )
            )
        return out

    def _keyword_hint_candidates(self, query_text: str, query_tokens: Set[str]) -> List[MatchCandidate]:
        out: List[MatchCandidate] = []
        for token in query_tokens:
            hsn4 = KEYWORD_HSN4_HINTS.get(token)
            if not hsn4:
                continue

            matched = self.hsn4_index.get(hsn4, [])
            if not matched:
                continue

            ranked = []
            for row in matched:
                row_desc = _prepare_query_text(row.get("description_norm", ""))
                sim = _fuzzy_similarity(query_text, row_desc)
                ranked.append((sim, row))

            ranked.sort(key=lambda x: x[0], reverse=True)
            for sim, row in ranked[:TOP_K_CANDIDATES]:
                score = max(68.0, min(82.0, 62.0 + (sim * 0.25)))
                out.append(
                    _row_to_candidate(
                        row,
                        "keyword_hint",
                        score,
                        f"Keyword hint from token '{token}' ({round(sim, 1)} similarity)",
                    )
                )
        return out

    def _shortlist(self, query_tokens: Set[str]) -> List[int]:
        if not query_tokens:
            return list(range(len(self.hsn_rows)))

        idx_set: Set[int] = set()
        for token in query_tokens:
            idx_set.update(self.token_index.get(token, set()))

        if not idx_set:
            return list(range(len(self.hsn_rows)))
        return list(idx_set)

    def _hint_boost(self, query_tokens: Set[str], row: dict) -> float:
        row_hsn4 = row.get("hsn4", "")
        for token in query_tokens:
            hint = KEYWORD_HSN4_HINTS.get(token)
            if hint and row_hsn4 == hint:
                return 8.0
        return 0.0

    def _score_row(self, query_text: str, query_tokens: Set[str], idx: int, category_norm: str) -> Tuple[float, float]:
        row = self.hsn_rows[idx]
        row_desc = _prepare_query_text(row.get("description_norm", ""))
        seq = _fuzzy_similarity(query_text, row_desc)

        row_tokens = self.row_tokens.get(idx, set())
        if not query_tokens or not row_tokens:
            overlap = 0.0
        else:
            overlap = 100.0 * len(query_tokens.intersection(row_tokens)) / max(1, len(query_tokens.union(row_tokens)))

        weighted = (0.55 * seq) + (0.45 * overlap)
        score = _base_score("fuzzy_description", weighted)
        score += self._hint_boost(query_tokens, row)
        if category_norm and category_norm == row.get("category_norm", ""):
            score += 5
        return weighted, score

    def _fuzzy_candidates(self, desc_norm: str, category_norm: str) -> List[MatchCandidate]:
        if not desc_norm:
            return []

        query_text = _prepare_query_text(desc_norm)
        query_tokens = _tokenize(query_text)
        shortlist = self._shortlist(query_tokens)

        scored_rows = []
        for idx in shortlist:
            similarity, score = self._score_row(query_text, query_tokens, idx, category_norm)
            if similarity < 35:
                continue
            row = self.hsn_rows[idx]
            scored_rows.append((similarity, score, row))

        scored_rows.sort(key=lambda item: (item[1], item[0]), reverse=True)
        out: List[MatchCandidate] = []
        for similarity, score, row in scored_rows[:TOP_K_CANDIDATES]:
            out.append(
                _row_to_candidate(
                    row,
                    "fuzzy_description",
                    score,
                    f"Fuzzy+token match ({round(similarity, 1)} similarity)",
                )
            )
        return out

    def resolve(self, description_norm: str, category_norm: str, client_hsn_norm: str) -> List[MatchCandidate]:
        normalized_query = _prepare_query_text(description_norm)
        query_tokens = _tokenize(normalized_query)

        candidates: List[MatchCandidate] = []
        candidates.extend(self._prefix_candidates(client_hsn_norm))

        if not normalized_query.strip():
            dedup = {candidate.hsn8: candidate for candidate in candidates}
            ordered = sorted(dedup.values(), key=lambda c: c.score, reverse=True)
            return ordered[:TOP_K_CANDIDATES]

        candidates.extend(self._exact_candidates(normalized_query, category_norm))
        candidates.extend(self._keyword_hint_candidates(normalized_query, query_tokens))
        candidates.extend(self._fuzzy_candidates(normalized_query, category_norm))

        dedup = {}
        for candidate in candidates:
            current = dedup.get(candidate.hsn8)
            if current is None or candidate.score > current.score:
                dedup[candidate.hsn8] = candidate

        ordered = sorted(dedup.values(), key=lambda c: c.score, reverse=True)
        return ordered[:TOP_K_CANDIDATES]


def resolve_row(
    description_norm: str,
    category_norm: str,
    client_hsn_norm: str,
    hsn_rows: List[dict],
) -> List[MatchCandidate]:
    matcher = HsnMatcher(hsn_rows)
    return matcher.resolve(description_norm, category_norm, client_hsn_norm)


def select_primary(candidates: List[MatchCandidate]) -> tuple[MatchCandidate | None, str]:
    if not candidates:
        return None, "No candidate found"

    top = candidates[0]
    reason = top.reason
    if len(candidates) > 1 and abs(top.score - candidates[1].score) < 5:
        top.score = min(top.score, 74)
        reason += "; Ambiguous candidates (small score gap)"

    top.score = max(0, min(100, top.score))
    return top, reason


def status_from_score(score: float) -> str:
    return _route_status(score)
