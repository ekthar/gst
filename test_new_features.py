#!/usr/bin/env python
"""Test script for new features"""

from gst_hsn_tool import db
from gst_hsn_tool import hsn_extractor
from gst_hsn_tool import similarity

print("=" * 60)
print("Testing Database Module")
print("=" * 60)

# Test 1: Insert product
success = db.insert_product(
    name='Cadbury Silk',
    category='Confectionery',
    hsn_4digit='2106',
    hsn_8digit='21069020',
    source_url='https://example.com'
)
print(f"✅ Insert product: {success}")

# Test 2: Retrieve product
product = db.get_product('Cadbury Silk')
if product:
    print(f"✅ Retrieved product: {product['name']}")
else:
    print(f"❌ Product not found")

# Test 3: Count products
count = db.get_total_count()
print(f"✅ Total products in DB: {count}")

print("\n" + "=" * 60)
print("Testing HSN Extractor")
print("=" * 60)

# Test HSN extraction
test_text = """
The 8-digit HSN code for Cadbury Silk chocolate is 21069020.
Category: Confectionery
The 4-digit HSN is 2106.
This product falls under Food & Beverages.
"""

extraction = hsn_extractor.extract_hsn_from_text(test_text)
print(f"✅ Extracted category: {extraction['category']}")
print(f"✅ Extracted 4-digit HSN: {extraction['hsn_4digit']}")
print(f"✅ Extracted 8-digit HSN: {extraction['hsn_8digit']}")

print("\n" + "=" * 60)
print("Testing Similarity Matching")
print("=" * 60)

# Add another product for testing
db.insert_product('Cadbury Dairy Milk', 'Chocolate & Confectionery', '2106', '21069020')

# Test fuzzy match
similar = similarity.find_similar_in_db('Cadbury Silk Chocolate')
if similar:
    print(f"✅ Found similar product: {similar['name']} (match_type: {similar['match_type']})")
else:
    print(f"ℹ️ No similar product found")

# Test keyword match
candidates = ['Cadbury Silk', 'Cadbury Dairy Milk', 'Laptop', 'Cotton Fabric']
keyword_results = similarity.keyword_match('Cadbury Chocolate', candidates)
print(f"✅ Keyword match results: {keyword_results}")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
