# Pre-push Security Checklist

Run this quick check before every `git push`:

```bash
# 1. Check what's staged
git status
git diff --cached --name-only
```

**These files must NEVER appear in the output:**
- [ ] `.env`
- [ ] `data/videos.json` or any `data/*.json`
- [ ] `.streamlit/secrets.toml`
- [ ] Any file containing real API keys
- [ ] Any `*.log` files
- [ ] Any `*.db` or `*.sqlite` files

If any appear, remove them:
```bash
git rm --cached <filename>
```

Then re-check with `git status` before pushing.
