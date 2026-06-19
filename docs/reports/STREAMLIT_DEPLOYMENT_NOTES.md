# Streamlit Cloud Deployment Notes

## Deployment Steps

1. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud) and sign in with GitHub
2. Click **New app**
3. Select the repository: `Database_Project` (or your GitHub repo name)
4. Set **Branch**: `main`
5. Set **Main file path**: `app.py`
6. Click **Advanced settings** → **Secrets**
7. Add the secrets listed below, then click **Deploy**

## Required Secrets

In Streamlit Cloud **Settings → Secrets**, add the following (TOML format).
Replace placeholder values with your actual credentials — never commit real values to git.

```toml
SUPABASE_URL = "your-supabase-project-url"
SUPABASE_KEY = "your-supabase-anon-key"
```

## Optional Secrets

```toml
GEMINI_API_KEY = "your-gemini-api-key"
```

If `GEMINI_API_KEY` is not provided, the AI Report and Gemini advisory features will be disabled gracefully.

## Local Development Secrets

For local development, create `.streamlit/secrets.toml` (this file is gitignored):

```toml
SUPABASE_URL = "your-supabase-project-url"
SUPABASE_KEY = "your-supabase-anon-key"
GEMINI_API_KEY = "your-gemini-api-key"
```

## Streamlit Configuration

`.streamlit/config.toml` is committed and sets the dark theme automatically. No additional theme configuration is needed in Streamlit Cloud.

## Notes

- `Database_Project_Dataset/` (raw CSV data) is gitignored; it is not needed at runtime since all data lives in Supabase.
- `__pycache__/`, `*.pyc`, `*.log` are gitignored and should not appear in the repo.
- The app requires a live Supabase connection; it will not function without valid `SUPABASE_URL` and `SUPABASE_KEY`.
