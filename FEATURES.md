# GST HSN Resolver - Database Lookup System

## 🎯 What's New (Latest Build)

The app has been completely rebuilt as a **database-driven HSN lookup system** with the following features:

### Core Features

1. **Single Product Lookup**
   - Enter product name → Search database
   - Auto-fallback to Google search if not found
   - Results automatically stored in SQLite DB
   - Match confidence: Exact (100%) → Fuzzy (80%+) → Keyword-based

2. **Bulk File Upload & Processing**
   - Upload Excel (.xlsx) or CSV files with product names
   - Auto-lookup each product with progress tracking
   - Auto-store results in database
   - Download results as CSV or Excel

3. **Database Management**
   - View all products with category, 4-digit HSN, 8-digit HSN
   - Search products by name (fuzzy match + keyword)
   - Delete products
   - Export database as CSV

4. **Legacy Features** (Backward Compatible)
   - AI Training: Bulk training from Google search queries
   - File Mapping: Legacy product mapping
   - Settings: Edit Google queries and product names

## 📊 Database Schema

Products table:
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT,              -- e.g., "Confectionery", "Electronics"
    hsn_4digit TEXT,            -- e.g., "2106"
    hsn_8digit TEXT,            -- e.g., "21069020"
    source_url TEXT,            -- URL where data was found
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

Database location: `data/db/gst_hsn.db` (auto-created on first run)

## 🚀 Quick Start (Azure Linux)

### 1. Clone & Setup
```bash
cd ~
git clone https://github.com/ekthar/gst.git
cd gst
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Web UI
```bash
python -m streamlit run src/gst_hsn_tool/web_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501
```

### 3. Open Browser
- Local: http://localhost:8501
- Azure VM: http://<public-ip>:8501

**Note:** Make sure to expose port 8501 in Azure Network Security Group

### 4. Use Each Tab

**Lookup Tab:**
1. Enter product name (e.g., "Cadbury Silk")
2. Click "Search"
3. View results: Product, Category, 4-digit & 8-digit HSN, Match confidence
4. Product auto-saved if found from Google

**Bulk Upload Tab:**
1. Prepare Excel/CSV with product names in first column
2. Click upload file
3. Click "Run Lookup"
4. Download results as CSV or Excel
5. All products auto-saved to database

**Database Tab:**
1. View all products (paginated, limit: 10-500)
2. Search by product name
3. Delete products by name
4. Export as CSV

**Settings Tab:**
1. Edit Google search queries (for bulk AI training)
2. Edit product names (for bulk AI training)


## 🧠 How Lookup Works

### Single Product Lookup Flow
```
User enters "Cadbury Silk"
    ↓
Check database for exact match
    ↓ (if found) → Return result + Mark as DB match
    ↓ (if not found)
Fuzzy match in database (80%+ similarity)
    ↓ (if found) → Return similar product + Show confidence
    ↓ (if not found)
Keyword matching in database
    ↓ (if found) → Return result + Mark as keyword match
    ↓ (if not found)
Search Google for "Cadbury Silk 8 digit hsn code india"
    ↓
Extract from first 3 results:
  - Category (using 15 regex patterns for common categories)
  - 4-digit HSN (e.g., 2106)
  - 8-digit HSN (e.g., 21069020)
    ↓
Auto-store in database
    ↓
Return to user
```

### HSN Extraction Patterns

The AI looks for:
- **8-digit HSN**: `\b(\d{8})\b` (most reliable)
- **4-digit HSN**: `hsn\s+(?:code\s+)?(\d{4})`
- **Categories**: 15 regex patterns for common categories:
  - Electronics, Clothing, Food, Cosmetics, Furniture
  - Books, Toys, Sports, Metals, Plastics, Chemicals
  - Minerals, Wood & Paper, Animal Products, Agricultural

## 💾 Database Operations

### Python API
```python
from gst_hsn_tool import db

# Insert product
db.insert_product(
    name="Cadbury Silk",
    category="Confectionery",
    hsn_4digit="2106",
    hsn_8digit="21069020",
    source_url="https://..."
)

# Get product
product = db.get_product("Cadbury Silk")
print(product)  # Returns dict

# Search products
results = db.search_products("Cadbury", limit=10)

# Get all products
all_products = db.get_all_products(limit=1000)

# Delete product
db.delete_product("Cadbury Silk")

# Check if exists
exists = db.product_exists("Cadbury Silk")

# Get total count
count = db.get_total_count()
```

### Similarity Matching
```python
from gst_hsn_tool import similarity

# Find similar in DB (best match)
result = similarity.find_similar_in_db("Cadbury Silk Chocolate")
# Returns best match with confidence score

# Fuzzy match (80%+ threshold)
matches = similarity.fuzzy_match("Cadbury", candidates, threshold=80)

# Keyword match
keyword_results = similarity.keyword_match("Cadbury Chocolate", candidates)
```

### HSN Extraction
```python
from gst_hsn_tool import hsn_extractor

# Extract from text
result = hsn_extractor.extract_hsn_from_text(page_text)
print(result)
# {'category': 'Confectionery', 'hsn_4digit': '2106', 'hsn_8digit': '21069020'}

# Validate HSN code
is_valid = hsn_extractor.validate_hsn_code("21069020")  # True
```

## 📁 File Structure

```
gst/
├── src/gst_hsn_tool/
│   ├── db.py                    # SQLite database CRUD
│   ├── hsn_extractor.py         # HSN + category extraction
│   ├── similarity.py            # Fuzzy + keyword matching
│   ├── lookup.py                # Lookup logic + Google search
│   ├── web_app.py              # Streamlit UI (6 tabs)
│   ├── web_collector.py        # Google discovery (legacy)
│   ├── training.py             # Bulk training (legacy)
│   ├── pipeline.py             # File mapping (legacy)
│   └── config.py               # Configuration
├── data/
│   ├── db/                     # SQLite database files
│   │   └── gst_hsn.db         # Product database
│   ├── google_search_queries.txt
│   ├── google_search_products.txt
│   └── ...
├── requirements.txt
└── README.md
```

## 🔧 Configuration

Edit `src/gst_hsn_tool/config.py` to tune performance:

```python
# Database
DB_PATH = "data/db/gst_hsn.db"

# Similarity matching
SIMILARITY_THRESHOLD = 80      # Fuzzy match threshold (0-100)
SIMILARITY_FAST_MODE = False   # Disable Levenshtein for speed

# Google lookup
GOOGLE_SEARCH_TIMEOUT = 10     # seconds
GOOGLE_LOOKUP_ATTEMPTS = 3     # URLs to try per product
GOOGLE_LOOKUP_DELAY = 0.3     # seconds between lookups (throttle)
```

## ✅ Testing

Run the test script:
```bash
python test_new_features.py
```

Output should show:
- ✅ Database operations (insert, retrieve, count)
- ✅ HSN extraction (category, 4-digit, 8-digit)
- ✅ Similarity matching (fuzzy, keyword, exact)

## 🎓 Usage Examples

### Example 1: Single Lookup
```
User: "Cadbury Silk"
System: Exact match → Found in database
Category: Confectionery
4-Digit HSN: 2106
8-Digit HSN: 21069020
Match Type: Database (existing)
```

### Example 2: New Product (Google Lookup)
```
User: "iPhone 15"
System: Not in database → Search Google
Found in Google results → Extract HSN
Category: Electronics
4-Digit HSN: 8517
8-Digit HSN: 85171200
Match Type: Google search (new)
Stored: ✅ Added to database
```

### Example 3: Bulk Upload
```
File: products.xlsx
Column A: ["Cadbury Silk", "Laptop", "Cotton Shirt"]
        ↓
Lookup each (3 items)
Result:
  - Cadbury Silk: Found in DB (exact)
  - Laptop: Found in DB (fuzzy "Lenovo Laptop")
  - Cotton Shirt: Google search → Added to DB
        ↓
Download: gst_hsn_lookup_results_20260318_1234.csv
```

## 🐛 Troubleshooting

### Port 8501 not accessible
```bash
# On Azure VMs (Linux)
1. Open Azure Portal
2. VM → Networking → Add inbound rule
3. Protocol: TCP, Port: 8501, Source: Your IP
4. Test: curl http://127.0.0.1:8501
```

### Database locked
```bash
# If you see "database is locked" error:
# 1. Stop all running instances
# 2. Delete data/db/gst_hsn.db (will be recreated)
# 3. Restart app
```

### Google search returns 0 results
```bash
# Common causes:
1. Incorrect working directory (must be ~/gst)
2. Google rate-limiting (add delay in config)
3. Network/proxy issues

# Debug:
python -c "from gst_hsn_tool import lookup; print(lookup._search_google_for_hsn('test'))"
```

## 📞 Support

- **GitHub**: https://github.com/ekthar/gst
- **Issues**: Report via GitHub issues
- **Logs**: Check data/logs/ for any errors

## 📜 License

This project is provided as-is for GST HSN code resolution.

---

**Last Updated**: March 18, 2026
**Version**: 3.0 (Database-driven with bulk upload)
