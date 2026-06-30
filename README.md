# Crisis Room

A multi-agent incident response simulator built for the Global AI Hackathon Series with Qwen Cloud — **Track 3: Agent Society**.

Four agents — Triage, Fix, Commander, Comms — collaborate (and conflict) under live time pressure to resolve a simulated production incident. The Commander can reject the Fix Agent's proposals and send them back for revision, or escalate high-risk actions to a human operator who must approve or deny them before anything proceeds.

## Why this is Agent Society, not a chatbot wrapper

- **Real disagreement, not scripted dialogue.** The Fix Agent proposes actions independently; the Commander independently evaluates and can reject them, forcing a genuine second round with no human-authored script dictating the outcome.
- **Escalating severity changes agent behavior.** As the clock runs past the threshold, severity escalates and the Commander's prompt context shifts — visible in its reasoning, not just a label change.
- **Human-in-the-loop checkpoint.** HIGH-risk actions never auto-execute. The simulation genuinely pauses (via an `asyncio.Future`) until a human responds through the UI.

## Architecture

```
┌─────────────┐      SSE stream       ┌──────────────────┐
│  Frontend    │◄──────────────────────│   FastAPI backend │
│ (index.html) │  POST /approve  ─────►│   (main.py)        │
└─────────────┘                        └─────────┬─────────┘
                                                   │
                         ┌─────────────────────────┼─────────────────────────┐
                         ▼                         ▼                         ▼
                  ┌─────────────┐         ┌─────────────┐           ┌─────────────┐
                  │   Triage    │         │     Fix     │           │  Commander   │
                  │   Agent     │────────►│    Agent    │──────────►│    Agent     │
                  └─────────────┘         └─────────────┘           └──────┬───────┘
                                                  ▲                          │
                                                  │ REJECT (revise)          │ ESCALATE
                                                  └──────────────────────────┘
                                                                              │
                                                                       Human approval
                                                                              │
                                                                              ▼
                                                                       ┌─────────────┐
                                                                       │    Comms    │
                                                                       │    Agent    │
                                                                       └─────────────┘

All agents call Qwen Cloud (qwen-max / qwen-plus) via the OpenAI-compatible endpoint:
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

## Project structure

```
crisis-room/
├── .gitignore
├── .env.example          # copy to .env, fill in your real key — .env is git-ignored
├── LICENSE                # MIT — required for the public repo OSS license
├── README.md
├── docker-compose.yml      # run backend + frontend together
├── backend/
│   ├── main.py             # FastAPI app, SSE orchestration, human-approval endpoint
│   ├── agents.py           # Triage / Fix / Commander / Comms agent calls to Qwen Cloud
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
└── frontend/
    ├── index.html           # single-file UI (radar clock, live feed, approvals)
    ├── Dockerfile
    ├── nginx.conf
    └── docker-entrypoint.sh # injects API_BASE into index.html at container start
```

## Setup — Option A: Docker (recommended, works the same on Codespaces or any machine)

1. Copy the env template and fill in your real key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```
   QWEN_API_KEY=your-real-key-from-home.qwencloud.com
   ```
   `.env` is listed in `.gitignore` — it will never be committed, even if you `git add .`.

2. Build and run both services:
   ```bash
   docker compose up --build
   ```
3. Backend is live at `http://localhost:8000`, frontend at `http://localhost:5500`.
4. In Codespaces, forward both ports (8000 and 5500) as **Public**, and set `API_BASE` in `.env` to your forwarded port-8000 URL before running, so the containerized frontend points at the right backend.

To stop: `docker compose down`

## Setup — Option B: Without Docker (GitHub Codespaces / browser-based)

1. Push this folder to a GitHub repo, open it in **Codespaces**.
2. Backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   export QWEN_API_KEY="your-key-from-home.qwencloud.com"
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Forward port 8000 (Codespaces does this automatically — make it **Public** so the frontend can reach it).
4. Frontend: open `frontend/index.html` in the Codespaces browser preview, or serve it:
   ```bash
   cd frontend
   python3 -m http.server 5500
   ```
5. In `index.html`, set `window.API_BASE` to your forwarded Codespaces port-8000 URL if not running on localhost.
6. Click **Trigger Incident**.

## Deploying the backend to Alibaba Cloud (required for submission proof)

Simplest path for the deployment proof requirement:
1. Use **Alibaba Cloud Function Compute** (serverless) or a small **ECS** free-tier instance.
2. **If using ECS:** install Docker, `git clone` your repo, then `docker compose up --build -d` (the `-d` keeps it running after you disconnect — no need for screen/tmux). Set your real `QWEN_API_KEY` in `.env` on the server, never in committed files.
   **If using Function Compute:** deploy `backend/` directly with its `requirements.txt`; set `QWEN_API_KEY` as a Function Compute environment variable in the console, not in code.
3. Record a short screen capture showing the service running on the Alibaba Cloud console (instance/function page) AND a successful API call against the public Alibaba Cloud URL — this is your "Proof of Alibaba Cloud Deployment" video.
4. Point `index.html`'s `API_BASE` (or the `API_BASE` env var if using Docker) at that public URL for your main demo video too.

## Submission checklist

- [ ] Public GitHub repo with OSS license visible in the About section
- [ ] Architecture diagram (use the one above, or redraw it cleanly — e.g. in Excalidraw)
- [ ] Proof-of-Alibaba-Cloud-deployment video (separate, short)
- [ ] ~3 min demo video: trigger an incident, show a REJECT round, show a human-approval pause, show resolution
- [ ] Project description explaining Track 3 fit
- [ ] Tag the submission: Productivity, Design, Machine Learning/AI
- [ ] Identify Track 3: Agent Society in the submission form

## Model tiering

- `qwen-max` (or your chosen reasoning-tier model) — Triage and Commander, where judgment quality matters most
- `qwen-plus` — Fix and Comms, higher-frequency, lower-stakes generations

Check `/mnt/skills` model-selection doc / the hackathon's "Choose Your Model" guide to confirm exact current model IDs available on your account, and adjust `QWEN_FAST_MODEL` / `QWEN_REASONING_MODEL` env vars accordingly.
