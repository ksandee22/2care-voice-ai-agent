# Deploy: GitHub + Render

## Security first

- **Never commit** `.env` or real API keys.
- GitHub **does not accept account passwords** for `git push`. Use a [Personal Access Token (PAT)](https://github.com/settings/tokens) or SSH keys.
- If you shared a password in chat, **change it immediately** on GitHub and email.

---

## 1. Push to GitHub

Install [Git for Windows](https://git-scm.com/download/win) if `git` is not in your PATH.

```powershell
cd voice-ai-agent

git init
git add .
git commit -m "2Care.ai voice AI agent - initial submission"

git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/2care-voice-ai-agent.git
git push -u origin main
```

When prompted for password, use a **GitHub PAT** (scope: `repo`), not your GitHub password.

Create the empty repo first on https://github.com/new (name: `2care-voice-ai-agent`, public, no README).

---

## 2. Deploy on Render

1. Sign in at https://render.com
2. **New +** → **Web Service**
3. Connect GitHub → select `2care-voice-ai-agent`
4. Settings:

| Field | Value |
|-------|--------|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

5. Environment variables:

| Key | Value |
|-----|--------|
| `MOCK_AI` | `true` (recommended for free demo) |
| `OPENAI_API_KEY` | (optional, if not using mock) |
| `REDIS_URL` | (optional, from Render Redis add-on) |

6. Click **Create Web Service**. Wait for build (~3–5 min).

Your public URL:

```text
https://2care-voice-ai-agent.onrender.com
```

(Exact name depends on what you choose in Render.)

---

## 3. Verify deployment

- Health: `https://YOUR-SERVICE.onrender.com/health`
- Swagger: `https://YOUR-SERVICE.onrender.com/docs`
- Demo UI: `https://YOUR-SERVICE.onrender.com/index.html`
- WebSocket: `wss://YOUR-SERVICE.onrender.com/ws/voice`

---

## 4. Submission links to share

```text
GitHub:  https://github.com/YOUR_USERNAME/2care-voice-ai-agent
Live:    https://YOUR-SERVICE.onrender.com
Docs:    https://YOUR-SERVICE.onrender.com/docs
```

---

## Notes

- Free Render services **spin down** after ~15 min idle; first request may take 30–60s.
- Browser microphone needs **HTTPS** — Render provides that automatically.
- SQLite on Render is ephemeral; appointments reset on redeploy (fine for demos).
