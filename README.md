# ReviewMind
> The PR reviewer that learns your team's taste.

ReviewMind reviews your PRs, opens fix branches with changes applied, and gets smarter every time you accept or reject its suggestions.

## The problem
Generic AI code reviewers don't know your team. They suggest things you don't care about and miss things you do. Developers ignore 80% of their comments.

## How ReviewMind is different
Three things no other PR bot does:

1. Opens a fix PR — doesn't just comment, applies the fix
2. Learns from merges — accepted = learn it, rejected = stop suggesting it
3. Writes TEAM_STYLE.md — auto-commits your team's conventions after 20 feedbacks

## Setup in 5 steps
1. `git clone this repo && cd reviewmind`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` — fill in your API keys
4. `ngrok http 5000` — copy the HTTPS URL
5. `python app.py` — visit `localhost:5000/dashboard`

## GitHub webhook setup
Settings → Webhooks → Add webhook

- URL: `https://YOUR-NGROK-URL/webhook`
- Content type: `application/json`
- Secret: match `GITHUB_WEBHOOK_SECRET` in `.env`
- Events: Pull requests + Issue comments

## How the learning works
ReviewMind stores every suggestion it makes. When a developer merges the auto-generated fix PR, those patterns are marked accepted. Close without merging and they're marked rejected. After 20 feedbacks, ReviewMind auto-commits TEAM_STYLE.md to your repo. Every future review uses your accepted patterns as few-shot examples — the bot progressively aligns with your team's actual taste.

## Try the demo
```bash
python sample_demo.py
```

## Cost
gpt-4o-mini: ~$0.15 per 1,000 reviews.
$15 in API credits = 100,000 PR reviews.

## Built with
- OpenAI Codex + gpt-4o-mini
- Flask + SQLite
- PyGithub
- Built during OpenAI × Outskill Hackathon 2026
