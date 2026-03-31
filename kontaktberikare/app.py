"""app.py — Streamlit UI for Kontaktberikare. All enrichment logic lives in enricher.py."""
from __future__ import annotations

import io
import time

import pandas as pd
import streamlit as st

from enricher import EnrichmentResult, enrich_company

# ── DataFrame helpers (defined outside main to avoid Streamlit rerun overhead) ─

def _preview_df(results: list[EnrichmentResult], names: list[str]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Företag": name,
            "E-post": r.email or "—",
            "Telefon": r.phone or "—",
            "Webbplats": r.website or "—",
            "Källa": r.source or "—",
        }
        for name, r in zip(names, results)
    ])


def _full_results_df(df: pd.DataFrame, results: list[EnrichmentResult]) -> pd.DataFrame:
    df_out = df.reset_index(drop=True).copy()
    df_out["E-post"] = [r.email for r in results]
    df_out["Telefon"] = [r.phone for r in results]
    df_out["Webbplats"] = [r.website for r in results]
    df_out["Källa"] = [r.source for r in results]
    return df_out


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="Kontaktberikare", page_icon="📧", layout="wide")

    st.markdown(
        "<style>.stApp { max-width: 1100px; margin: 0 auto; }</style>",
        unsafe_allow_html=True,
    )

    st.title("📧 Kontaktberikare")
    st.caption("Ladda upp en Excel-fil med företag och berika listan automatiskt med e-postadresser och telefonnummer.")

    # ── Section 2: File upload ─────────────────────────────────────────────────
    uploaded = st.file_uploader("Ladda upp Excel-fil", type=["xlsx", "xls"])
    if not uploaded:
        st.info("👆 Börja med att ladda upp din fil.")
        st.stop()

    # ── Section 3: Sheet selection + preview ──────────────────────────────────
    xl = pd.ExcelFile(uploaded)
    if len(xl.sheet_names) > 1:
        sheet = st.selectbox("Välj flik", xl.sheet_names)
    else:
        sheet = xl.sheet_names[0]

    df = pd.read_excel(xl, sheet_name=sheet, dtype=str).fillna("")

    st.subheader("Förhandsgranskning")
    st.dataframe(df.head(10), use_container_width=True)
    st.caption(f"{len(df)} rader totalt")

    # ── Section 4: Column mapping ──────────────────────────────────────────────
    st.subheader("Mappa kolumner")
    st.caption("Välj vilka kolumner som innehåller respektive information. Endast företagsnamn är obligatoriskt.")

    NO_COL = "— (använd ej)"
    options = [NO_COL] + list(df.columns)

    col_left, col_right = st.columns(2)
    with col_left:
        name_col = st.selectbox("Företagsnamn *", options)
        city_col = st.selectbox("Stad", options)
    with col_right:
        addr_col = st.selectbox("Adress", options)
        st.selectbox("Organisationsnummer", options)  # reserved for future use

    if name_col == NO_COL:
        st.warning("Välj en kolumn för företagsnamn för att fortsätta.")
        st.stop()

    # ── Section 5: Settings ────────────────────────────────────────────────────
    with st.expander("⚙️ Inställningar"):
        delay = st.slider(
            "Fördröjning mellan sökningar (sekunder)",
            min_value=1.0, max_value=5.0, value=2.5, step=0.5,
            help="Lägre värde = snabbare, men högre risk för att bli rate-limitad av sökmotorn.",
        )
        max_rows = int(st.number_input(
            "Max antal rader att berika (0 = alla)",
            min_value=0, value=0, step=10,
            help="Ange ett lågt antal (t.ex. 5) för att testa innan du kör hela listan.",
        ))

    # ── Section 6: Run enrichment ──────────────────────────────────────────────
    if not st.button("🚀 Starta berikningsprocessen", type="primary", use_container_width=True):
        st.stop()

    df_to_process = df if max_rows == 0 else df.head(max_rows)
    total = len(df_to_process)

    progress_bar = st.progress(0)
    status_text = st.empty()
    preview_placeholder = st.empty()

    results: list[EnrichmentResult] = []
    names_processed: list[str] = []
    found_emails = 0
    found_phones = 0

    for i, (_, row) in enumerate(df_to_process.iterrows()):
        company_name = str(row[name_col]) if name_col != NO_COL else ""
        city = str(row[city_col]) if city_col != NO_COL else ""
        address = str(row[addr_col]) if addr_col != NO_COL else ""

        status_text.text(f"🔍 Söker: {company_name} ({i + 1}/{total})")
        progress_bar.progress(i / total)

        result = enrich_company(name=company_name, city=city, address=address)
        results.append(result)
        names_processed.append(company_name)

        if result.email:
            found_emails += 1
        if result.phone:
            found_phones += 1

        if (i + 1) % 3 == 0 or i + 1 == total:
            preview_placeholder.dataframe(
                _preview_df(results, names_processed),
                use_container_width=True,
            )

        if i < total - 1:
            time.sleep(delay)

    progress_bar.progress(1.0)
    status_text.text("✅ Klart!")

    # ── Section 7: Results + download ─────────────────────────────────────────
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Rader berikade", total)
    with m2:
        pct_email = round(found_emails / total * 100) if total > 0 else 0
        st.metric("E-post hittad", found_emails, delta=f"{pct_email}%")
    with m3:
        pct_phone = round(found_phones / total * 100) if total > 0 else 0
        st.metric("Telefon hittad", found_phones, delta=f"{pct_phone}%")

    df_out = _full_results_df(df_to_process, results)
    st.dataframe(df_out, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_out.to_excel(writer, sheet_name="Berikade kontakter", index=False)
    buffer.seek(0)

    st.download_button(
        label="⬇ Ladda ner Excel",
        data=buffer,
        file_name="berikade_kontakter.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
