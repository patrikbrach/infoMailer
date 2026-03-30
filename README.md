# infoMailer — Venue Email Enricher

Streamlit-app som tar en CSV med serveringsställen, googlar på varje rad, besöker hemsidan och hämtar e-postadresser.

## Kom igång

```bash
cd venue_enricher
pip install -r requirements.txt
streamlit run app.py
```

## Input-format

CSV med minst två kolumner:

| Serveringsställe | Postort |
|---|---|
| Restaurang Exempel | Stockholm |
| Café Testet | Göteborg |

Övriga kolumner bevaras i output-filen.

## Flöde

1. Ladda upp CSV i appen
2. Granska preview
3. Klicka "Starta sökning"
4. Appen googlar varje rad, besöker hemsidan och extraherar e-post
5. Ladda ner enrichad CSV

## Begränsningar

- `googlesearch-python` kan rate-limiteas efter ~50 sökningar. Appen har 1s fördröjning mellan anrop.
- Sidor bakom Cloudflare eller JS-renderade kontaktsidor hittas inte.
- Ingen proxy — kör lokalt eller på server med vanlig IP.
