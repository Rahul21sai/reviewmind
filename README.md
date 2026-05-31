<div align="center">

# 🧠 ReviewMind

### The AI PR Reviewer That Learns Your Team's Taste

[![Built with OpenAI](https://img.shields.io/badge/Built%20with-OpenAI%20gpt--4o--mini-412991?style=for-the-badge&logo=openai)](https://openai.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**ReviewMind reviews your PRs, learns from your decisions, opens fix branches, and auto-generates your team's coding style guide.**

[Live Demo](https://reviewmind-cul5.onrender.com) · [Dashboard](https://reviewmind-cul5.onrender.com/dashboard?repo=Rahul21sai/reviewmind) · [Setup Status](https://reviewmind-cul5.onrender.com/setup)

</div>

---

## 🔥 The Problem

Generic AI code reviewers don't know your team. They suggest things you don't care about and miss things you do.

- **80% of AI review comments are ignored** by developers
- Static linters check rigid rules but **never adapt** to team preferences
- Style guides get written once and **forgotten in a week**
- Every new team member rediscovers the same patterns

## 💡 How ReviewMind Is Different

Three things no other PR bot does:

| Feature | What It Does | Why It Matters |
|---------|-------------|----------------|
| 🔧 **Opens Fix PRs** | Doesn't just comment — applies the fix in a new branch | One-click to accept a suggestion |
| 📈 **Learns From Merges** | Merge fix = learned pattern. Close = stop suggesting | Gets smarter with every review |
| 📋 **Writes TEAM_STYLE.md** | Auto-commits your team's conventions after 20 feedbacks | Living documentation, always current |

## 🏗️ Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  GitHub PR   │────▶│  Flask Webhook   │────▶│  OpenAI gpt-4o   │
│  (opened)    │     │  Server          │     │  -mini           │
└──────────────┘     └────────┬────────┘     └────────┬─────────┘
                              │                       │
                     ┌────────▼────────┐     ┌────────▼─────────┐
                     │  PyGithub       │     │  Structured      │
                     │  (fetch diff)   │     │  Outputs (JSON)  │
                     └────────┬────────┘     └────────┬─────────┘
                              │                       │
              ┌───────────────┼───────────────────────┘
              │               │
    ┌─────────▼─────┐  ┌─────▼──────────┐  ┌──────────────────┐
    │  PR Comment    │  │  Fix PR        │  │  SQLite/Postgres │
    │  (suggestions) │  │  (auto-apply)  │  │  (memory)        │
    └───────────────┘  └────────────────┘  └────────┬─────────┘
                                                     │
                              ┌───────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Feedback Loop     │
                    │  merge = accept    │
                    │  close = reject    │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  TEAM_STYLE.md     │
                    │  (auto-committed)  │
                    └────────────────────┘
```

## 🔄 How the Learning Loop Works

```
1. Developer opens a PR
2. ReviewMind reviews the diff with gpt-4o-mini
3. Bot comments suggestions + opens a fix PR
4. Developer merges fix PR → patterns marked "accepted"
   Developer closes fix PR → patterns marked "rejected"
5. After 20 feedbacks → TEAM_STYLE.md auto-committed to repo
6. Every future review uses accepted/rejected patterns as context
7. The bot progressively aligns with your team's actual taste
```

## 🚀 Quick Start

```bash
git clone https://github.com/Rahul21sai/reviewmind.git
cd reviewmind
pip install -r requirements.txt
cp .env.example .env  # Fill in your API keys
python -m reviewmind.app
# Visit http://localhost:5000
```

### GitHub Webhook Setup
Settings → Webhooks → Add webhook:
- **URL**: `https://YOUR-URL/webhook`
- **Content type**: `application/json`
- **Secret**: match `GITHUB_WEBHOOK_SECRET` in `.env`
- **Events**: Pull requests + Issue comments

## 📊 Dashboard Features

The interactive dashboard at `/dashboard` includes:

- **Real-time metrics** — PRs reviewed, acceptance rate, fix PRs opened/merged
- **Acceptance rate chart** — visual learning curve over time
- **Learning timeline** — every suggestion with accept/reject buttons
- **Simulate feedbacks** — one-click demo with 20 realistic events
- **PR risk scoring** — High/Medium/Low priority classification
- **Live PR review** — review any GitHub PR directly from the dashboard
- **TEAM_STYLE.md preview** — generate and commit your team's style guide
- **Setup health check** — verify all integrations at `/setup`

## 🤖 OpenAI & Codex Usage

### Runtime AI (Production)
- **gpt-4o-mini** generates code review suggestions via Structured Outputs API
- **gpt-4o-mini** writes TEAM_STYLE.md from accepted/rejected patterns
- **Structured Outputs** (Pydantic schema) guarantees valid JSON responses — no parsing failures
- **In-context learning** — accepted patterns become few-shot examples in every prompt

### Development AI (Building ReviewMind)
- **OpenAI Codex** (via ChatGPT/Codex) was used to architect, implement, debug, and iterate the entire MVP
- **Antigravity IDE** was used for final-stage improvements, dashboard redesign, and deployment
- Codex designed the SQLite schema, Flask route structure, prompt engineering, and webhook flow
- Codex generated the pitch deck script (`generate_deck.py`) and demo data seeder

### Cost
- gpt-4o-mini: **~$0.15 per 1,000 reviews**
- $15 in API credits = **100,000 PR reviews**

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, Flask 3.0 |
| AI Engine | OpenAI gpt-4o-mini, Structured Outputs |
| GitHub Integration | PyGithub |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | Vanilla HTML5, CSS3, Chart.js |
| Deployment | Render, Docker |
| Development | OpenAI Codex, Antigravity IDE |

## 🎯 Target Audience

- Small engineering teams wanting useful AI reviews without generic noise
- Startups that can't afford dedicated code review tooling
- Open-source maintainers enforcing contribution standards
- Fast-moving product teams needing living style documentation

## 📁 Project Structure

```
reviewmind/
├── reviewmind/
│   ├── app.py          # Flask entry point, routes, landing page
│   ├── dashboard.py    # Interactive dashboard UI
│   ├── reviewer.py     # AI review generation with Structured Outputs
│   ├── fixer.py        # Auto fix PR generator
│   ├── feedback.py     # Webhook feedback processor
│   ├── style_writer.py # TEAM_STYLE.md generator
│   ├── demo_data.py    # Realistic demo data seeder
│   ├── db.py           # SQLite/PostgreSQL persistence
│   └── config.py       # Environment configuration
├── Dockerfile
├── render.yaml
├── requirements.txt
├── sample_demo.py      # Offline demo script
└── TEAM_STYLE.md       # Auto-generated style guide
```

## 🏆 Built For

**OpenAI × Outskill AI Builders Hackathon 2026**

Built by **Vudumula Naga Sai Rahul**

---

<div align="center">

*ReviewMind gets smarter with every review. Your team's taste, codified.*

</div>
