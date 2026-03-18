"""GST HSN Resolver Web UI (Local + Azure)."""

from __future__ import annotations

import io
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gst_hsn_tool import db
from gst_hsn_tool.lookup import lookup_product_by_name


def _canonical_name_key(name: str) -> str:
    text = str(name or "").lower().strip()
    text = re.sub(r"\b(rs\.?\s*\d+(?:\.\d+)?)\b", " ", text)
    text = re.sub(r"\b\d+(?:g|gm|kg|ml|l|pcs?)\b", " ", text)
    text = re.sub(r"\b(117|177|217)\b", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _setup_page() -> None:
    st.set_page_config(page_title="GST HSN Resolver", page_icon="G", layout="wide")
    st.markdown(
        """
        <style>
            :root {
                --brand: #006a4e;
                --brand-soft: #e8f4ef;
                --ink: #0f172a;
                --muted: #4b5563;
                --line: #dce4ea;
            }
            .main .block-container {
                max-width: 1180px;
                padding-top: 1.4rem;
                padding-bottom: 2rem;
            }
            .app-hero {
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 14px 16px;
                background: linear-gradient(135deg, #f8fbfa 0%, #eef7f3 100%);
                margin-bottom: 0.8rem;
            }
            .app-hero h1 {
                margin: 0;
                font-size: 1.65rem;
                color: var(--ink);
                line-height: 1.2;
            }
            .app-hero p {
                margin: 0.35rem 0 0 0;
                color: var(--muted);
                font-size: 0.98rem;
            }
            .small-note {
                color: #5b6471;
                font-size: 0.92rem;
            }
            div.stButton > button {
                border-radius: 10px;
                border: 1px solid #c9d7d1;
            }
            div.stDownloadButton > button {
                border-radius: 10px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_load_upload(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    name = (uploaded_file.name or "").lower()
    if name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
    elif name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        raise ValueError("Unsupported file type. Use .xlsx or .csv")

    if df is None or df.empty:
        raise ValueError("Uploaded file is empty.")
    return df


def _extract_product_names(df: pd.DataFrame, selected_column: str) -> list[str]:
    if selected_column not in df.columns:
        return []
    names = df[selected_column].dropna().astype(str).str.strip().tolist()
    return [n for n in names if n]


def _master_file_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "hsn_master_from_gst.csv"


def _run_bulk_lookup_batch(
    product_names: list[str],
    *,
    max_workers: int,
    dedupe_names: bool,
    show_live_details: bool,
    fast_local_first: bool,
    deep_google_all: bool,
    search_if_not_found: bool = True,
    similar_threshold: int = 80,
) -> tuple[list[dict[str, Any]], int]:
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    results_container = st.container()

    all_results: list[dict[str, Any] | None] = [None] * len(product_names)
    success_count = 0
    processed = 0

    key_to_indexes: dict[str, list[int]] = {}
    key_to_name: dict[str, str] = {}
    for idx, raw_name in enumerate(product_names):
        cleaned = str(raw_name).strip()
        canonical = _canonical_name_key(cleaned)
        key_base = canonical if canonical else cleaned.lower()
        key = key_base if dedupe_names else f"{idx}:{key_base}"
        key_to_name.setdefault(key, cleaned)
        key_to_indexes.setdefault(key, []).append(idx)

    effective_fast_local_first = fast_local_first and not deep_google_all
    force_google = deep_google_all

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                lookup_product_by_name,
                key_to_name[key],
                True,
                search_if_not_found,
                force_google,
                effective_fast_local_first,
                similar_threshold,
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
                error_text = str(exc)[:80]

            for row_idx in indexes:
                original_name = str(product_names[row_idx]).strip()
                if result:
                    row = {
                        "input_name": original_name,
                        "matched_name": result.get("matched_name") or result.get("name") or original_name,
                        "category": result.get("category"),
                        "hsn_4digit": result.get("hsn_4digit"),
                        "hsn_8digit": result.get("hsn_8digit"),
                        "source_url": result.get("source_url"),
                        "match_type": result.get("match_type", "unknown"),
                        "confidence": result.get("confidence"),
                        "is_new": result.get("is_new", False),
                    }
                    all_results[row_idx] = row
                    if row["hsn_4digit"]:
                        success_count += 1
                else:
                    all_results[row_idx] = {
                        "input_name": original_name,
                        "matched_name": None,
                        "category": "Error" if error_text else None,
                        "hsn_4digit": None,
                        "hsn_8digit": None,
                        "source_url": None,
                        "match_type": f"error: {error_text}" if error_text else "not_found",
                        "confidence": None,
                        "is_new": False,
                    }
                processed += 1

            progress = processed / max(1, len(product_names))
            progress_bar.progress(progress)
            status_text.text(
                f"Processing {processed}/{len(product_names)} | Resolved {success_count} | Workers {max_workers}"
            )

            if show_live_details:
                with results_container:
                    outcome = result.get("hsn_4digit") if result else "N/A"
                    st.caption(f"{canonical_name} -> HSN {outcome}")

    progress_bar.progress(1.0)
    status_text.empty()
    return [r for r in all_results if r is not None], success_count


def _lookup_tab() -> None:
    st.header("Product HSN Lookup")
    st.caption("Search one product at a time. Results are auto-saved to the local database.")

    col1, col2 = st.columns([3, 1])
    with col1:
        product_name = st.text_input("Product name", placeholder="Example: Parle Monaco, Egg, Rice Jaya")
    with col2:
        do_search = st.button("Run Lookup", use_container_width=True)

    if do_search and product_name.strip():
        with st.spinner("Resolving HSN..."):
            result = lookup_product_by_name(
                product_name.strip(),
                auto_store=True,
                search_if_not_found=True,
                force_google_search=False,
                fast_local_first=True,
                similar_threshold=80,
            )

        if not result:
            st.warning("No HSN found for the provided product name.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Product", str(result.get("name", "")))
        c2.metric("Category", str(result.get("category", "")))
        c3.metric("HSN 4-digit", str(result.get("hsn_4digit", "")))
        c4.metric("HSN 8-digit", str(result.get("hsn_8digit", "")))

        st.write(f"Match type: **{result.get('match_type', 'unknown')}**")
        source_url = result.get("source_url")
        if source_url:
            st.write(f"Source: {source_url}")


def _bulk_upload_tab() -> None:
    st.header("Bulk Upload")
    st.caption("Upload a CSV/XLSX, choose product column, run parallel lookup, and download results.")
    uploaded_file = st.file_uploader("Upload file", type=["xlsx", "csv"], key="bulk_upload")

    if not uploaded_file:
        st.info("Upload a file to begin. The app supports .xlsx and .csv.")
        return

    try:
        df = _safe_load_upload(uploaded_file)
    except Exception as exc:
        st.error(f"Unable to read file: {exc}")
        return

    st.success(f"Loaded {len(df)} rows from {uploaded_file.name}")
    st.dataframe(df.head(10), use_container_width=True)

    column_name = st.selectbox("Product name column", options=list(df.columns), index=0)
    product_names = _extract_product_names(df, column_name)
    if not product_names:
        st.warning("No valid product names found in the selected column.")
        return
    st.info(f"Products queued: {len(product_names)}")

    speed_col1, speed_col2, speed_col3 = st.columns(3)
    with speed_col1:
        max_workers = st.slider("Parallel workers", min_value=2, max_value=24, value=12, step=2)
    with speed_col2:
        dedupe_names = st.checkbox("Deduplicate similar names", value=True)
    with speed_col3:
        show_live_details = st.checkbox("Show per-item live logs", value=False)

    strategy_col1, strategy_col2 = st.columns(2)
    with strategy_col1:
        fast_local_first = st.checkbox("Hybrid fast mode", value=True)
    with strategy_col2:
        deep_google_all = st.checkbox("Deep web search for every item", value=False)

    unresolved_prev = st.session_state.get("bulk_unresolved_names", [])
    st.markdown("### Unresolved Retry Tools")
    status_c1, status_c2 = st.columns(2)
    status_c1.metric("Stored unresolved", len(unresolved_prev))
    if status_c2.button("Clear unresolved list", use_container_width=True):
        st.session_state["bulk_unresolved_names"] = []
        unresolved_prev = []
        st.success("Unresolved list cleared.")

    retry_col1, retry_col2 = st.columns(2)
    with retry_col1:
        if st.button("Retry unresolved with deep web search", disabled=not unresolved_prev, use_container_width=True):
            retry_rows, retry_success = _run_bulk_lookup_batch(
                unresolved_prev,
                max_workers=max_workers,
                dedupe_names=True,
                show_live_details=show_live_details,
                fast_local_first=False,
                deep_google_all=True,
                search_if_not_found=True,
                similar_threshold=80,
            )
            st.success(f"Resolved {retry_success}/{len(unresolved_prev)}")
            st.dataframe(pd.DataFrame(retry_rows), use_container_width=True)
            st.session_state["bulk_unresolved_names"] = [
                str(r.get("input_name", "")).strip()
                for r in retry_rows
                if not str(r.get("hsn_4digit") or "").strip()
            ]

    with retry_col2:
        if st.button("Retry unresolved with relaxed local mode", disabled=not unresolved_prev, use_container_width=True):
            retry_rows, retry_success = _run_bulk_lookup_batch(
                unresolved_prev,
                max_workers=max_workers,
                dedupe_names=True,
                show_live_details=show_live_details,
                fast_local_first=True,
                deep_google_all=False,
                search_if_not_found=False,
                similar_threshold=65,
            )
            st.success(f"Resolved {retry_success}/{len(unresolved_prev)}")
            st.dataframe(pd.DataFrame(retry_rows), use_container_width=True)
            st.session_state["bulk_unresolved_names"] = [
                str(r.get("input_name", "")).strip()
                for r in retry_rows
                if not str(r.get("hsn_4digit") or "").strip()
            ]

    if st.button("Start Bulk Lookup", type="primary", use_container_width=True):
        rows, success_count = _run_bulk_lookup_batch(
            product_names,
            max_workers=max_workers,
            dedupe_names=dedupe_names,
            show_live_details=show_live_details,
            fast_local_first=fast_local_first,
            deep_google_all=deep_google_all,
            search_if_not_found=True,
            similar_threshold=80,
        )

        unresolved_count = sum(1 for r in rows if not str(r.get("hsn_4digit") or "").strip())
        st.success(
            f"Lookup complete. Resolved {success_count}/{len(product_names)} | Unresolved {unresolved_count}"
        )

        results_df = pd.DataFrame(rows)
        st.dataframe(results_df, use_container_width=True)

        unresolved_names = [
            str(r.get("input_name", "")).strip()
            for r in rows
            if not str(r.get("hsn_4digit") or "").strip()
        ]
        st.session_state["bulk_unresolved_names"] = unresolved_names

        c1, c2 = st.columns(2)
        with c1:
            csv_buffer = io.StringIO()
            results_df.to_csv(csv_buffer, index=False)
            st.download_button(
                "Download CSV",
                data=csv_buffer.getvalue(),
                file_name=f"gst_hsn_lookup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with c2:
            excel_buffer = io.BytesIO()
            results_df.to_excel(excel_buffer, index=False, sheet_name="HSN Lookup")
            excel_buffer.seek(0)
            st.download_button(
                "Download Excel",
                data=excel_buffer.getvalue(),
                file_name=f"gst_hsn_lookup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


def _database_tab() -> None:
    st.header("Database")
    st.caption("Browse, search, and export saved products.")

    total_count = db.get_total_count()
    st.metric("Total products", total_count)

    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("Search product name")
    with col2:
        limit = st.selectbox("Max rows", [10, 25, 50, 100, 500, 1000], index=3)

    products = db.search_products(search_query.strip(), limit=limit) if search_query else db.get_all_products(limit=limit)

    if products:
        df = pd.DataFrame(products)
        st.dataframe(df, use_container_width=True, height=450)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            "Download Database CSV",
            data=csv_buffer.getvalue(),
            file_name=f"gst_hsn_db_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("No products found in database.")

    st.divider()
    st.subheader("Danger Zone")
    if st.checkbox("I understand reset deletes all records"):
        if st.button("Reset Database", use_container_width=True):
            db_path = Path(__file__).parent.parent.parent / "data" / "db" / "gst_hsn.db"
            if db_path.exists():
                db_path.unlink()
            db.init_db()
            st.success("Database reset complete")
            st.rerun()


def main() -> None:
    _setup_page()
    st.markdown(
        """
        <section class="app-hero">
            <h1>GST HSN Resolver</h1>
            <p>Fast local-first lookup with web fallback, GST master enrichment, and SQLite persistence.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<p class="small-note">Mode: newest model only (Lookup, Bulk Upload, Database)</p>', unsafe_allow_html=True)

    master_path = _master_file_path()
    if not master_path.exists():
        st.warning(
            "GST master file is missing: data/hsn_master_from_gst.csv. "
            "4-digit HSN lookup will work, but some 8-digit enrichment may remain blank until this file is available."
        )

    tab_lookup, tab_bulk, tab_database = st.tabs(["Lookup", "Bulk Upload", "Database"])
    with tab_lookup:
        _lookup_tab()
    with tab_bulk:
        _bulk_upload_tab()
    with tab_database:
        _database_tab()


if __name__ == "__main__":
    main()
