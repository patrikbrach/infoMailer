import time
import streamlit as st
import pandas as pd
from scraper import enrich_row

st.title("Venue Email Enricher")
st.markdown("Ladda upp en CSV med serveringsställen för att automatiskt hämta e-postadresser.")

uploaded = st.file_uploader("Ladda upp CSV", type="csv")

if uploaded:
    try:
        df = pd.read_csv(uploaded, sep=None, engine="python", encoding_errors="replace")
    except Exception as e:
        st.error(f"Kunde inte läsa filen: {e}")
        st.stop()

    missing_cols = [c for c in ["Serveringsställe", "Postort"] if c not in df.columns]
    if missing_cols:
        st.error(f"CSV saknar kolumner: {', '.join(missing_cols)}")
        st.stop()

    st.subheader("Förhandsgranskning")
    st.dataframe(df.head(10))
    st.caption(f"{len(df)} rader totalt")

    if st.button("Starta sökning", type="primary"):
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, row in df.iterrows():
            name = row["Serveringsställe"]
            city = row["Postort"]
            status.text(f"Söker: {name}, {city}  ({i + 1}/{len(df)})")

            email, url = enrich_row(str(name), str(city))
            results.append({"Email": email, "Källa": url})

            progress.progress((i + 1) / len(df))
            # Polite delay to avoid Google rate limits
            time.sleep(1)

        status.empty()
        progress.empty()

        df_out = pd.concat([df, pd.DataFrame(results)], axis=1)

        found = df_out["Email"].notna().sum()
        st.success(f"Klar! Hittade e-post för {found} av {len(df)} ställen.")
        st.dataframe(df_out)

        csv_bytes = df_out.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Ladda ner CSV",
            data=csv_bytes,
            file_name="enriched.csv",
            mime="text/csv",
        )
