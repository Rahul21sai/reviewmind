"""Flask dashboard and live demo routes for ReviewMind."""

from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, render_template_string, request

from reviewmind.db import (
    get_acceptance_rate,
    get_accepted_patterns,
    get_feedback_count,
    get_fix_pr_merged_count,
    get_fix_pr_opened_count,
    get_latest_style_snapshot,
    get_rejected_patterns,
    get_review_count,
    get_weekly_acceptance_rates,
)
from reviewmind.reviewer import generate_review


logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ReviewMind Dashboard</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f172a;
      --card: #1e293b;
      --muted: #94a3b8;
      --text: #e2e8f0;
      --accent: #22c55e;
      --danger: #ef4444;
      --code: #020617;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 36px 0 48px;
    }
    header {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-end;
      margin-bottom: 28px;
    }
    h1 { margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: 0; }
    h2 { margin: 0 0 18px; font-size: 1.15rem; letter-spacing: 0; }
    p { color: var(--muted); margin: 8px 0 0; }
    .repo {
      color: var(--accent);
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      overflow-wrap: anywhere;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .card {
      background: var(--card);
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 8px;
      padding: 18px;
    }
    .metric-number {
      color: var(--accent);
      font-size: 2rem;
      font-weight: 800;
      line-height: 1;
    }
    .metric-label { color: var(--muted); margin-top: 8px; font-size: 0.9rem; }
    .grid-two {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 18px;
    }
    ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
    li {
      background: rgba(15, 23, 42, 0.7);
      border-radius: 8px;
      padding: 10px 12px;
      color: #cbd5e1;
    }
    .green li::before { content: "•"; color: var(--accent); margin-right: 10px; }
    .red li::before { content: "•"; color: var(--danger); margin-right: 10px; }
    textarea {
      width: 100%;
      min-height: 220px;
      resize: vertical;
      background: var(--code);
      color: var(--text);
      border: 1px solid rgba(148, 163, 184, 0.3);
      border-radius: 8px;
      padding: 14px;
      font: 0.95rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    button {
      margin-top: 12px;
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: #052e16;
      font-weight: 800;
      padding: 12px 16px;
      cursor: pointer;
    }
    pre, code {
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    pre {
      background: var(--code);
      border-radius: 8px;
      color: #bbf7d0;
      overflow: auto;
      padding: 14px;
      white-space: pre-wrap;
    }
    .style-pre { max-height: 280px; }
    .suggestion {
      border-top: 1px solid rgba(148, 163, 184, 0.16);
      margin-top: 16px;
      padding-top: 16px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 54px;
      height: 28px;
      border-radius: 999px;
      background: rgba(34, 197, 94, 0.16);
      color: var(--accent);
      font-weight: 800;
      margin-bottom: 10px;
    }
    .progress {
      height: 14px;
      background: #020617;
      border-radius: 999px;
      overflow: hidden;
      margin: 16px 0 10px;
    }
    .progress span { display: block; height: 100%; background: var(--accent); }
    .placeholder { color: var(--muted); }
    canvas { max-height: 220px; }
    @media (max-width: 820px) {
      header, .grid-two { grid-template-columns: 1fr; display: grid; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 520px) {
      .metrics { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>🤖 ReviewMind</h1>
      <p>The PR reviewer that learns your team's taste.</p>
    </div>
    <div class="repo">{{ repo }}</div>
  </header>

  <section class="metrics">
    <div class="card"><div class="metric-number">{{ review_count }}</div><div class="metric-label">Total PRs reviewed</div></div>
    <div class="card"><div class="metric-number">{{ acceptance_rate }}%</div><div class="metric-label">Acceptance rate</div></div>
    <div class="card"><div class="metric-number">{{ fix_opened }}</div><div class="metric-label">Fix PRs opened</div></div>
    <div class="card"><div class="metric-number">{{ fix_merged }}</div><div class="metric-label">Fix PRs merged</div></div>
  </section>

  <section class="card">
    <h2>Acceptance rate over time</h2>
    {% if weekly_rates %}
      <canvas id="rateChart" height="220"></canvas>
    {% else %}
      <p class="placeholder">Chart will appear after first reviews.</p>
    {% endif %}
  </section>

  <section class="grid-two">
    <div class="card">
      <h2>✅ What this team cares about</h2>
      {% if accepted %}
        <ul class="green">{% for item in accepted %}<li>{{ item }}</li>{% endfor %}</ul>
      {% else %}
        <p class="placeholder">Patterns will appear after first PR reviews.</p>
      {% endif %}
    </div>
    <div class="card">
      <h2>❌ What we ignore</h2>
      {% if rejected %}
        <ul class="red">{% for item in rejected %}<li>{{ item }}</li>{% endfor %}</ul>
      {% else %}
        <p class="placeholder">Patterns will appear after first PR reviews.</p>
      {% endif %}
    </div>
  </section>

  <section class="card" style="margin-top:18px">
    <h2>🔬 Try it live</h2>
    <textarea id="diffInput" rows="10" placeholder="Paste any Python diff here and click Review..."></textarea>
    <button id="reviewButton">Review this diff</button>
    <div id="reviewResults"></div>
  </section>

  <section class="card" style="margin-top:18px">
    <h2>TEAM_STYLE.md</h2>
    {% if style_snapshot %}
      <pre class="style-pre">{{ style_snapshot.style_md }}</pre>
      <p>Last updated: {{ style_snapshot.timestamp }}</p>
    {% else %}
      <div class="progress"><span style="width: {{ progress }}%"></span></div>
      <p>{{ feedback_count }}/20 feedbacks collected</p>
      <p>TEAM_STYLE.md will auto-generate at 20 feedbacks</p>
    {% endif %}
  </section>
</main>
<script>
const weeklyRates = {{ weekly_rates_json | safe }};
if (weeklyRates.length) {
  new Chart(document.getElementById('rateChart'), {
    type: 'line',
    data: {
      labels: weeklyRates.map(item => item.week),
      datasets: [{
        label: 'Acceptance rate',
        data: weeklyRates.map(item => Math.round(item.rate * 100)),
        borderColor: '#22c55e',
        backgroundColor: '#22c55e',
        fill: false,
        tension: 0.25
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#94a3b8' } },
        x: { grid: { color: 'rgba(148,163,184,.10)' }, ticks: { color: '#94a3b8' } }
      }
    }
  });
}

document.getElementById('reviewButton').addEventListener('click', async () => {
  const results = document.getElementById('reviewResults');
  results.innerHTML = '<p class="placeholder">Reviewing...</p>';
  try {
    const response = await fetch('/demo-review', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({diff: document.getElementById('diffInput').value, repo: {{ repo_json | safe }}})
    });
    if (!response.ok) throw new Error('Request failed');
    const suggestions = await response.json();
    if (!suggestions.length) {
      results.innerHTML = '<p class="placeholder">No suggestions returned yet.</p>';
      return;
    }
    results.innerHTML = suggestions.map(item => `
      <div class="suggestion">
        <div class="badge">Line ${item.line}</div>
        <div><strong>${item.issue}</strong></div>
        <p>${item.suggestion}</p>
        <pre>${item.fix_code}</pre>
      </div>
    `).join('');
  } catch (error) {
    results.innerHTML = '<p style="color:#fca5a5">Review failed. Please try again.</p>';
  }
});
</script>
</body>
</html>
"""


@dashboard_bp.get("/dashboard")
def dashboard() -> str:
    """Render the ReviewMind repository dashboard."""
    repo = request.args.get("repo", "demo/reviewmind-test")
    feedback_count = get_feedback_count(repo)
    weekly_rates = get_weekly_acceptance_rates(repo)
    style_snapshot = get_latest_style_snapshot(repo)
    return render_template_string(
        HTML_TEMPLATE,
        repo=repo,
        repo_json=json.dumps(repo),
        review_count=get_review_count(repo),
        acceptance_rate=round(get_acceptance_rate(repo) * 100),
        fix_opened=get_fix_pr_opened_count(repo),
        fix_merged=get_fix_pr_merged_count(repo),
        weekly_rates=weekly_rates,
        weekly_rates_json=json.dumps(weekly_rates),
        accepted=get_accepted_patterns(repo, limit=5),
        rejected=get_rejected_patterns(repo, limit=5),
        style_snapshot=style_snapshot,
        feedback_count=feedback_count,
        progress=min(100, int((feedback_count / 20) * 100)),
    )


@dashboard_bp.post("/demo-review")
def demo_review():
    """Return live demo suggestions for a submitted diff."""
    try:
        data = request.get_json(silent=True) or {}
        diff = str(data.get("diff", ""))
        repo = str(data.get("repo", "demo/reviewmind-test"))
        return jsonify(generate_review(diff, repo))
    except Exception:
        logger.exception("Demo review failed")
        return jsonify([]), 200
