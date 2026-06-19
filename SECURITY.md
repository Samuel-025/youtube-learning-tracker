# Security & Privacy

## What stays on your machine

YouTube Learning Tracker is **local-first** — your data never leaves your computer.

| Data | Location | In GitHub? |
|---|---|---|
| Video library | `data/videos.json` | ❌ Never |
| Transcripts | `data/videos.json` | ❌ Never |
| Summaries | `data/videos.json` | ❌ Never |
| Notes | `data/videos.json` | ❌ Never |
| API keys | `.env` | ❌ Never |
| Streamlit secrets | `.streamlit/secrets.toml` | ❌ Never |

All of the above are covered by `.gitignore`.

---

## What IS in GitHub

| File | Contains |
|---|---|
| `.env.example` | Placeholder keys only (no real values) |
| `.streamlit/secrets.toml.example` | Placeholder keys only |
| `data/.gitkeep` | Empty placeholder file only |
| All `*.py` files | Source code only (no personal data) |

---

## If you accidentally commit sensitive data

1. **Revoke the key immediately** — don't wait.
2. Generate a new key from the provider dashboard.
3. Remove the file from git history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   git push origin --force --all
   ```
4. Update `.gitignore` to prevent it happening again.

---

## API Key Safety

- **Never hardcode** API keys in `.py` files.
- Always load from `os.getenv("KEY_NAME")` or `st.secrets["KEY_NAME"]`.
- The `.env` file is gitignored — but double-check before every `git push`.
- Use `git status` before committing to verify no sensitive files are staged.

---

## Pre-push safety check

Run this before every push to verify nothing sensitive is staged:
```bash
git status
git diff --cached --name-only
```

If you see `.env`, `data/*.json`, or `secrets.toml` in the output — **do not push**.
Remove them with:
```bash
git rm --cached .env
git rm --cached data/videos.json
```
