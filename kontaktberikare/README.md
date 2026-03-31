# Kontaktberikare

Streamlit-app som berikar en Excel-lista med svenska företag med e-postadresser och telefonnummer, helt automatiskt och utan API-nycklar.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Cloud

1. Push repot till GitHub.
2. Gå till [share.streamlit.io](https://share.streamlit.io) och koppla repot.
3. Sätt **Main file path** till `kontaktberikare/app.py`.
4. Klicka Deploy — Streamlit Cloud hittar `requirements.txt` automatiskt.

## How It Works

Berikningspipelinen kör tre steg per rad:

1. **Hitta webbplats** — DuckDuckGo-sökning på företagsnamn + ort. Filtrerar bort katalogsidor (hitta.se, eniro.se, etc.) och returnerar första egna domän.
2. **Skrapa webbplats** — Hämtar startsidan och upp till 5 kontaktsidor (`/kontakt`, `/om-oss`, etc.). Extraherar e-post via `mailto:`-länkar och regex, telefon via `tel:`-länkar och regex.
3. **Fallback-sökning** — Om ingen e-post hittades, söker DuckDuckGo specifikt efter kontaktuppgifter och skannar söksnippetarna.

## Limitations

- DuckDuckGo kan rate-limita vid hög belastning. Använd fördröjningsinställningen (standard 2,5 s).
- Sidor med JavaScript-renderat innehåll eller Cloudflare-skydd kan inte skrapas.
- Förväntad träfffrekvens: 50–70 % beroende på bransch och hur digitala företagen är.
