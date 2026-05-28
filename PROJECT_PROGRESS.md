# ReviewMind Project Progress

## Project Summary

ReviewMind is an AI-powered GitHub PR reviewer that learns a team's coding preferences over time. It reviews pull request diffs, comments suggestions, stores feedback, tracks accepted and rejected patterns, and generates a `TEAM_STYLE.md` file once enough feedback is collected.

Repository:

```text
https://github.com/Rahul21sai/reviewmind
```

## What Has Been Built

### 1. Initial Python Project Setup

Created the base Python project structure:

```text
reviewmind/
  __init__.py
.env.example
requirements.txt
```

Added dependencies:

```text
flask>=3.0.0
openai>=1.0.0
PyGithub>=2.1.1
python-dotenv>=1.0.0
requests>=2.31.0
```

### 2. SQLite Database Layer

Created `reviewmind/db.py`.

It manages:

- `feedback`
- `reviews`
- `style_snapshots`

Implemented helpers for:

- saving feedback
- saving reviews
- fetching accepted patterns
- fetching rejected patterns
- calculating acceptance rate
- counting reviews and feedback
- tracking weekly acceptance rates
- saving generated style guide snapshots

### 3. Configuration

Created `reviewmind/config.py`.

It loads environment variables from `.env`:

```text
OPENAI_API_KEY
GITHUB_TOKEN
GITHUB_WEBHOOK_SECRET
PORT
```

Also defines project constants:

```text
MODEL = "gpt-4o-mini"
MAX_SUGGESTIONS = 5
MIN_FEEDBACK_FOR_STYLE = 20
FIX_BRANCH_PREFIX = "reviewmind/fix-pr-"
STYLE_FILE_NAME = "TEAM_STYLE.md"
DB_PATH = "reviewmind.db"
```

### 4. AI Reviewer Logic

Created `reviewmind/reviewer.py`.

It:

- reads accepted and rejected team patterns from SQLite
- builds an OpenAI review prompt
- sends PR diffs to `gpt-4o-mini`
- parses JSON suggestions
- saves generated feedback
- formats suggestions as a GitHub PR comment

### 5. Auto Fix PR Generator

Created `reviewmind/fixer.py`.

It:

- connects to GitHub using PyGithub
- creates a fix branch like `reviewmind/fix-pr-{pr_number}`
- attempts simple code replacements
- opens a GitHub fix PR
- comments back on the original PR

### 6. Feedback Processor

Created `reviewmind/feedback.py`.

It handles:

- fix PR closed/merged events
- manual comments like:

```text
reviewmind accept
reviewmind reject
```

It updates stored feedback so ReviewMind can learn from developer decisions.

### 7. TEAM_STYLE.md Generator

Created `reviewmind/style_writer.py`.

It:

- checks when at least 20 feedback rows exist
- gathers accepted and rejected patterns
- calls OpenAI to generate a team style guide
- commits `TEAM_STYLE.md` to GitHub
- stores a local style snapshot in SQLite

Generated file:

```text
TEAM_STYLE.md
```

GitHub link:

```text
https://github.com/Rahul21sai/reviewmind/blob/main/TEAM_STYLE.md
```

### 8. Flask Dashboard

Created `reviewmind/dashboard.py`.

Dashboard URL:

```text
http://localhost:5000/dashboard?repo=Rahul21sai/reviewmind
```

The dashboard shows:

- total PRs reviewed
- acceptance rate
- fix PRs opened
- fix PRs merged
- acceptance rate chart
- accepted patterns
- rejected patterns
- latest `TEAM_STYLE.md`
- real GitHub PR review form
- pasted diff review form

### 9. Flask App And Webhook Server

Created `reviewmind/app.py`.

Routes:

```text
GET  /health
GET  /dashboard?repo=owner/repo
POST /demo-review
POST /review-pr
POST /webhook
```

The app can:

- verify GitHub webhook signatures
- process PR open/reopen/synchronize events
- process issue comments
- review a real GitHub PR from the dashboard
- post ReviewMind comments to GitHub
- save review history locally

### 10. Demo Script

Created `sample_demo.py`.

It is a local demo script that:

- seeds fake accepted/rejected learning patterns
- prints mock review suggestions
- previews what `TEAM_STYLE.md` would look like

This is useful for screen recording when API keys or webhooks are not available.

### 11. Real-Time MVP Flow

Added a real PR review flow.

From the dashboard, ReviewMind can now:

1. accept a real repository name
2. accept a real PR number
3. fetch the PR diff from GitHub
4. call OpenAI
5. generate review suggestions
6. optionally comment on the PR
7. optionally create a fix PR
8. save review and feedback rows
9. update dashboard metrics

Endpoint:

```text
POST /review-pr
```

### 12. GitHub Push

The project was pushed to:

```text
https://github.com/Rahul21sai/reviewmind
```

Latest major pushed commit:

```text
feat: add real-time PR review MVP flow
```

## Real PR Test Completed

Test PR:

```text
https://github.com/Rahul21sai/reviewmind/pull/1
```

ReviewMind successfully:

- loaded `.env` keys
- fetched the real PR diff
- called OpenAI
- generated a review suggestion
- posted a ReviewMind comment on the PR
- saved review and feedback rows into `reviewmind.db`

## Learning Data Created

Created 20 learning review/feedback records for:

```text
Rahul21sai/reviewmind
```

Current local dashboard data:

```text
Reviews: 22
Feedback rows: 22
Acceptance rate: 68%
Fix PRs opened: 15
Fix PRs merged: 15
TEAM_STYLE.md generated: yes
```

## Important Security Note

Real keys must only be stored in:

```text
.env
```

Never put real keys in:

```text
.env.example
README.md
GitHub commits
screenshots
videos
```

`.env.example` should contain only placeholders:

```text
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=github_pat_...
GITHUB_WEBHOOK_SECRET=your-secret-here
PORT=5000
```

## How To Run Locally

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
python -m reviewmind.app
```

Open dashboard:

```text
http://localhost:5000/dashboard?repo=Rahul21sai/reviewmind
```

Run local demo:

```powershell
python sample_demo.py
```

## How To Test Real PR Review

1. Create or open a GitHub PR.
2. Start the Flask app.
3. Open the dashboard.
4. Enter:

```text
Repository: Rahul21sai/reviewmind
Pull request number: 1
```

5. Keep `Comment on the PR` checked.
6. Keep `Try to open a fix PR` unchecked for the first test.
7. Click `Review real PR`.

ReviewMind should comment on the PR and update the dashboard.

## Current MVP Status

ReviewMind now has a working Phase 1 MVP:

- real GitHub PR review flow
- OpenAI-powered review suggestions
- local learning memory
- dashboard metrics
- GitHub PR comments
- generated `TEAM_STYLE.md`
- demo script for backup recording

This is ready to show as a hackathon Phase 1 working MVP.
