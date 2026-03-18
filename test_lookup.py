#!/usr/bin/env python
"""Test the improved lookup functionality"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gst_hsn_tool.lookup import lookup_product_by_name

print("=" * 60)
print("Testing Lookup Functionality")
print("=" * 60)

test_products = [
    "Cadbury Silk",
    "Laptop",
    "Cotton Fabric", 
    "iPhone 15",
    "Tea",
]

for product in test_products:
    print(f"\n🔍 Searching: {product}")
    try:
        result = lookup_product_by_name(product, auto_store=False, search_if_not_found=True)
        if result:
            print(f"   ✅ Found")
            print(f"      Category: {result.get('category')}")
            print(f"      4-digit HSN: {result.get('hsn_4digit')}")
            print(f"      8-digit HSN: {result.get('hsn_8digit')}")
            print(f"      Match type: {result.get('match_type')}")
        else:
            print(f"   ⚠️ No result returned")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
