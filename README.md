# GST HSN Resolver - Database-Driven Lookup

**Latest Release (v3.0):** Complete rebase to database-driven HSN lookup with bulk file upload support.

## 🎯 What It Does

Convert product names to GST HSN codes with a **database-backed lookup system**:

1. **Single Product Lookup** - Enter product name → Get category + 4-digit & 8-digit HSN
2. **Bulk File Upload** - Upload Excel/CSV with product names → Auto-lookup all → Download results
3. **Database Management** - View, search, delete products in SQLite DB
4. **AI Training** (legacy) - Bulk training from Google search queries
5. **File Mapping** (legacy) - Legacy product mapping

## 🚀 Quick Start

### For Azure Linux Server

```bash
# 1. Clone & setup
cd ~
git clone https://github.com/ekthar/gst.git
cd gst
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run web UI
python -m streamlit run src/gst_hsn_tool/web_app.py --server.address 0.0.0.0 --server.port 8501

# 3. Open browser
# http://<your-public-ip>:8501
```

**Important:** Expose port 8501 in Azure NSG:
- Go to Azure Portal → VM → Networking → Add inbound rule
- Protocol: TCP, Port: 8501, Source: Your IP

### For Windows Desktop

```bash
python -m gst_hsn_tool
```

## 📊 Database-Driven Workflow

```
Product Name Input
         ↓
┌─────────────────────┐
│  Check SQLite DB    │
├─────────────────────┤
│ 1. Exact match?     │ ✅ Return (100% confidence)
│ 2. Fuzzy match?     │ ✅ Return (80%+ confidence)
│ 3. Keyword match?   │ ✅ Return (50% confidence)
└─────────────────────┘
         ↓
    Not found
         ↓
┌─────────────────────┐
│  Google Search      │
├─────────────────────┤
│ Search: "[Product]  │
│  8 digit hsn code   │
│  india"             │
│                     │
│ Extract:            │
│ • Category          │
│ • 4-digit HSN       │
│ • 8-digit HSN       │
└─────────────────────┘
         ↓
    Auto-Store in DB
         ↓
   Return to User
```

## 🎨 Web UI Tabs

### 1. Lookup Tab 🔍
- Enter single product name
- Instant search (DB → Google fallback)
- Shows match type & confidence
- Auto-stores new products

**Example:**
```
Input: "Cadbury Silk"
Output:
  Product: Cadbury Silk
  Category: Confectionery
  4-Digit HSN: 2106
  8-Digit HSN: 21069020
  Match: Database (exact)
```

### 2. Bulk Upload Tab 📁
- Upload Excel (.xlsx) or CSV file
- Auto-lookup all products (progress tracking)
- Download results as CSV or Excel
- All products saved to database

**Workflow:**
1. Upload file with product names in column A
2. Click "Run Lookup"
3. Wait for progress
4. Download results

### 3. Database Tab 🗄️
- View all products (10-500 limit)
- Search by name (fuzzy match)
- Delete products
- Export as CSV

### 4. AI Training Tab 🤖 (legacy)
- Bulk training from Google queries
- Auto-backup after run
- Download backup zip

### 5. Mapping Tab 📋 (legacy)
- Legacy file mapping feature
- Backward compatible

### 6. Settings Tab ⚙️
- Edit Google search queries
- Edit product names for training

## 💾 How Data is Stored

SQLite database (`data/db/gst_hsn.db`):

```sql
products:
  - id (primary key)
  - name (unique, indexed)
  - category
  - hsn_4digit
  - hsn_8digit
  - source_url
  - created_at
  - updated_at
```

All lookups (DB + Google) are automatically stored.

## 🧠 Similarity Matching Strategy

```
Confidence Levels:
  100% → Exact match in DB
   80%+ → Fuzzy match (typos tolerated)
   50% → Keyword match (partial names)
    N/A → Google search (new product)
```

**Example Matches:**
- "Cadbury Silk" = "Cadbury Silk" (exact, 100%)
- "cadbury silk chocolate" ≈ "Cadbury Silk" (fuzzy, 85%)
- "cadbury chocolate" = "Cadbury Silk" (keyword, 50%)

## 📥 File Upload Format

**Supported formats:** Excel (.xlsx) or CSV

**Format:**
```
Product Name          (any other columns ignored)
Cadbury Silk
Laptop
Cotton Fabric
iPhone 15
```

**Output:**
```
Product Name    | Category      | 4-Digit HSN | 8-Digit HSN | Source URL              | Match Type
Cadbury Silk    | Confectionery | 2106        | 21069020    | https://...             | database
Laptop          | Electronics   | 8471        | 84715030    | https://...             | fuzzy
Cotton Fabric   | Textiles      | 5208        | 52081200    | https://...             | google_search
iPhone 15       | Electronics   | 8517        | 85171200    | https://...             | google_search
```

## 🔧 Configuration

Edit `src/gst_hsn_tool/config.py`:

```python
# Similarity matching
SIMILARITY_THRESHOLD = 80          # 0-100 (fuzzy match)

# Google lookup
GOOGLE_SEARCH_TIMEOUT = 10         # seconds
GOOGLE_LOOKUP_ATTEMPTS = 3         # URLs to try
GOOGLE_LOOKUP_DELAY = 0.3         # throttle between requests
```

## 📦 Dependencies

```
streamlit==1.42.2           # Web UI
openpyxl==3.1.5           # Excel handling
xlrd==2.0.1               # Legacy Excel
fuzzywuzzy==0.18.0        # Fuzzy matching
python-Levenshtein==0.23.0 # Faster fuzzy matching
pandas==2.3.3             # Data processing
```

Install all:
```bash
pip install -r requirements.txt
```

## 🧪 Testing

Run comprehensive tests:
```bash
python test_new_features.py
```

Or test individual modules:
```python
from gst_hsn_tool import db, lookup, similarity

# Database
product = db.get_product("Cadbury Silk")

# Lookup
result = lookup.lookup_product_by_name("iPhone 15")

# Similarity
similar = similarity.find_similar_in_db("Cadbury Chocolate")
```

## 📊 Performance

- **Lookup speed:** ~0.5-2 seconds (DB lookup) or ~5-10 seconds (Google search)
- **Bulk upload:** ~0.3-1 second per product (with throttle)
- **Database size:** ~1MB per 1000 products
- **Memory:** <100MB for 10,000 products

Tips to improve speed:
1. Pre-populate database with common products
2. Enable fuzzy caching (faster matching)
3. Reduce Google lookup delay (may risk throttling)

## 🐛 Common Issues

### "Port 8501 already in use"
```bash
# Kill existing process
lsof -i :8501 | grep -v PID | awk '{print $2}' | xargs kill -9
```

### "Database is locked"
```bash
# Stop all instances and delete DB
rm -f data/db/gst_hsn.db
# App will recreate on next run
```

### "Google returns 0 results"
- Check working directory (must be repo root)
- Add delay between requests (config.py)
- Check network/proxy settings

## 📂 Project Structure

```
gst/
├── src/gst_hsn_tool/
│   ├── db.py              # Database CRUD
│   ├── hsn_extractor.py   # HSN + category extraction
│   ├── similarity.py      # Fuzzy matching
│   ├── lookup.py          # Lookup logic
│   ├── web_app.py        # Streamlit UI (NEW)
│   ├── web_collector.py  # Google discovery
│   ├── training.py       # Bulk training
│   └── config.py         # Config
├── data/
│   ├── db/               # SQLite databases
│   │   └── gst_hsn.db
│   ├── google_search_*.txt
│   └── ...
├── requirements.txt
├── README.md
└── FEATURES.md           # Detailed feature guide
```

## 📖 Documentation

- **FEATURES.md** - Detailed feature documentation and API reference
- **README.md** - This file (quick start)
- **Code comments** - In-depth documentation in source files

## 🎓 Usage Examples

### Example 1: Single Lookup via Web UI

```
User navigates to "Lookup" tab
Enters: "Cadbury Silk"
Clicks: "Search"
System shows:
  ✅ Category: Confectionery
  ✅ 4-Digit HSN: 2106
  ✅ 8-Digit HSN: 21069020
  ✅ Match Type: Database (existing)
```

### Example 2: Bulk Upload from Excel

```
User prepares: products.xlsx
  Column A: ["Cadbury Silk", "Laptop", "Cotton Fabric", "iPhone 15"]
  
Navigates to "Bulk Upload" tab
Uploads file
Clicks: "Run Lookup"

System processes (progress bar):
  ✅ Cadbury Silk → DB (exact match)
  ✅ Laptop → DB (fuzzy match "Lenovo Laptop")
  ✅ Cotton Fabric → Google search (new)
  ✅ iPhone 15 → Google search (new)
  
Downloads: gst_hsn_results_20260318_1234.csv
All 4 products saved to DB for future lookups
```

### Example 3: Database Search

```
User navigates to "Database" tab
Searches: "Cadbury"
System returns:
  ✅ Cadbury Silk (Confectionery, 2106, 21069020)
  ✅ Cadbury Dairy Milk (Chocolate, 2106, 21069020)
  ✅ Cadbury Bournvita (Beverages, 2202, 22029090)
  
User can:
  📥 Download as CSV
  🗑️ Delete products
  📊 View full details
```

## 🚀 Deployment

### For Azure Linux (Recommended)

```bash
# 1. SSH into VM
ssh azureuser@<public-ip>

# 2. Clone and setup
cd ~ && git clone https://github.com/ekthar/gst.git && cd gst
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run (interactive for testing)
python -m streamlit run src/gst_hsn_tool/web_app.py --server.address 0.0.0.0 --server.port 8501

# 4. Or run in background
nohup python -m streamlit run src/gst_hsn_tool/web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &
tail -f web.log
```

### Port Exposure (Azure NSG)

1. Open Azure Portal
2. Navigate to VM → Networking → Inbound port rules
3. Click "+ Add inbound port rule"
4. Configure:
   - Source: IP / Your public IP
   - Destination port: 8501
   - Protocol: TCP
   - Action: Allow
5. Click Add

Test:
```bash
curl -I http://<your-public-ip>:8501
# Should return 200 OK
```

## 📝 Version History

- **v3.0** (Mar 18, 2026) - Database-driven lookup, bulk upload, similarity matching
- **v2.0** - Google-only training pipeline with parallel fetching
- **v1.0** - Initial offline mapping tool

## 📞 Support

- **Issues:** https://github.com/ekthar/gst/issues
- **Wiki:** https://github.com/ekthar/gst/wiki

---

**Last Updated:** March 18, 2026
**Repository:** https://github.com/ekthar/gst


- File pickers for client input, HSN master, and output file.
- One-click run button.
- Live run log and completion summary.
- Open-output button to launch the generated Excel file.
- Download Official HSN button to auto-create local master from GST source.
- AI Training Mode button for separate practice-data refresh.
- Backup Training and Restore Training buttons.
- Separate `AI Training` tab with dedicated logs.
- Upload training file flow with user-defined headers (for example: Product, Category, HSN Code).

## Modern UI font setup (Hanken Grotesk)

The UI is configured to prefer `Hanken Grotesk` for a modern rounded look.

To bundle this font with your app build:

1. Put font files in `assets/fonts/`.
2. Recommended names:
  - `HankenGrotesk-VariableFont_wght.ttf`
  - `HankenGrotesk-Regular.ttf`
  - `HankenGrotesk-Medium.ttf`

If these files are not present, app falls back to `Segoe UI` automatically.

## Build EXE and installer for other systems

### 1) Build executable folder (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1 -AppVersion 0.1.0
```

Output:

- `dist/GST HSN Resolver/GST HSN Resolver.exe`

Share the full `dist/GST HSN Resolver/` folder if you do not need an installer.

### 2) Build installable setup (.exe installer)

Install Inno Setup 6 first: https://jrsoftware.org/isinfo.php

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1 -AppVersion 0.1.0
```

Installer output:

- `dist_installer/GST-HSN-Resolver-Setup-0.1.0.exe`

You can distribute this installer to different Windows systems.

## No HSN master? Auto-download from GST

You can generate your local master directly from official GST directory:

Option 1 (UI):

- Open app and click `Download Official HSN`.
- Save the generated CSV (for example `data/hsn_master_from_gst.csv`).
- The app auto-fills this file as HSN master.

Option 2 (command):

```bash
python -m gst_hsn_tool.bootstrap_master --output data/hsn_master_from_gst.csv
```

This downloads `HSN_SAC.xlsx` from GST tutorial domain and builds an 8-digit goods master using `HSN_MSTR` sheet.

## Real-world noisy names supported

The matcher supports messy client spellings and short forms (example: cabdury diary mik, cd milk, c diary milk) using:

- typo and phrase normalization,
- token-based fuzzy matching,
- keyword-to-HSN chapter hints,
- confidence-based review routing.

Rows with low confidence remain in manual review queue.

## AI-like learning memory (offline)

The app now learns from past high-confidence mappings and reuse them in future runs.

- Learning database file: `data/learned_mappings.csv`
- Reuses exact learned hits first, then fuzzy learned hits.
- Saves new learned records from confident rows automatically.
- Fully offline, no paid API needed.

This means repeat product names and close spelling variants improve over time.

## Upload file training with headers

In `AI Training` tab, you can upload Excel/CSV and map header names:

- Product header (example: `Product`)
- Category header (example: `Category`)
- HSN header (example: `HSN Code`)

The app imports these rows into `data/learned_mappings.csv` for future runs.

## Separate AI training mode (Google-only feed)

Training mode is separate from normal filing run.

- Downloads or snapshots HSN master for training use.
- Runs Google Search queries only.
- Collects pages only from URLs discovered in Google results.
- Feeds only those Google-discovered pages into harvested HSN pairs.
- Creates a practice file in `data/training/practice/`.
- Keeps training artifacts in `data/training/`.

This lets the system refresh practice data without touching your filing flow.

Control the exact search prompts in:

- `data/google_search_queries.txt`

For product-wise search, add names in:

- `data/google_search_products.txt`

Example line:

- `cabdury silk`

Training mode automatically creates queries like:

- `cabdury silk 8 digit hsn code category`
- `cabdury silk gst hsn code 8 digit`

Only Google-discovered links from these searches are fed into AI learning.

## Scaling training data to GB-level

Training mode now writes a cumulative corpus file:

- `data/training/corpus/training_corpus.csv`

To increase data volume, tune these constants in `src/gst_hsn_tool/config.py`:

- `TRAINING_MAX_PAGES` (crawl more pages per run)
- `TRAINING_PRACTICE_MAX_ROWS` (generate larger practice files per run)
- `TRAINING_MAX_SECONDS` (hard time budget per run)
- `TRAINING_GOOGLE_MAX_RESULTS_PER_QUERY` (Google result depth per query)
- `TRAINING_GOOGLE_PRODUCT_LIMIT` (max product names used per run)
- `TRAINING_FETCH_WORKERS` (parallel page fetch workers)
- `TRAINING_GOOGLE_DISCOVERY_DELAY_SECONDS` (delay between Google result-page requests)

This keeps training mode focused and ensures only Google-discovered links feed AI learning.

Each run also writes discovered Google result URLs to:

- `data/training/raw/google_discovered_*.csv`

### Bulk GB training

Use repeated autonomous runs to grow corpus:

```bash
python -m gst_hsn_tool.train_bulk --target-gb 1 --max-runs 50 --master data/hsn_master_from_gst.csv
```

This keeps running training mode until corpus reaches target size or max runs.

Run AI Training Mode repeatedly; corpus grows and deduplicates over time.

## Backup and restore

You can backup and restore the entire training memory state.

- Backup includes `data/learned_mappings.csv` and `data/training/` files.
- Restore safely restores only those allowed paths.

## File lock handling

If output Excel is open in another app, mapper now auto-saves to a timestamped fallback file instead of failing.

## What this MVP does

- Reads a client Excel file.
- Reads a local HSN reference CSV.
- Matches product descriptions to likely 8-digit HSN codes.
- Expands 4-digit and 6-digit client HSN codes to 8-digit candidates.
- Assigns confidence score and review status.
- Exports 3 sheets in one Excel output: `mapped`, `review_queue`, `audit_log`.

## Output columns (requested format)

The primary mapped output contains these columns first:

1. product_name
2. category
3. hsn4
4. hsn6
5. hsn_description

Additional controls: resolved_hsn8, score, status, reason.

## Quick start

1. Create and activate a virtual environment.
2. Install package:

```bash
pip install -e .
```

For tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -q
```

3. Run:

```bash
python -m gst_hsn_tool.cli \
  --input data/client_input_template.csv \
  --hsn-master data/hsn_master_template.csv \
  --output data/output_result.xlsx
```

## Expected input columns

Client input file should include these columns:

- `product_id` (optional but recommended)
- `description` (required)
- `category` (optional)
- `client_hsn` (optional, supports 4/6/8 digits)
- `gst_rate` (optional)

HSN master file should include these columns:

- `hsn8` (required, exactly 8 digits)
- `description` (required)
- `category` (optional)
- `rate` (optional)
- `aliases` (optional, `|` separated)

## Review routing thresholds

- `>= 90`: `auto_approved`
- `75 - 89`: `supervisor_review`
- `< 75`: `manual_review`

## Notes

- This is Phase-1 implementation scaffolding, designed to be extended with domain rules for food/pharma/supermarket products.
- Keep `hsn_master_template.csv` updated as your canonical source.
- CLI is still available, but desktop UI is now the primary workflow on Windows.
- For very large volumes (20 lakh rows), prefer CSV output path (for example `output.csv`) because single-sheet Excel has row limits.
- Repeated product names are cached automatically to reduce matching time.
- Learning memory accumulates across runs in `data/learned_mappings.csv`.
