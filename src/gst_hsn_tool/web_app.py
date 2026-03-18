"""
GST HSN Resolver - Streamlit Web UI for Azure deployment
Database-driven lookup with bulk file upload support
"""

from __future__ import annotations

import io
import csv
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd
from openpyxl import load_workbook

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gst_hsn_tool import db
from gst_hsn_tool.lookup import lookup_product_by_name, bulk_lookup_products
from gst_hsn_tool.training import backup_training_state, run_training_mode
from gst_hsn_tool.config import (
    DEFAULT_BACKUP_FILE,
    LEARNING_DB_PATH,
    TRAINING_CORPUS_FILE,
    TRAINING_GOOGLE_PRODUCTS_FILE,
    TRAINING_GOOGLE_QUERIES_FILE,
)
from gst_hsn_tool.pipeline import run_pipeline


def _canonical_name_key(name: str) -> str:
    """Normalize product names for better dedupe during bulk runs."""
    text = str(name or "").lower().strip()
    text = re.sub(r"\b(rs\.?\s*\d+(?:\.\d+)?)\b", " ", text)
    text = re.sub(r"\b\d+(?:g|gm|kg|ml|l|pcs?)\b", " ", text)
    text = re.sub(r"\b(117|177|217)\b", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def _write_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _setup_page() -> None:
    st.set_page_config(
        page_title="GST HSN Resolver",
        page_icon="🔍",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        :root {
            --bg: #fff8f5;
            --card: #ffffff;
            --text: #2f2230;
            --muted: #7b6a79;
            --accent: #ff8259;
            --line: #f2d8cd;
            --mint: #75b9af;
        }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: "Hanken Grotesk", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent);
            border-bottom: 3px solid var(--accent);
        }
        .stButton > button {
            background: linear-gradient(135deg, var(--accent) 0%, #ff9a7b 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            padding: 0.75rem 1.5rem;
        }
        .stButton > button:hover {
            opacity: 0.9;
        }
        .stContainer {
            background: var(--card);
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid var(--line);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _lookup_tab() -> None:
    """Single product HSN lookup tab"""
    st.header("🔍 Product HSN Lookup")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        product_name = st.text_input(
            "Enter product name",
            placeholder="e.g., Cadbury Silk, Laptop, Cotton Fabric",
            key="lookup_product"
        )
    
    with col2:
        search_button = st.button("🔍 Search", use_container_width=True)
    
    if search_button and product_name:
        st.info(f"🔍 Searching for '{product_name}'...")
        
        try:
            with st.spinner("Checking database and Google..."):
                result = lookup_product_by_name(
                    product_name.strip(),
                    auto_store=True,
                    search_if_not_found=True
                )
            
            if result:
                # Display results in columns
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Product", result.get('name', 'N/A')[:20])
                with col2:
                    st.metric("Category", result.get('category', 'Not found'))
                with col3:
                    st.metric("4-Digit HSN", result.get('hsn_4digit', 'N/A'))
                with col4:
                    st.metric("8-Digit HSN", result.get('hsn_8digit', 'N/A') or 'Searching...')
                
                # Show match details
                st.divider()
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    match_type = result.get('match_type', 'Unknown')
                    st.write(f"**Match Type:** {match_type.replace('_', ' ').title()}")
                
                with col2:
                    if result.get('match_type') in ['fuzzy', 'keyword']:
                        confidence = result.get('confidence', 'N/A')
                        st.write(f"**Confidence:** {confidence}%")
                    elif result.get('match_type') == 'database':
                        st.write("**Status:** ✅ Exact database match")
                    else:
                        st.write("**Status:** 🔎 Found via Google search")
                
                with col3:
                    if result.get('source_url'):
                        st.write(f"**Source:** [Link]({result['source_url'][:50]}...)")
                
                st.divider()
                
                # Show if it's new
                if result.get('is_new'):
                    st.success("✅ New product added to database!")
                else:
                    st.info("ℹ️ Product found in database")
            else:
                st.warning("⚠️ Could not find product information. Try different name.")
        
        except Exception as e:
            st.error(f"❌ Error during search: {str(e)}")
            st.info("Try refreshing and searching again")
    
    # Show example searches
    st.divider()
    st.markdown("### 📚 Example Searches")
    st.markdown("""
    Try these products:
    - **Cadbury Silk** (Chocolate/Confectionery)
    - **Laptop** (Electronics)
    - **Cotton Shirt** (Textiles)
    - **iPhone** (Electronics)
    - **Tea** (Beverages)
    """)


def _bulk_upload_tab() -> None:
    """Bulk upload tab for Excel/CSV files with real-time DB updates"""
    st.header("📁 Bulk Upload & Auto-Lookup")
    
    st.write("Upload Excel/CSV → Auto-search HSN for each product → Results saved to DB in real-time")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "📄 Upload Excel (.xlsx) or CSV file",
        type=["xlsx", "csv"],
        key="bulk_upload"
    )
    
    if uploaded_file:
        try:
            # Read file
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Loaded {len(df)} rows from file")
            
            # Show preview
            with st.expander("👀 Preview data", expanded=True):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Get product names (first column)
            if len(df.columns) > 0:
                product_column = df.columns[0]
                product_names = df[product_column].dropna().astype(str).tolist()
                
                st.info(f"📊 **{len(product_names)}** products ready to lookup")

                speed_col1, speed_col2, speed_col3 = st.columns(3)
                with speed_col1:
                    max_workers = st.slider("Parallel workers", min_value=2, max_value=24, value=10, step=2)
                with speed_col2:
                    dedupe_names = st.checkbox("Deduplicate exact names", value=True)
                with speed_col3:
                    show_live_details = st.checkbox("Show live details (slower)", value=False)

                strategy_col1, strategy_col2 = st.columns(2)
                with strategy_col1:
                    fast_local_first = st.checkbox("Hybrid fast mode (local/master first)", value=True)
                with strategy_col2:
                    deep_google_all = st.checkbox("Deep Google for every item (slower)", value=False)
                
                # Start lookup button
                if st.button("🚀 Start Auto-Lookup (Background)", use_container_width=True):
                    
                    # Create real-time progress display
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.container()
                    
                    # Store results
                    all_results: list[dict | None] = [None] * len(product_names)
                    success_count = 0
                    processed = 0

                    # Build unique-name map to reduce duplicate searches.
                    key_to_indexes: dict[str, list[int]] = {}
                    key_to_name: dict[str, str] = {}
                    for idx, raw_name in enumerate(product_names):
                        cleaned = str(raw_name).strip()
                        canonical = _canonical_name_key(cleaned)
                        key_base = canonical if canonical else cleaned.lower()
                        key = key_base if dedupe_names else f"{idx}:{key_base}"
                        key_to_name.setdefault(key, cleaned)
                        key_to_indexes.setdefault(key, []).append(idx)
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_map = {
                            executor.submit(
                                lookup_product_by_name,
                                key_to_name[key],
                                True,
                                True,
                                not fast_local_first and deep_google_all,
                                fast_local_first,
                            ): key
                            for key in key_to_indexes
                        }

                        for future in as_completed(future_map):
                            key = future_map[future]
                            canonical_name = key_to_name[key]
                            indexes = key_to_indexes[key]

                            result = None
                            error_text = None
                            try:
                                result = future.result()
                            except Exception as exc:
                                error_text = str(exc)[:60]

                            for row_idx in indexes:
                                original_name = str(product_names[row_idx]).strip()
                                if result:
                                    row = {
                                        'input_name': original_name,
                                        'matched_name': result.get('matched_name') or result.get('name') or original_name,
                                        'category': result.get('category'),
                                        'hsn_4digit': result.get('hsn_4digit'),
                                        'hsn_8digit': result.get('hsn_8digit'),
                                        'source_url': result.get('source_url'),
                                        'match_type': result.get('match_type', 'unknown'),
                                        'confidence': result.get('confidence'),
                                        'is_new': result.get('is_new', False),
                                    }
                                    all_results[row_idx] = row
                                    if row['hsn_4digit']:
                                        success_count += 1
                                else:
                                    all_results[row_idx] = {
                                        'input_name': original_name,
                                        'matched_name': None,
                                        'category': 'Error' if error_text else None,
                                        'hsn_4digit': None,
                                        'hsn_8digit': None,
                                        'source_url': None,
                                        'match_type': f'error: {error_text}' if error_text else 'not_found',
                                        'confidence': None,
                                        'is_new': False,
                                    }
                                processed += 1

                            progress = processed / max(1, len(product_names))
                            progress_bar.progress(progress)
                            status_text.text(
                                f"⏳ Processing: {processed}/{len(product_names)} | ✅ Saved: {success_count} | ⚡ Workers: {max_workers}"
                            )

                            if show_live_details:
                                with results_container:
                                    outcome = result.get('hsn_4digit') if result else 'N/A'
                                    st.caption(f"{canonical_name} -> HSN {outcome}")
                    
                    # Completion
                    progress_bar.progress(1.0)
                    status_text.empty()
                    
                    st.success(f"✅ **Lookup Complete!** Saved {success_count}/{len(product_names)} products to database")
                    
                    # Show summary stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Processed", len(product_names))
                    with col2:
                        st.metric("Successfully Added", success_count)
                    with col3:
                        st.metric("Failed/Skipped", len(product_names) - success_count)
                    
                    # Results table
                    st.subheader("📋 Results Summary")
                    results_df = pd.DataFrame([r for r in all_results if r is not None])
                    st.dataframe(results_df, use_container_width=True)
                    
                    # Download options
                    st.divider()
                    st.subheader("📥 Download Results")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # CSV download
                        csv_buffer = io.StringIO()
                        results_df.to_csv(csv_buffer, index=False)
                        csv_data = csv_buffer.getvalue()
                        
                        st.download_button(
                            label="📥 Download as CSV",
                            data=csv_data,
                            file_name=f"gst_hsn_lookup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    with col2:
                        # Excel download
                        excel_buffer = io.BytesIO()
                        results_df.to_excel(excel_buffer, index=False, sheet_name="HSN Lookup")
                        excel_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Download as Excel",
                            data=excel_buffer.getvalue(),
                            file_name=f"gst_hsn_lookup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
        
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
    
    else:
        # Show file format guide
        st.info("📝 **File Format Guide:**")
        st.markdown("""
        Your Excel/CSV should have product names in the **first column**:
        
        | Product Name | (other columns ignored) |
        |---|---|
        | Cadbury Silk | ... |
        | Laptop | ... |
        | Cotton Fabric | ... |
        
        The app will:
        1. 🔍 Search for HSN code for each product
        2. 💾 Save to database automatically
        3. 📊 Show results in real-time
        4. 📥 Let you download the results
        """)


def _database_tab() -> None:
    """Database management tab"""
    st.header("🗄️ Database Management")
    
    # Show stats
    total_count = db.get_total_count()
    st.metric("📊 Total Products in Database", total_count)
    
    st.divider()
    
    # Tabs for different database operations
    tab_view, tab_search, tab_delete, tab_reset = st.tabs([
        "View All",
        "Search",
        "Delete Item",
        "Reset Database"
    ])
    
    with tab_view:
        st.subheader("📋 All Products")
        limit = st.selectbox("Show limit:", [10, 25, 50, 100, 500, 1000], key="view_limit")
        
        products = db.get_all_products(limit=limit)
        
        if products:
            df = pd.DataFrame(products)
            df = df.drop('id', axis=1)
            df = df.rename(columns={
                'name': 'Product Name',
                'category': 'Category',
                'hsn_4digit': '4-Digit HSN',
                'hsn_8digit': '8-Digit HSN',
                'source_url': 'Source URL',
                'created_at': 'Created'
            })
            
            st.dataframe(df, use_container_width=True, height=500)
            
            # Export option
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label="📥 Download All as CSV",
                data=csv_data,
                file_name=f"gst_hsn_db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("📭 No products in database yet. Start by uploading a file!")
    
    with tab_search:
        st.subheader("🔍 Search Products")
        search_query = st.text_input("Search by product name", placeholder="e.g., Cadbury")
        
        if search_query:
            products = db.search_products(search_query.strip(), limit=100)
            
            if products:
                df = pd.DataFrame(products)
                df = df.drop('id', axis=1)
                df = df.rename(columns={
                    'name': 'Product Name',
                    'category': 'Category',
                    'hsn_4digit': '4-Digit HSN',
                    'hsn_8digit': '8-Digit HSN',
                    'source_url': 'Source URL',
                    'created_at': 'Created'
                })
                
                st.dataframe(df, use_container_width=True)
                st.success(f"✅ Found {len(df)} products")
            else:
                st.warning(f"❌ No products found matching '{search_query}'")
    
    with tab_delete:
        st.subheader("🗑️ Delete Product")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            product_to_delete = st.text_input("Enter product name to delete", key="delete_product")
        
        with col2:
            st.write("")
            st.write("")
            if st.button("🗑️ Delete", use_container_width=True, key="delete_btn"):
                if product_to_delete:
                    success = db.delete_product(product_to_delete.strip())
                    if success:
                        st.success(f"✅ Deleted: {product_to_delete}")
                        st.rerun()
                    else:
                        st.error(f"❌ Product not found: {product_to_delete}")
    
    with tab_reset:
        st.subheader("⚠️ Reset Database")
        st.warning("⚠️ **Warning:** This will delete ALL products in the database and cannot be undone!")
        
        st.markdown("""
        Use this option to:
        - Start fresh with a clean database
        - Remove all previous lookups
        - Clear space for new data
        """)
        
        if st.checkbox("I understand and want to delete all data", key="confirm_reset"):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Reset Database to Empty", use_container_width=True, key="reset_btn"):
                    try:
                        # Delete the database file
                        from pathlib import Path
                        db_path = Path(__file__).parent.parent.parent / "data" / "db" / "gst_hsn.db"
                        if db_path.exists():
                            db_path.unlink()
                            st.success("✅ Database reset successfully!")
                            st.info("📝 Database will be recreated on next lookup. Reloading...")
                            st.rerun()
                        else:
                            st.info("ℹ️ Database file not found, creating fresh...")
                            db.init_db()
                            st.success("✅ Fresh database created!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error resetting database: {str(e)}")
            
            with col2:
                current_count = db.get_total_count()
                st.metric("Products to Delete", current_count)


def _mapping_tab() -> None:
    """Legacy mapping tab"""
    st.header("📋 File Mapping (Legacy)")
    
    uploaded_file = st.file_uploader("Upload Excel file for mapping", type=["xlsx"])
    
    if uploaded_file:
        st.info(f"File: {uploaded_file.name}")
        
        if st.button("▶️ Run Mapping", use_container_width=True):
            with st.spinner("Processing..."):
                try:
                    result = run_pipeline(uploaded_file)
                    st.success("✅ Mapping completed")
                    st.write(result)
                except Exception as e:
                    st.error(f"Error: {str(e)}")


def _training_tab() -> None:
    """AI training tab (backward compatibility)"""
    st.header("🤖 AI Training Mode")
    st.write("Bulk training from Google search queries (legacy mode)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        auto_backup = st.checkbox("✅ Auto-backup after training", value=True)
    
    with col2:
        st.write("")
    
    if st.button("🚀 Run Training", use_container_width=True):
        st.info("Starting AI training mode...")
        
        with st.spinner("Training in progress..."):
            result = run_training_mode()
        
        # Display results
        st.markdown("### Training Results")
        for key, value in result.items():
            st.write(f"**{key}:** {value}")
        
        # Auto-backup if enabled
        if auto_backup:
            st.info("Creating backup...")
            backup_path = backup_training_state(Path.cwd())
            
            if backup_path.exists():
                st.success(f"✅ Backup created: {backup_path.name}")
                
                # Offer download
                with open(backup_path, 'rb') as f:
                    backup_data = f.read()
                
                st.download_button(
                    label="📥 Download Backup Zip",
                    data=backup_data,
                    file_name=backup_path.name,
                    mime="application/zip",
                    use_container_width=True
                )


def _settings_tab() -> None:
    """Settings tab"""
    st.header("⚙️ Settings")
    
    st.subheader("Google Search Queries")
    
    queries_text = _read_text(TRAINING_GOOGLE_QUERIES_FILE)
    new_queries = st.text_area(
        "Edit Google search queries (one per line)",
        value=queries_text,
        height=150,
        key="queries_input"
    )
    
    if st.button("💾 Save Queries", use_container_width=True):
        _write_text(TRAINING_GOOGLE_QUERIES_FILE, new_queries)
        st.success("✅ Queries saved")
    
    st.divider()
    
    st.subheader("Product Names for Training")
    
    products_text = _read_text(TRAINING_GOOGLE_PRODUCTS_FILE)
    new_products = st.text_area(
        "Edit product names (one per line)",
        value=products_text,
        height=150,
        key="products_input"
    )
    
    if st.button("💾 Save Products", use_container_width=True):
        _write_text(TRAINING_GOOGLE_PRODUCTS_FILE, new_products)
        st.success("✅ Products saved")


def main() -> None:
    _setup_page()
    st.title("🔍 GST HSN Resolver - Web UI")
    st.caption("Database-driven lookup + Google search with bulk file upload support")
    
    # Create tabs
    tab_lookup, tab_bulk, tab_database, tab_training, tab_mapping, tab_settings = st.tabs([
        "Lookup",
        "Bulk Upload",
        "Database",
        "AI Training",
        "Mapping",
        "Settings"
    ])
    
    with tab_lookup:
        _lookup_tab()
    
    with tab_bulk:
        _bulk_upload_tab()
    
    with tab_database:
        _database_tab()
    
    with tab_training:
        _training_tab()
    
    with tab_mapping:
        _mapping_tab()
    
    with tab_settings:
        _settings_tab()


if __name__ == "__main__":
    main()
