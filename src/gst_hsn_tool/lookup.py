"""
Product lookup module - searches Google for HSN code by product name.
"""

import json
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


def lookup_product_by_name(
    product_name: str,
    auto_store: bool = True,
    search_if_not_found: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Lookup a product by name in database.
    If not found and search_if_not_found=True, search Google and store result.
    
    Returns:
        Dict with: name, category, hsn_4digit, hsn_8digit, source_url, match_type, is_new
        Or None if not found and search_if_not_found=False
    """
    
    # First, check for similar products in DB
    similar = similarity.find_similar_in_db(product_name.strip())
    
    if similar:
        # Found in DB
        return {
            **similar,
            'is_new': False
        }
    
    # Not in DB, try Google search if enabled
    if search_if_not_found:
        result = _search_google_for_hsn(product_name.strip())
        
        if result and auto_store:
            # Store in DB
            db.insert_product(
                name=product_name.strip(),
                category=result.get('category'),
                hsn_4digit=result.get('hsn_4digit'),
                hsn_8digit=result.get('hsn_8digit'),
                source_url=result.get('source_url')
            )
        
        if result:
            result['is_new'] = True
            result['match_type'] = 'google_search'
        
        return result
    
    return None


def _search_google_for_hsn(product_name: str, num_results: int = 5) -> Optional[Dict[str, Any]]:
    """
    Search Google for product HSN code.
    Returns best result found with extracted HSN and category.
    """
    
    query = f"{product_name} 8 digit hsn code india"
    
    try:
        urls = _get_google_search_urls(query, num_results=num_results)
    except Exception as e:
        return None
    
    # Try to fetch and extract from first few URLs
    for url in urls[:3]:
        try:
            html_text = _fetch_url(url)
            if not html_text:
                continue
            
            # Extract HSN and category
            extraction = extract_hsn_from_google_result(html_text, product_name)
            
            # If we found at least category or HSN, return it
            if extraction['category'] or extraction['hsn_4digit'] or extraction['hsn_8digit']:
                extraction['source_url'] = url
                return extraction
            
            # Small delay to avoid throttling
            time.sleep(0.5)
        
        except Exception as e:
            continue
    
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
    
    # Multiple regex patterns to handle different Google HTML formats
    patterns = [
        r'/url\?q=([^&]+)',  # Standard format
        r'/url\?url=([^&]+)',  # Alternative format
        r'href="(/url\?[^"]*)"',  # href attribute
        r'data-url="([^"]*)"',  # data attribute
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html_text)
        for match in matches:
            # Decode URL-encoded string
            try:
                decoded_url = urllib.parse.unquote(match)
                # Filter out Google's own URLs
                if decoded_url.startswith('http') and 'google' not in decoded_url:
                    urls.append(decoded_url)
            except:
                pass
    
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
