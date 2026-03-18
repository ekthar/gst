from __future__ import annotations

from pathlib import Path

import streamlit as st

from gst_hsn_tool.config import (
    LEARNING_DB_PATH,
    TRAINING_CORPUS_FILE,
    TRAINING_GOOGLE_PRODUCTS_FILE,
    TRAINING_GOOGLE_QUERIES_FILE,
)
from gst_hsn_tool.pipeline import run_pipeline
from gst_hsn_tool.training import run_training_mode


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
        page_title="GST HSN Resolver Web",
        page_icon="??",
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
        .stApp {
            background:
                radial-gradient(circle at 12% 10%, #ffe8de 0%, transparent 22%),
                radial-gradient(circle at 88% 8%, #ffe6d8 0%, transparent 24%),
                linear-gradient(180deg, #fff8f5 0%, #fff4ef 100%);
        }
        .block-container {
            max-width: 1200px;
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            color: var(--text);
            letter-spacing: 0.2px;
        }
        .badge {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            border: 1px solid var(--line);
            background: #fff0ea;
            color: #62485e;
            font-size: 12px;
            margin-bottom: 8px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 14px 16px;
        }
        .muted { color: var(--muted); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _mapping_tab() -> None:
    st.markdown('<div class="badge">Mapping</div>', unsafe_allow_html=True)
    st.markdown("### Run Product Mapping")

    c1, c2, c3 = st.columns(3)
    with c1:
        client_input = st.text_input("Client input (csv/xlsx/xls)", value="data/client_input_template.csv")
    with c2:
        master_input = st.text_input("HSN master (csv/xlsx/xls)", value="data/hsn_master_from_gst.csv")
    with c3:
        output_input = st.text_input("Output path (.xlsx/.csv)", value="data/output_result.xlsx")

    if st.button("Run Mapping", type="primary", use_container_width=False):
        with st.spinner("Running mapping..."):
            try:
                summary = run_pipeline(
                    client_path=Path(client_input.strip()),
                    hsn_master_path=Path(master_input.strip()),
                    output_path=Path(output_input.strip()),
                )
            except Exception as exc:
                st.error(f"Mapping failed: {exc}")
            else:
                st.success("Mapping completed")
                st.json(summary)


def _training_tab() -> None:
    st.markdown('<div class="badge">AI Training</div>', unsafe_allow_html=True)
    st.markdown("### Run Google-Only Training")

    default_master = "data/hsn_master_from_gst.csv"
    master_path = st.text_input("Master path (optional)", value=default_master)

    log_box = st.empty()

    if st.button("Run Training", type="primary", use_container_width=False):
        logs: list[str] = []

        def logger(msg: str) -> None:
            logs.append(msg)
            log_box.text("\n".join(logs[-80:]))

        with st.spinner("Running training mode..."):
            try:
                master = Path(master_path.strip()) if master_path.strip() else None
                summary = run_training_mode(current_master_path=master, logger=logger)
            except Exception as exc:
                st.error(f"Training failed: {exc}")
            else:
                st.success("Training completed")
                st.json(summary)


def _settings_tab() -> None:
    st.markdown('<div class="badge">Google Inputs</div>', unsafe_allow_html=True)
    st.markdown("### Edit Google Queries and Product Names")
    st.markdown('<div class="muted">Only Google-discovered links are used for learning.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        q_text = st.text_area(
            "Google search queries",
            value=_read_text(TRAINING_GOOGLE_QUERIES_FILE),
            height=320,
        )
        if st.button("Save Queries"):
            _write_text(TRAINING_GOOGLE_QUERIES_FILE, q_text)
            st.success(f"Saved: {TRAINING_GOOGLE_QUERIES_FILE}")

    with c2:
        p_text = st.text_area(
            "Product names (one per line)",
            value=_read_text(TRAINING_GOOGLE_PRODUCTS_FILE),
            height=320,
        )
        if st.button("Save Products"):
            _write_text(TRAINING_GOOGLE_PRODUCTS_FILE, p_text)
            st.success(f"Saved: {TRAINING_GOOGLE_PRODUCTS_FILE}")

    st.markdown("### Data Paths")
    st.code(
        "\n".join(
            [
                f"Learning DB: {LEARNING_DB_PATH}",
                f"Training corpus: {TRAINING_CORPUS_FILE}",
                f"Google queries: {TRAINING_GOOGLE_QUERIES_FILE}",
                f"Google products: {TRAINING_GOOGLE_PRODUCTS_FILE}",
            ]
        )
    )


def main() -> None:
    _setup_page()
    st.title("GST HSN Resolver - Azure Web UI")
    st.caption("Use this on Linux Azure via browser. Mapping + Google-only training are both supported.")

    tab_map, tab_train, tab_settings = st.tabs(["Mapping", "AI Training", "Google Inputs"])
    with tab_map:
        _mapping_tab()
    with tab_train:
        _training_tab()
    with tab_settings:
        _settings_tab()


if __name__ == "__main__":
    main()
