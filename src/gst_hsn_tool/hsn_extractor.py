"""
HSN extraction from Google search results using regex and pattern matching.
"""

import re
from typing import Optional, Dict, Tuple


# Common product categories
CATEGORY_PATTERNS = {
    r'\b(electronic|computer|mobile|phone|tablet|laptop)\b': 'Electronics',
    r'\b(clothing|apparel|garment|fabric|textile|dress|shirt|pant)\b': 'Clothing & Textiles',
    r'\b(food|beverage|drink|coffee|tea|biscuit|chocolate|candy|confection)\b': 'Food & Beverages',
    r'\b(cosmetic|beauty|makeup|perfume|fragrance|cream|lotion|soap)\b': 'Cosmetics & Beauty',
    r'\b(furniture|sofa|chair|table|bed|wardrobe)\b': 'Furniture',
    r'\b(book|magazine|newspaper|publication|printing)\b': 'Books & Publications',
    r'\b(toy|game|doll|puzzle|plaything)\b': 'Toys & Games',
    r'\b(sport|equipment|athletic|fitness)\b': 'Sports & Equipment',
    r'\b(metal|steel|iron|aluminum|copper)\b': 'Metals & Minerals',
    r'\b(plastic|polymer|rubber|synthetic)\b': 'Plastics & Polymers',
    r'\b(chemical|pharmaceutical|medicine|drug)\b': 'Chemicals & Pharmaceuticals',
    r'\b(mineral|ore|stone|sand|gravel)\b': 'Minerals & Stones',
    r'\b(wood|timber|paper|pulp)\b': 'Wood & Paper',
    r'\b(animal|meat|fish|dairy|egg|poultry)\b': 'Animal Products',
    r'\b(vegetable|fruit|crop|grain|cereal|wheat|rice)\b': 'Agricultural Products',
}


def extract_hsn_from_text(text: str) -> Dict[str, Optional[str]]:
    """
    Extract HSN codes and category from Google search result text.
    
    Returns:
        Dict with keys: category, hsn_4digit, hsn_8digit
    """
    result = {
        'category': None,
        'hsn_4digit': None,
        'hsn_8digit': None
    }
    
    # Clean text
    text = text.lower()
    text_clean = re.sub(r'[^\w\s]', ' ', text)
    
    # Extract 8-digit HSN (more specific)
    hsn_8_matches = re.findall(r'\b(\d{8})\b', text)
    if hsn_8_matches:
        # Filter for plausible HSN codes (01000000 to 99999999)
        for match in hsn_8_matches:
            if match.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                result['hsn_8digit'] = match
                break
    
    # Extract 4-digit HSN (less specific, use as fallback)
    if not result['hsn_4digit']:
        # Look for patterns like "HSN 8543" or "HSN: 8543"
        hsn_4_patterns = [
            r'hsn\s+(?:code\s+)?(\d{4})',
            r'hsn\s*:\s*(\d{4})',
            r'(\d{4})\s+hsn',
        ]
        for pattern in hsn_4_patterns:
            matches = re.findall(pattern, text)
            if matches:
                result['hsn_4digit'] = matches[0]
                break
    
    # If we found 8-digit HSN, extract 4-digit from it
    if result['hsn_8digit'] and not result['hsn_4digit']:
        result['hsn_4digit'] = result['hsn_8digit'][:4]
    
    # Extract category based on keywords
    for pattern, category in CATEGORY_PATTERNS.items():
        if re.search(pattern, text_clean):
            result['category'] = category
            break
    
    return result


def extract_hsn_from_google_result(page_text: str, product_name: str) -> Dict[str, Optional[str]]:
    """
    Extract HSN and category from a single Google search result page.
    Uses multiple strategies to find the most relevant HSN code.
    
    Returns:
        Dict with category, hsn_4digit, hsn_8digit
    """
    result = extract_hsn_from_text(page_text)
    
    # If extraction failed, try more aggressive pattern matching
    if not result['hsn_8digit'] and not result['hsn_4digit']:
        # Look for HSN in common formats in the page
        patterns = [
            r'hsn[:\s]+(\d{4,8})',
            r'code[:\s]+(\d{4,8})',
            r'(?:hsn|code|tariff)\s+(\d{4,8})',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, page_text.lower())
            for match in matches:
                if len(match) == 8:
                    result['hsn_8digit'] = match
                    result['hsn_4digit'] = match[:4]
                    break
                elif len(match) == 4:
                    result['hsn_4digit'] = match
                    break
            if result['hsn_4digit'] or result['hsn_8digit']:
                break
    
    return result


def validate_hsn_code(hsn_code: str) -> bool:
    """
    Validate if a string looks like a valid HSN code.
    """
    if not hsn_code:
        return False
    
    # Must be all digits, 4 or 8 digits long
    if not hsn_code.isdigit():
        return False
    
    if len(hsn_code) not in (4, 8):
        return False
    
    # 4-digit HSN should be in range 0100-9999
    if len(hsn_code) == 4:
        code_int = int(hsn_code)
        return 100 <= code_int <= 9999
    
    # 8-digit HSN should be in range 01000000-99999999
    if len(hsn_code) == 8:
        code_int = int(hsn_code)
        return 1000000 <= code_int <= 99999999
    
    return False
