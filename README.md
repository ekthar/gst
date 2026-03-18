# GST HSN Resolver (Offline MVP)

Offline-first tool to process client Excel files, normalize/resolve HSN to 8-digit candidates, and export review-ready outputs.

## Linux Azure Web UI (recommended for Linux servers)

If you only have an Azure Linux server, use browser UI with Streamlit.

Start web UI:

```bash
python -m streamlit run src/gst_hsn_tool/web_app.py --server.address 0.0.0.0 --server.port 8501
```

Open in browser:

- `http://<your-azure-public-ip>:8501`

Azure Network Security Group rule required:

- Allow inbound TCP `8501` from your trusted IP.

Run in background on server:

```bash
nohup python -m streamlit run src/gst_hsn_tool/web_app.py --server.address 0.0.0.0 --server.port 8501 > webui.log 2>&1 &
tail -f webui.log
```

Web UI features:

- Mapping tab (run file mapping)
- AI Training tab (Google-only training)
- One-click `Run Training` with automatic backup zip creation
- Download backup zip directly from browser after run
- Google Inputs tab (edit product names and Google queries)

## Windows desktop app

After installation, start the UI app:

```bash
python -m gst_hsn_tool
```

Or double-click:

- `Launch GST HSN App.bat`

The desktop app includes:

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
