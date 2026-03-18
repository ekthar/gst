# GST HSN Resolver

Streamlined newest-model build focused on:
1. Single product lookup
2. Bulk file lookup
3. SQLite database management

## Run

### Local
```bash
python run_web_app.py --local
```

### Azure/Linux VM
```bash
python run_web_app.py --azure
```

The Azure mode binds to `0.0.0.0` and uses `$PORT` when present.

## Features

- DB-first lookup with fuzzy/keyword matching
- Online fallback search (Google + DuckDuckGo)
- 4-digit and 8-digit HSN extraction/enrichment
- GST master enrichment from `data/hsn_master_from_gst.csv`
- Parallel bulk processing with retry tools for unresolved rows

## Input Format

Upload `.xlsx` or `.csv` with product names in the first column.

## Output Columns

- `input_name`
- `matched_name`
- `category`
- `hsn_4digit`
- `hsn_8digit`
- `source_url`
- `match_type`
- `confidence`
- `is_new`

## Project Layout

- `run_web_app.py`: launcher for local/Azure
- `src/gst_hsn_tool/web_app.py`: Streamlit UI
- `src/gst_hsn_tool/lookup.py`: resolver pipeline
- `src/gst_hsn_tool/db.py`: SQLite storage
- `src/gst_hsn_tool/hsn_extractor.py`: code extraction logic
- `src/gst_hsn_tool/similarity.py`: local similarity matching
- `src/gst_hsn_tool/loader.py`: master CSV loader

## Install

```bash
pip install -r requirements.txt
```
