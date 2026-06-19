# Next-Legend Finder

A football scouting intelligence system that identifies high-potential young players using statistical growth models, mentor matching, and career simulation.

## Features

- **Scouting Board** — Browse and filter prospects with growth scores and player dossiers
- **Career Simulation** — Simulate player development under different environmental scenarios
- **Mentor Lab** — Vector-similarity-based matching with legendary career templates
- **AI Report** — Gemini-powered qualitative advisory (optional)
- **Scouting Notes** — Persistent structured scouting memos per player

## Tech Stack

- **Frontend**: Streamlit
- **Database**: PostgreSQL via Supabase (pgvector for style embeddings)
- **AI**: Google Gemini (optional)
- **Data**: Transfermarkt-based player statistics

## Local Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires a `.streamlit/secrets.toml` file (see `docs/reports/STREAMLIT_DEPLOYMENT_NOTES.md`).

## Streamlit Cloud Deployment

1. Connect this repository in [Streamlit Cloud](https://streamlit.io/cloud)
2. Set **Main file path** to `app.py`
3. Add secrets under **Settings → Secrets** (see `docs/reports/STREAMLIT_DEPLOYMENT_NOTES.md`)

## Project Structure

```
app.py                  # Streamlit entry point
requirements.txt        # Python dependencies
views/                  # Page-level view modules
services/               # Database and data access layer
components/             # Reusable UI components
styles/                 # CSS and theme helpers
docs/
  specs/                # Product specs
  tasks/                # Development task files
  audit/                # QA and audit reports
  reports/              # Implementation and deployment reports
  figures/              # Architecture diagrams
  archive/              # Archived documents
```

## Database Schema Note

Player data is stored in Supabase PostgreSQL. Schema setup is handled by `create_and_upload_db.py`.
The `Database_Project_Dataset/` folder (raw CSVs) is excluded from this repository.
