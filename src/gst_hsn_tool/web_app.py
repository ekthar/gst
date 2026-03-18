"""
GST HSN Resolver - Streamlit Web UI for Azure deployment
Database-driven lookup with bulk file upload support
"""

from __future__ import annotations

import io
import csv
import sys
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
        st.info(f"Searching for '{product_name}'...")
        
        with st.spinner("Searching database and Google..."):
            result = lookup_product_by_name(
                product_name.strip(),
                auto_store=True,
                search_if_not_found=True
            )
        
        if result:
            # Display results
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Product Name", result.get('name', 'N/A'))
            with col2:
                st.metric("Category", result.get('category', 'Not found'))
            with col3:
                st.metric("4-Digit HSN", result.get('hsn_4digit', 'Not found'))
            with col4:
                st.metric("8-Digit HSN", result.get('hsn_8digit', 'Not found'))
            
            # Show match details
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Match Type:** {result.get('match_type', 'Unknown')}")
                if result.get('match_type') == 'fuzzy' or result.get('match_type') == 'keyword':
                    st.write(f"**Confidence:** {result.get('confidence', 'N/A')}%")
            
            with col2:
                if result.get('source_url'):
                    st.write(f"**Source:** [Link]({result['source_url']})")
            
            # Show if it's new
            if result.get('is_new'):
                st.success("✅ Product added to database!")
            else:
                st.info("ℹ️ Product found in database")
        else:
            st.warning("Product not found in database or Google search")


def _bulk_upload_tab() -> None:
    """Bulk upload tab for Excel/CSV files"""
    st.header("📁 Bulk Upload & Lookup")
    
    st.write("Upload a file with product names. We'll lookup HSN codes and store them in the database.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Upload Excel (.xlsx) or CSV file",
            type=["xlsx", "csv"],
            key="bulk_upload"
        )
    
    with col2:
        st.write("")
        st.write("")
        auto_lookup = st.checkbox("Auto lookup 🔍", value=True)
    
    if uploaded_file and auto_lookup:
        try:
            # Read file
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.write(f"📊 Loaded {len(df)} rows from file")
            
            # Show preview
            st.write("**Preview:**")
            st.dataframe(df.head(), use_container_width=True)
            
            # Get product names (assume first column)
            if len(df.columns) > 0:
                product_column = df.columns[0]
                product_names = df[product_column].dropna().astype(str).tolist()
                
                st.write(f"**Products to lookup:** {len(product_names)}")
                
                if st.button("🚀 Run Lookup", use_container_width=True):
                    # Show progress
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(current, total):
                        progress_bar.progress(current / total)
                        status_text.text(f"Progress: {current}/{total}")
                    
                    # Run bulk lookup
                    results = bulk_lookup_products(
                        product_names,
                        auto_store=True,
                        progress_callback=update_progress
                    )
                    
                    progress_bar.progress(1.0)
                    status_text.empty()
                    
                    # Show results
                    st.success(f"✅ Lookup complete! Found {len([r for r in results if r.get('hsn_4digit')])} HSN codes")
                    
                    # Convert to dataframe for display
                    results_df = pd.DataFrame(results)
                    st.dataframe(results_df, use_container_width=True)
                    
                    # Offer download
                    csv_buffer = io.StringIO()
                    results_df.to_csv(csv_buffer, index=False)
                    csv_data = csv_buffer.getvalue()
                    
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv_data,
                        file_name=f"gst_hsn_lookup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    # Also offer Excel format
                    excel_buffer = io.BytesIO()
                    results_df.to_excel(excel_buffer, index=False, sheet_name="HSN Results")
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Results as Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"gst_hsn_lookup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")


def _database_tab() -> None:
    """Database management tab"""
    st.header("🗄️ Database Management")
    
    # Show stats
    total_count = db.get_total_count()
    st.metric("Total Products in Database", total_count)
    
    st.divider()
    
    # View products
    st.subheader("View Products")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_query = st.text_input("Search products by name", placeholder="e.g., Cadbury")
    
    with col2:
        st.write("")
        st.write("")
        limit = st.selectbox("Limit results", [10, 25, 50, 100, 500])
    
    if search_query:
        products = db.search_products(search_query.strip(), limit=limit)
    else:
        products = db.get_all_products(limit=limit)
    
    if products:
        # Convert to dataframe
        df = pd.DataFrame(products)
        # Drop id column for display
        df = df.drop('id', axis=1)
        # Rename columns
        df = df.rename(columns={
            'name': 'Product Name',
            'category': 'Category',
            'hsn_4digit': '4-Digit HSN',
            'hsn_8digit': '8-Digit HSN',
            'source_url': 'Source URL',
            'created_at': 'Created'
        })
        
        st.dataframe(df, use_container_width=True)
        
        # Export option
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.download_button(
            label="📥 Download as CSV",
            data=csv_data,
            file_name=f"gst_hsn_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No products found in database")
    
    st.divider()
    
    # Delete product
    st.subheader("Delete Product")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        product_to_delete = st.text_input("Enter product name to delete", key="delete_product")
    
    with col2:
        st.write("")
        st.write("")
        if st.button("🗑️ Delete", use_container_width=True):
            if product_to_delete:
                success = db.delete_product(product_to_delete.strip())
                if success:
                    st.success(f"✅ Deleted: {product_to_delete}")
                    st.rerun()
                else:
                    st.error(f"Product not found: {product_to_delete}")


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
