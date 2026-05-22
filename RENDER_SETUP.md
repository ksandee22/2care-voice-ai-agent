# Render — Where is “Start Command”? (Step-by-step)

## CRITICAL: `backend` folder must be on GitHub

Open https://github.com/ksandee22/2care-voice-ai-agent — you **must** see folders:

- `backend/`
- `agent/`
- `services/`
- `memory/`
- `scheduler/`
- `frontend/`

If you only see `run.py`, `README.md`, `requirements.txt` (no `backend/`), Render **will always fail** with `No module named 'backend'`.

**Fix:** push the full project from your PC (see **Push full code to GitHub** at the bottom).

---

## First: confirm service type

You must have a **Web Service**, not a Static Site.

- Dashboard → your service name
- Under the title it should say **Web Service**
- If it says **Static Site**, delete it and create a new **Web Service**

---

## Method A — Settings (existing service)

1. Open https://dashboard.render.com
2. Click your service: **2care-voice-ai-agent**
3. Left sidebar → click **Settings** (gear icon)
4. Scroll down to the section **Build & Deploy** (or **Deploy**)
5. Look for these fields in order:
   - **Root Directory**
   - **Build Command**
   - **Start Command** ← paste here:

```bash
PYTHONPATH=. uvicorn app:app --host 0.0.0.0 --port $PORT
```

**OR** (if full repo is on GitHub with `backend/` folder):

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

6. Click **Save Changes**
7. Top right → **Manual Deploy** → **Deploy latest commit**

### If you still don’t see “Start Command”

- Scroll the Settings page all the way down (it’s below Build Command)
- Try a wider browser window or zoom out (Ctrl + minus)
- Some accounts show **Commands** instead of separate build/start fields

---

## Method B — Set it when creating the service (easiest)

1. **New +** → **Web Service**
2. Connect GitHub → repo `2care-voice-ai-agent`
3. On the **Create** page (before Create Web Service), you’ll see:
   - Language: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `PYTHON_VERSION` = `3.12.0`
5. Add: `MOCK_AI` = `true`
6. Click **Create Web Service**

---

## Method C — No Start Command field? Use `render.yaml` (Blueprint)

1. Ensure `render.yaml` is in your GitHub repo root (this project includes it)
2. Render Dashboard → **New +** → **Blueprint**
3. Connect the same GitHub repo
4. Render reads `render.yaml` and sets build/start commands automatically
5. Deploy

---

## Method D — `Procfile` (auto-detected)

This repo has a `Procfile`:

```text
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

After you push to GitHub, Render **may** pick this up for Python services.  
Still prefer Method A or B to be sure.

---

## Required environment variables

| Key | Value |
|-----|--------|
| `PYTHON_VERSION` | `3.12.0` |
| `MOCK_AI` | `true` |

Optional: `OPENAI_API_KEY` if you disable mock mode.

---

## Verify success

Open in browser:

```text
https://YOUR-SERVICE-NAME.onrender.com/health
```

Should return JSON with `"status": "running"`.

---

## Push full code to GitHub (required if `backend/` is missing)

In PowerShell:

```powershell
cd "c:\Users\sande\OneDrive\Desktop\2care.ai\voice-ai-agent"

& "C:\Program Files\Git\bin\git.exe" add .
& "C:\Program Files\Git\bin\git.exe" commit -m "Add full application code for Render"
& "C:\Program Files\Git\bin\git.exe" remote add origin https://github.com/ksandee22/2care-voice-ai-agent.git
# If remote exists: git remote set-url origin https://github.com/ksandee22/2care-voice-ai-agent.git

& "C:\Program Files\Git\bin\git.exe" push -u origin main
```

Use a **GitHub Personal Access Token** as password when prompted.

After push, refresh GitHub — confirm `backend/` folder exists. Then on Render: **Manual Deploy → Clear build cache & deploy**.
