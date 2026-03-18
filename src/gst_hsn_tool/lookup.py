"""
Product lookup module - searches Google for HSN code by product name.
"""

import json
import html
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Optional, Dict, Any
from pathlib import Path

from .hsn_extractor import extract_hsn_from_google_result, validate_hsn_code
from . import db
from . import similarity
from .loader import load_hsn_master
from .utils import normalize_hsn_digits, normalize_text


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

GOOGLE_SEARCH_URL = "https://www.google.com/search"
DUCKDUCKGO_SEARCH_URL = "https://html.duckduckgo.com/html/"
SEARCH_FETCH_WORKERS = 6
SEARCH_URLS_PER_PRODUCT = 8

NOISE_TOKENS = {
    "rs",
    "mrp",
    "offer",
    "small",
    "big",
    "pack",
    "combo",
    "free",
    "pcs",
    "pc",
    "gm",
    "kg",
    "ml",
    "ltr",
}


MASTER_CANDIDATE_PATHS = [
    Path("data") / "hsn_master_from_gst.csv",
]


def _normalize_product_query(product_name: str) -> str:
    """Clean noisy commercial tokens to improve Google query relevance."""
    raw = product_name.lower().replace("/", " ").replace("-", " ")
    parts = [p.strip() for p in raw.split() if p.strip()]
    cleaned = []
    for part in parts:
        if part.isdigit():
            continue
        if part in NOISE_TOKENS:
            continue
        if re.fullmatch(r"rs\.?\d+", part):
            continue
        cleaned.append(part)
    return " ".join(cleaned).strip() or product_name.strip()


def _token_set(value: str) -> set[str]:
    text = normalize_text(value)
    if not text:
        return set()
    return {p for p in text.split() if len(p) > 2 and p not in NOISE_TOKENS and not p.isdigit()}


def _token_variants(tokens: set[str]) -> set[str]:
    """Expand tokens with simple singular/plural variants for better master matching."""
    out = set(tokens)
    for t in list(tokens):
        if t.endswith("s") and len(t) > 4:
            out.add(t[:-1])
        else:
            out.add(f"{t}s")
    return out


def _resolve_master_path() -> Optional[Path]:
    # Preferred static master path.
    for path in MASTER_CANDIDATE_PATHS:
        if path.exists() and path.is_file():
            return path
    return None


@lru_cache(maxsize=4)
def _load_master_rows_cached(path_str: str, mtime: float) -> list[dict]:
    del mtime  # part of cache key only
    path = Path(path_str)
    try:
        rows = load_hsn_master(path)
        for row in rows:
            desc_tokens = _token_set(row.get("description", ""))
            alias_tokens: set[str] = set()
            aliases_norm = row.get("aliases_norm", [])
            if isinstance(aliases_norm, list):
                for item in aliases_norm:
                    alias_tokens |= _token_set(str(item))
            row["_lookup_tokens"] = _token_variants(desc_tokens | alias_tokens)
        return rows
    except Exception:
        return []


@lru_cache(maxsize=4)
def _build_master_inverted_index(path_str: str, mtime: float) -> dict[str, list[int]]:
    rows = _load_master_rows_cached(path_str, mtime)
    index: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        for tok in row.get("_lookup_tokens", set()):
            index.setdefault(tok, []).append(i)
    return index


def _master_text_fallback(product_name: str) -> Optional[Dict[str, Any]]:
    """Try mapping product text directly to GST master descriptions when Google misses."""
    master_path = _resolve_master_path()
    if not master_path:
        return None

    try:
        stat = master_path.stat()
    except Exception:
        return None

    rows = _load_master_rows_cached(str(master_path), stat.st_mtime)
    if not rows:
        return None

    query_tokens = _token_variants(_token_set(product_name))
    if not query_tokens:
        return None

    index = _build_master_inverted_index(str(master_path), stat.st_mtime)
    candidate_idxs: set[int] = set()
    for tok in query_tokens:
        for idx in index.get(tok, []):
            candidate_idxs.add(idx)

    if not candidate_idxs:
        return None

    best_row = None
    best_score = 0.0
    for idx in candidate_idxs:
        row = rows[idx]
        rt = row.get("_lookup_tokens", set())
        if not rt:
            continue
        overlap = len(query_tokens & rt)
        score = overlap / max(1, len(query_tokens))
        if score > best_score:
            best_score = score
            best_row = row

    # Require minimum confidence to avoid noisy guesses.
    if not best_row or best_score < 0.25:
        return None

    hsn8 = normalize_hsn_digits(best_row.get("hsn8", ""))
    if len(hsn8) != 8:
        return None

    return {
        "category": best_row.get("category") or "GST Master",
        "hsn_4digit": hsn8[:4],
        "hsn_8digit": hsn8,
        "source_url": None,
    }


def _extract_hsn6_from_text(text: str) -> str:
    # Prefer explicit HSN-like context.
    lower = text.lower()
    for pattern in [r'hsn\s*(?:code)?\s*[:\-]?\s*(\d{6})\b', r'\b(\d{6})\s*(?:hsn|tariff)\b']:
        match = re.search(pattern, lower)
        if match:
            return normalize_hsn_digits(match.group(1))
    return ""


def _best_hsn8_from_master(product_name: str, hsn4: str, hsn6: str = "") -> str:
    master_path = _resolve_master_path()
    if not master_path:
        return ""

    try:
        stat = master_path.stat()
    except Exception:
        return ""

    rows = _load_master_rows_cached(str(master_path), stat.st_mtime)
    if not rows:
        return ""

    prefix6 = normalize_hsn_digits(hsn6)
    prefix4 = normalize_hsn_digits(hsn4)
    if len(prefix6) != 6:
        prefix6 = ""
    if len(prefix4) != 4:
        prefix4 = ""
    if not prefix6 and not prefix4:
        return ""

    product_tokens = _token_set(product_name)

    candidates = []
    for row in rows:
        code = row.get("hsn8", "")
        if prefix6 and not code.startswith(prefix6):
            continue
        if not prefix6 and prefix4 and not code.startswith(prefix4):
            continue
        candidates.append(row)

    if not candidates:
        return ""

    if not product_tokens:
        return candidates[0].get("hsn8", "")

    def score(row: dict) -> tuple[int, int]:
        desc_tokens = _token_set(row.get("description", ""))
        alias_tokens = _token_set(" ".join(row.get("aliases_norm", []) if isinstance(row.get("aliases_norm"), list) else []))
        all_tokens = desc_tokens | alias_tokens
        overlap = len(product_tokens & all_tokens)
        # Use overlap first, then prefer longer specific match prefix (6-digit constrained better than 4-digit).
        specificity = 2 if prefix6 else 1
        return (overlap, specificity)

    best = max(candidates, key=score)
    return best.get("hsn8", "")


def _enrich_result_with_master(product_name: str, result: dict) -> dict:
    if not result:
        return result

    if result.get("hsn_8digit"):
        return result

    hsn4 = normalize_hsn_digits(result.get("hsn_4digit", ""))
    hsn6 = normalize_hsn_digits(result.get("hsn_6digit", ""))

    if len(hsn6) != 6 and len(hsn4) == 4:
        # Derive a likely 6-digit prefix from text when possible is handled earlier,
        # otherwise we match by 4-digit bucket.
        hsn6 = ""

    if len(hsn4) != 4 and len(hsn6) == 6:
        hsn4 = hsn6[:4]

    best_hsn8 = _best_hsn8_from_master(product_name, hsn4=hsn4, hsn6=hsn6)
    if best_hsn8 and len(best_hsn8) == 8:
        result["hsn_8digit"] = best_hsn8
        result["hsn_4digit"] = best_hsn8[:4]
    return result


def lookup_product_by_name(
    product_name: str,
    auto_store: bool = True,
    search_if_not_found: bool = True,
    force_google_search: bool = False,
    fast_local_first: bool = False,
    similar_threshold: int = 80,
) -> Optional[Dict[str, Any]]:
    """
    Lookup a product by name in database.
    If not found and search_if_not_found=True, search Google and store result.
    
    Returns:
        Dict with: name, category, hsn_4digit, hsn_8digit, source_url, match_type, is_new
        Or None if not found and search_if_not_found=False
    """
    
    cleaned_name = product_name.strip()

    if fast_local_first:
        local_result = _fallback_hsn_guess(cleaned_name)
        if not local_result:
            local_result = _master_text_fallback(cleaned_name)
        if local_result:
            local_result = _enrich_result_with_master(cleaned_name, local_result)
            if auto_store and local_result.get("hsn_4digit"):
                inserted = db.insert_product(
                    name=cleaned_name,
                    category=local_result.get("category"),
                    hsn_4digit=local_result.get("hsn_4digit"),
                    hsn_8digit=local_result.get("hsn_8digit"),
                    source_url=local_result.get("source_url"),
                )
                if not inserted:
                    db.update_product(
                        name=cleaned_name,
                        category=local_result.get("category"),
                        hsn_4digit=local_result.get("hsn_4digit"),
                        hsn_8digit=local_result.get("hsn_8digit"),
                        source_url=local_result.get("source_url"),
                    )
            local_result["input_name"] = cleaned_name
            local_result["matched_name"] = cleaned_name
            local_result["name"] = cleaned_name
            local_result["searched_on_google"] = False
            local_result["is_new"] = True
            local_result["match_type"] = "fast_local"
            return local_result

    # First, check for similar products in DB
    similar = None if force_google_search else similarity.find_similar_in_db(cleaned_name, threshold=similar_threshold)
    
    if similar:
        # Backfill missing hsn_8digit from master when possible.
        enriched_similar = _enrich_result_with_master(cleaned_name, dict(similar))
        if auto_store and enriched_similar.get("hsn_8digit") and not similar.get("hsn_8digit"):
            db.update_product(
                name=similar.get("name", cleaned_name),
                category=enriched_similar.get("category"),
                hsn_4digit=enriched_similar.get("hsn_4digit"),
                hsn_8digit=enriched_similar.get("hsn_8digit"),
                source_url=enriched_similar.get("source_url"),
            )
        # Found in DB
        return {
            **enriched_similar,
            'input_name': cleaned_name,
            'matched_name': similar.get('name'),
            'name': cleaned_name,
            'is_new': False
        }
    
    # Not in DB, try Google search if enabled
    if search_if_not_found:
        result = _search_google_for_hsn(cleaned_name)

        if result:
            result = _enrich_result_with_master(cleaned_name, result)
            if auto_store and result.get('hsn_4digit'):
                inserted = db.insert_product(
                    name=cleaned_name,
                    category=result.get('category'),
                    hsn_4digit=result.get('hsn_4digit'),
                    hsn_8digit=result.get('hsn_8digit'),
                    source_url=result.get('source_url')
                )
                if not inserted:
                    db.update_product(
                        name=cleaned_name,
                        category=result.get('category'),
                        hsn_4digit=result.get('hsn_4digit'),
                        hsn_8digit=result.get('hsn_8digit'),
                        source_url=result.get('source_url')
                    )
            result['input_name'] = cleaned_name
            result['matched_name'] = cleaned_name
            result['name'] = cleaned_name
            result['searched_on_google'] = True
            result['is_new'] = True
            result['match_type'] = 'google_search'
        
        return result
    
    return None


def _search_google_for_hsn(product_name: str, num_results: int = 5) -> Optional[Dict[str, Any]]:
    """
    Search Google for product HSN code.
    Returns best result found with extracted HSN and category.
    """
    
    normalized_name = _normalize_product_query(product_name)
    query_candidates = [
        f"{normalized_name} hsn code",
        f"{normalized_name} gst hsn code india",
        f"{normalized_name} 8 digit hsn",
    ]

    urls: list[str] = []
    for query in query_candidates:
        discovered = list(_get_google_search_urls_cached(query, num_results))
        for link in discovered:
            if link not in urls:
                urls.append(link)
        if len(urls) >= num_results:
            break

    # Secondary online source: DuckDuckGo fallback discovery.
    if len(urls) < num_results:
        for query in query_candidates:
            ddg_links = list(_get_duckduckgo_search_urls_cached(query, num_results))
            for link in ddg_links:
                if link not in urls:
                    urls.append(link)
            if len(urls) >= num_results:
                break
    
    if not urls:
        # No URLs found, use fallback
        fb = _fallback_hsn_guess(product_name)
        if fb:
            return fb
        return _master_text_fallback(product_name)
    
    # Fetch and extract candidates concurrently for speed.
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    candidates = urls[:SEARCH_URLS_PER_PRODUCT]
    with ThreadPoolExecutor(max_workers=SEARCH_FETCH_WORKERS) as executor:
        futures = [executor.submit(_fetch_extract_candidate, url, product_name) for url in candidates]
        for future in as_completed(futures):
            extraction = future.result()
            if not extraction:
                continue

            score = 0
            if extraction.get("hsn_4digit"):
                score += 1
            if extraction.get("hsn_6digit"):
                score += 1
            if extraction.get("hsn_8digit"):
                score += 2

            if score > best_score:
                best = extraction
                best_score = score

            # Early exit quality threshold.
            if score >= 3:
                break

    if best:
        return best
    
    # If nothing found, use fallback
    fb = _fallback_hsn_guess(product_name)
    if fb:
        return fb
    return _master_text_fallback(product_name)


def _fetch_extract_candidate(url: str, product_name: str) -> Optional[Dict[str, Any]]:
    try:
        html_text = _fetch_url(url)
        if not html_text:
            return None

        extraction = extract_hsn_from_google_result(html_text, product_name)
        if not extraction.get("hsn_6digit"):
            hsn6 = _extract_hsn6_from_text(html_text)
            if hsn6:
                extraction["hsn_6digit"] = hsn6

        if extraction.get('hsn_4digit') or extraction.get('hsn_8digit'):
            extraction['source_url'] = url
            return extraction
        return None
    except Exception:
        return None


def _fallback_hsn_guess(product_name: str) -> Optional[Dict[str, Any]]:
    """
    Fallback method to guess HSN category based on product name keywords.
    """
    tokens = _token_variants(_token_set(product_name))

    # Scored fallback rules (category, hsn4, keywords)
    rules = [
        ("Food & Beverages", "1905", {"biscuit", "cookie", "cookies", "cake", "cakes", "rusk", "wafer", "wafers", "muffin", "muffins", "cracker", "crackers", "plum", "milano", "digestive", "hobnobs", "marie"}),
        ("Food & Beverages", "1704", {"choco", "chocolate", "candy", "candies", "eclair", "eclairs", "toffee", "mint", "mints", "bonbon", "bar", "snickers", "solano"}),
        ("Food & Beverages", "2106", {"murukku", "sev", "pakkavada", "mixture", "chips", "popcorn", "frymes", "kuzhal", "chakli", "jeera"}),
        ("Food & Beverages", "2202", {"tea", "drink", "juice", "squash", "beverage", "7up", "soup", "knorr"}),
        ("Agricultural Products", "1006", {"rice", "undai", "ariurundai"}),
        ("Agricultural Products", "1701", {"sugar"}),
        ("Animal Products", "0407", {"egg", "eggs", "poultry", "hen"}),
        ("Agricultural Products", "0801", {"coconut"}),
        ("Stationery", "3215", {"ink"}),
        ("Stationery", "9017", {"scale", "ruler"}),
        ("Printed Material", "4911", {"sticker", "chart"}),
        ("Paper Articles", "4821", {"tag"}),
        ("Paper Articles", "4817", {"envelop", "envelope"}),
        ("Stationery", "9609", {"chalk"}),
        ("Household Articles", "3924", {"dust", "dustpan", "tray", "cover", "soap", "box", "clean", "scrub"}),
        ("Household Articles", "9603", {"broom", "wiper", "sweeper", "pazhakazthi", "kazthi"}),
        ("Floor Coverings", "5705", {"mat"}),
        ("Chemical Products", "3506", {"mseal", "m-seal", "epoxy", "adhesive", "compound"}),
        ("Sports Goods", "9504", {"carrom", "striker"}),
        ("Accessories", "9615", {"hair", "band"}),
        ("Accessories", "7117", {"ring", "stud", "pearl", "button", "buttons"}),
        ("Electronics", "8471", {"laptop", "computer", "phone", "mobile", "iphone", "samsung"}),
        ("Electronics", "8528", {"tv", "monitor", "display", "screen"}),
        ("Textiles", "5208", {"cotton", "fabric", "cloth", "textile", "shirt", "pant", "dress"}),
        ("Cosmetics", "3304", {"shampoo", "cosmetic", "beauty", "lotion", "cream"}),
    ]

    best = None
    best_score = 0
    for category, hsn4, kws in rules:
        score = len(tokens & kws)
        if score > best_score:
            best = (category, hsn4)
            best_score = score

    if best:
        category, hsn4 = best
        return {
            'category': category,
            'hsn_4digit': hsn4,
            'hsn_8digit': None,
            'source_url': None
        }

    # Last fallback: try direct semantic match against GST master descriptions.
    master_guess = _master_text_fallback(product_name)
    if master_guess:
        return master_guess
    
    # Unknown products should remain not_found instead of polluting DB with 9999.
    return None


def _get_google_search_urls(query: str, num_results: int = 5) -> list:
    """
    Get search result URLs from Google.
    """
    params = {
        'q': query,
        'num': min(num_results, 10),
        'pws': '0',  # Disable personalization
        'gbv': '1',  # Regular search
        'gl': 'in',  # India region
    }
    
    url = f"{GOOGLE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            html_text = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return []
    
    # Extract result URLs from Google HTML
    urls = _extract_urls_from_google_html(html_text)
    return urls[:num_results]


@lru_cache(maxsize=2048)
def _get_google_search_urls_cached(query: str, num_results: int = 5) -> tuple[str, ...]:
    return tuple(_get_google_search_urls(query, num_results))


def _get_duckduckgo_search_urls(query: str, num_results: int = 5) -> list:
    params = {
        "q": query,
        "kl": "in-en",
    }
    url = f"{DUCKDUCKGO_SEARCH_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    urls = _extract_duckduckgo_result_links(html_text)
    return urls[:num_results]


@lru_cache(maxsize=2048)
def _get_duckduckgo_search_urls_cached(query: str, num_results: int = 5) -> tuple[str, ...]:
    return tuple(_get_duckduckgo_search_urls(query, num_results))


def _extract_urls_from_google_html(html_text: str) -> list:
    """
    Extract result URLs from Google search result HTML.
    """
    urls = []
    
    patterns = [
        r'href=["\']/url\?(?:q|url)=([^"\'&]+)',
        r'href=["\']https?://(?:www\.)?google\.[^/]+/url\?(?:q|url)=([^"\'&]+)',
        r'data-url=["\'](https?://[^"\']+)["\']',
        r'href=["\'](https?://[^"\']+)["\']',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html_text, flags=re.IGNORECASE)
        for match in matches:
            try:
                decoded_url = html.unescape(urllib.parse.unquote(match))
                if not decoded_url.startswith(("http://", "https://")):
                    continue
                domain = urllib.parse.urlparse(decoded_url).netloc.lower()
                if "google." in domain:
                    continue
                urls.append(decoded_url)
            except Exception:
                continue
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


def _extract_duckduckgo_result_links(html_text: str) -> list:
    links = []
    seen = set()

    # DuckDuckGo redirect links with uddg payload.
    for match in re.findall(r'href=["\']https?://duckduckgo\.com/l/\?[^"\']*uddg=([^"\'&]+)', html_text, flags=re.IGNORECASE):
        try:
            decoded = urllib.parse.unquote(match)
            if decoded.startswith(("http://", "https://")) and decoded not in seen:
                seen.add(decoded)
                links.append(decoded)
        except Exception:
            continue

    # Direct result links in result__a anchors.
    for match in re.findall(r'class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\']', html_text, flags=re.IGNORECASE):
        try:
            decoded = html.unescape(match)
            if decoded.startswith(("http://", "https://")) and "duckduckgo.com" not in decoded and decoded not in seen:
                seen.add(decoded)
                links.append(decoded)
        except Exception:
            continue

    return links


def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch URL and return HTML text.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_text = resp.read().decode('utf-8', errors='ignore')
            return html_text
    except Exception as e:
        return None


def bulk_lookup_products(
    product_names: list,
    auto_store: bool = True,
    progress_callback=None
) -> list:
    """
    Lookup multiple products.
    
    Args:
        product_names: List of product name strings
        auto_store: Whether to store results in DB
        progress_callback: Optional function(current, total) to track progress
    
    Returns:
        List of result dicts
    """
    results = []
    
    for i, name in enumerate(product_names):
        if progress_callback:
            progress_callback(i + 1, len(product_names))
        
        result = lookup_product_by_name(
            name,
            auto_store=auto_store,
            search_if_not_found=True
        )
        
        if result:
            results.append(result)
        else:
            results.append({
                'name': name,
                'category': None,
                'hsn_4digit': None,
                'hsn_8digit': None,
                'source_url': None,
                'is_new': False,
                'match_type': 'not_found'
            })
        
        # Small delay between lookups to avoid throttling
        time.sleep(0.3)
    
    return results
