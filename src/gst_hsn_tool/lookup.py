"""
Product lookup module - searches Google for HSN code by product name.
"""

import json
import html
import re
import time
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any
from pathlib import Path

from .hsn_extractor import extract_hsn_from_google_result, validate_hsn_code
from . import db
from . import similarity


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

GOOGLE_SEARCH_URL = "https://www.google.com/search"

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


def lookup_product_by_name(
    product_name: str,
    auto_store: bool = True,
    search_if_not_found: bool = True,
    force_google_search: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Lookup a product by name in database.
    If not found and search_if_not_found=True, search Google and store result.
    
    Returns:
        Dict with: name, category, hsn_4digit, hsn_8digit, source_url, match_type, is_new
        Or None if not found and search_if_not_found=False
    """
    
    cleaned_name = product_name.strip()

    # First, check for similar products in DB
    similar = None if force_google_search else similarity.find_similar_in_db(cleaned_name)
    
    if similar:
        # Found in DB
        return {
            **similar,
            'input_name': cleaned_name,
            'matched_name': similar.get('name'),
            'name': cleaned_name,
            'is_new': False
        }
    
    # Not in DB, try Google search if enabled
    if search_if_not_found:
        result = _search_google_for_hsn(cleaned_name)
        
        if result and auto_store and result.get('hsn_4digit'):
            # Store in DB
            db.insert_product(
                name=cleaned_name,
                category=result.get('category'),
                hsn_4digit=result.get('hsn_4digit'),
                hsn_8digit=result.get('hsn_8digit'),
                source_url=result.get('source_url')
            )
        
        if result:
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
        try:
            discovered = _get_google_search_urls(query, num_results=num_results)
        except Exception:
            discovered = []
        for link in discovered:
            if link not in urls:
                urls.append(link)
        if len(urls) >= num_results:
            break
    
    if not urls:
        # No URLs found, use fallback
        return _fallback_hsn_guess(product_name)
    
    # Try to fetch and extract from first few URLs
    for idx, url in enumerate(urls[:5]):
        try:
            html_text = _fetch_url(url)
            if not html_text:
                continue
            
            # Extract HSN and category
            extraction = extract_hsn_from_google_result(html_text, product_name)
            
            # Accept only if HSN digits were found to avoid unrelated category-only matches.
            if extraction.get('hsn_4digit') or extraction.get('hsn_8digit'):
                extraction['source_url'] = url
                return extraction
            
            # Small delay to avoid throttling
            time.sleep(0.3)
        
        except Exception as e:
            continue
    
    # If nothing found, use fallback
    return _fallback_hsn_guess(product_name)


def _fallback_hsn_guess(product_name: str) -> Optional[Dict[str, Any]]:
    """
    Fallback method to guess HSN category based on product name keywords.
    """
    keywords = product_name.lower().split()
    
    category_map = {
        # Stationery / office supplies
        ('ink',): ('Stationery', '3215'),
        ('scale', 'ruler'): ('Stationery', '9017'),
        ('sticker',): ('Printed Material', '4911'),
        ('tag',): ('Paper Articles', '4821'),
        ('chalk',): ('Stationery', '9609'),
        ('envelop', 'envelope'): ('Paper Articles', '4817'),

        # Household plastic/cleaning
        ('dust', 'dustpan'): ('Household Articles', '3924'),
        ('tray',): ('Household Articles', '3924'),
        ('cover',): ('Household Articles', '3924'),
        ('clean', 'cleaner', 'cleaning', 'scrub', 'scrubber'): ('Household Articles', '3924'),
        ('pazhakazthi', 'kazthi', 'broom', 'wiper', 'sweeper'): ('Household Articles', '9603'),
        ('mat',): ('Floor Coverings', '5705'),
        ('soap', 'box'): ('Household Articles', '3924'),

        # Food & beverages
        ('sunfeast', 'bingo', 'biscuit', 'cookie', 'cracker'): ('Food & Beverages', '1905'),
        ('cadbury', 'chocolate', 'candy', 'toffee', 'orbit'): ('Food & Beverages', '1704'),
        ('tea', 'coffee', 'beverage', 'drink', 'juice', '7up', 'lemon'): ('Food & Beverages', '2202'),
        ('rice',): ('Agricultural Products', '1006'),
        ('sugar',): ('Agricultural Products', '1701'),
        ('egg', 'eggs', 'poultry', 'hen'): ('Animal Products', '0407'),
        ('coconut',): ('Agricultural Products', '0801'),

        # Hardware / misc
        ('m-seal', 'mseal', 'epoxy', 'compound', 'adhesive'): ('Chemical Products', '3506'),
        ('carrom', 'striker'): ('Sports Goods', '9504'),
        ('hair', 'band'): ('Accessories', '9615'),
        ('ring', 'stud', 'pearl', 'button', 'buttons'): ('Accessories', '7117'),

        # Electronics
        ('laptop', 'computer', 'phone', 'mobile', 'iphone', 'samsung'): ('Electronics', '8471'),
        ('tv', 'monitor', 'display', 'screen'): ('Electronics', '8528'),

        # Textiles
        ('cotton', 'fabric', 'cloth', 'textile', 'shirt', 'pant', 'dress'): ('Textiles', '5208'),

        # Cosmetics / personal care
        ('shampoo', 'cosmetic', 'beauty', 'lotion', 'cream'): ('Cosmetics', '3304'),
    }
    
    # Try to match keywords
    for keywords_tuple, (category, hsn_4) in category_map.items():
        for keyword in keywords:
            if keyword in keywords_tuple:
                return {
                    'category': category,
                    'hsn_4digit': hsn_4,
                    'hsn_8digit': None,
                    'source_url': None
                }
    
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_text = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return []
    
    # Extract result URLs from Google HTML
    urls = _extract_urls_from_google_html(html_text)
    return urls[:num_results]


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
