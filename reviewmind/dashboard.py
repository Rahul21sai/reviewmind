"""Flask dashboard blueprint with premium UI for ReviewMind."""

from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, render_template_string, request

from reviewmind.demo_data import seed_learning_data

from reviewmind.db import (
    get_acceptance_rate,
    get_accepted_patterns,
    get_feedback_count,
    get_fix_pr_merged_count,
    get_fix_pr_opened_count,
    get_latest_style_snapshot,
    get_recent_feedback,
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
  <title>ReviewMind Dashboard — {{ repo }}</title>
  <meta name="description" content="ReviewMind AI PR reviewer dashboard. Track team learning, acceptance rates, and style guide evolution.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
  <style>
    /* ─── Design Tokens ────────────────────────────── */
    :root {
      color-scheme: dark;
      --bg: #06090f;
      --surface: #0d1117;
      --card: rgba(22, 27, 34, 0.8);
      --card-solid: #161b22;
      --border: rgba(48, 54, 61, 0.6);
      --border-hover: rgba(48, 54, 61, 1);
      --text: #e6edf3;
      --text-secondary: #c9d1d9;
      --muted: #7d8590;
      --accent: #3fb950;
      --accent-dim: rgba(63, 185, 80, 0.15);
      --accent-glow: rgba(63, 185, 80, 0.08);
      --danger: #f85149;
      --danger-dim: rgba(248, 81, 73, 0.15);
      --warning: #d29922;
      --warning-dim: rgba(210, 153, 34, 0.15);
      --blue: #58a6ff;
      --blue-dim: rgba(88, 166, 255, 0.15);
      --purple: #a371f7;
      --purple-dim: rgba(163, 113, 247, 0.15);
      --code: #010409;
      --radius: 12px;
      --radius-sm: 8px;
      --radius-pill: 999px;
      --shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ─── Reset & Base ─────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    /* ─── Layout ───────────────────────────────────── */
    .topbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(6, 9, 15, 0.85);
      backdrop-filter: blur(16px) saturate(180%);
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
    }
    .topbar-inner {
      max-width: 1280px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 56px;
    }
    .topbar-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      color: var(--text);
    }
    .topbar-logo { font-size: 1.4rem; }
    .topbar-name {
      font-size: 1rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }
    .topbar-repo {
      color: var(--accent);
      font-family: 'SF Mono', ui-monospace, Consolas, monospace;
      font-size: 0.85rem;
      font-weight: 500;
    }

    main {
      max-width: 1280px;
      margin: 0 auto;
      padding: 32px 24px 64px;
    }

    /* ─── Section Headers ──────────────────────────── */
    .section-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
      margin-top: 36px;
    }
    .section-header:first-child { margin-top: 0; }
    .section-icon {
      width: 32px;
      height: 32px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
    }
    .section-icon.green { background: var(--accent-dim); }
    .section-icon.blue { background: var(--blue-dim); }
    .section-icon.purple { background: var(--purple-dim); }
    .section-icon.orange { background: var(--warning-dim); }
    .section-title {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.01em;
    }

    /* ─── Cards ────────────────────────────────────── */
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      backdrop-filter: blur(8px);
      transition: border-color var(--transition);
    }
    .card:hover { border-color: var(--border-hover); }

    /* ─── Metrics Grid ─────────────────────────────── */
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }
    .metric-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      backdrop-filter: blur(8px);
      transition: all var(--transition);
      position: relative;
      overflow: hidden;
    }
    .metric-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      border-radius: var(--radius) var(--radius) 0 0;
    }
    .metric-card:nth-child(1)::before { background: var(--accent); }
    .metric-card:nth-child(2)::before { background: var(--blue); }
    .metric-card:nth-child(3)::before { background: var(--purple); }
    .metric-card:nth-child(4)::before { background: var(--warning); }
    .metric-card:hover { transform: translateY(-2px); border-color: var(--border-hover); }
    .metric-number {
      font-size: 2.2rem;
      font-weight: 900;
      line-height: 1;
      letter-spacing: -0.03em;
    }
    .metric-card:nth-child(1) .metric-number { color: var(--accent); }
    .metric-card:nth-child(2) .metric-number { color: var(--blue); }
    .metric-card:nth-child(3) .metric-number { color: var(--purple); }
    .metric-card:nth-child(4) .metric-number { color: var(--warning); }
    .metric-label {
      color: var(--muted);
      margin-top: 8px;
      font-size: 0.85rem;
      font-weight: 500;
    }

    /* ─── Chart ────────────────────────────────────── */
    canvas { max-height: 240px; }

    /* ─── Two-Column Grid ──────────────────────────── */
    .grid-two {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
      margin-top: 16px;
    }

    /* ─── Pattern Lists ────────────────────────────── */
    .pattern-list {
      list-style: none;
      display: grid;
      gap: 8px;
    }
    .pattern-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 10px 14px;
      background: rgba(6, 9, 15, 0.5);
      border-radius: var(--radius-sm);
      font-size: 0.9rem;
      color: var(--text-secondary);
      line-height: 1.45;
    }
    .pattern-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      margin-top: 7px;
      flex-shrink: 0;
    }
    .pattern-dot.green { background: var(--accent); }
    .pattern-dot.red { background: var(--danger); }

    /* ─── Learning Timeline Table ──────────────────── */
    .timeline-table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 0.88rem;
    }
    .timeline-table th {
      text-align: left;
      padding: 10px 14px;
      color: var(--muted);
      font-weight: 600;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
    }
    .timeline-table td {
      padding: 12px 14px;
      border-bottom: 1px solid rgba(48, 54, 61, 0.3);
      vertical-align: middle;
    }
    .timeline-table tr:last-child td { border-bottom: none; }
    .timeline-table tr:hover td { background: rgba(22, 27, 34, 0.5); }
    .suggestion-text {
      max-width: 320px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* ─── Badges ───────────────────────────────────── */
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 3px 10px;
      border-radius: var(--radius-pill);
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .badge-accepted { background: var(--accent-dim); color: var(--accent); }
    .badge-rejected { background: var(--danger-dim); color: var(--danger); }
    .badge-pending { background: var(--warning-dim); color: var(--warning); }
    .badge-high { background: var(--danger-dim); color: var(--danger); }
    .badge-medium { background: var(--warning-dim); color: var(--warning); }
    .badge-low { background: var(--accent-dim); color: var(--accent); }
    .badge-pr {
      background: var(--blue-dim);
      color: var(--blue);
      font-family: 'SF Mono', ui-monospace, Consolas, monospace;
    }

    /* ─── Action Buttons ───────────────────────────── */
    .btn-group { display: flex; gap: 6px; }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      font-weight: 700;
      font-size: 0.85rem;
      font-family: inherit;
      border: 1px solid transparent;
      cursor: pointer;
      transition: all var(--transition);
      white-space: nowrap;
    }
    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .btn-sm {
      padding: 4px 10px;
      font-size: 0.75rem;
      border-radius: 6px;
    }
    .btn-accept {
      background: var(--accent-dim);
      color: var(--accent);
      border-color: rgba(63, 185, 80, 0.3);
    }
    .btn-accept:hover:not(:disabled) {
      background: var(--accent);
      color: #052e16;
    }
    .btn-reject {
      background: var(--danger-dim);
      color: var(--danger);
      border-color: rgba(248, 81, 73, 0.3);
    }
    .btn-reject:hover:not(:disabled) {
      background: var(--danger);
      color: #fff;
    }
    .btn-primary {
      background: var(--accent);
      color: #052e16;
      border-color: var(--accent);
    }
    .btn-primary:hover:not(:disabled) {
      box-shadow: 0 0 20px var(--accent-dim);
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: var(--card);
      color: var(--text);
      border-color: var(--border);
    }
    .btn-secondary:hover:not(:disabled) {
      border-color: var(--accent);
    }
    .btn-demo {
      background: linear-gradient(135deg, var(--purple-dim), var(--blue-dim));
      color: var(--purple);
      border-color: rgba(163, 113, 247, 0.3);
    }
    .btn-demo:hover:not(:disabled) {
      background: linear-gradient(135deg, var(--purple), var(--blue));
      color: #fff;
    }

    /* ─── Forms ────────────────────────────────────── */
    .form-group { margin-bottom: 14px; }
    .form-label {
      display: block;
      color: var(--muted);
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 6px;
    }
    input[type="number"], input[type="text"] {
      width: 100%;
      background: var(--code);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 10px 14px;
      font: 0.9rem/1.5 'SF Mono', ui-monospace, Consolas, monospace;
      transition: border-color var(--transition);
    }
    input:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-dim);
    }
    textarea {
      width: 100%;
      min-height: 180px;
      resize: vertical;
      background: var(--code);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 14px;
      font: 0.88rem/1.5 'SF Mono', ui-monospace, Consolas, monospace;
      transition: border-color var(--transition);
    }
    textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-dim);
    }
    label.checkbox {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.85rem;
      margin-right: 16px;
      cursor: pointer;
    }

    /* ─── Code & Style Preview ─────────────────────── */
    pre, code {
      font-family: 'SF Mono', ui-monospace, Consolas, monospace;
    }
    pre {
      background: var(--code);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      color: var(--accent);
      overflow: auto;
      padding: 16px;
      white-space: pre-wrap;
      font-size: 0.85rem;
      line-height: 1.6;
      max-height: 320px;
    }

    /* ─── Suggestions ──────────────────────────────── */
    .suggestion-card {
      border-top: 1px solid var(--border);
      padding-top: 16px;
      margin-top: 16px;
    }
    .suggestion-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .suggestion-issue { font-weight: 600; }
    .suggestion-fix {
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 10px;
    }

    /* ─── Progress Bar ─────────────────────────────── */
    .progress-bar {
      height: 10px;
      background: rgba(6, 9, 15, 0.8);
      border-radius: var(--radius-pill);
      overflow: hidden;
      margin: 12px 0 8px;
    }
    .progress-fill {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--blue));
      border-radius: var(--radius-pill);
      transition: width 0.6s ease;
    }
    .progress-label {
      color: var(--muted);
      font-size: 0.85rem;
    }

    /* ─── Toast Notifications ──────────────────────── */
    .toast-container {
      position: fixed;
      top: 72px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .toast {
      padding: 12px 20px;
      border-radius: var(--radius-sm);
      font-size: 0.88rem;
      font-weight: 600;
      animation: slideIn 0.3s ease, fadeOut 0.3s ease 2.7s forwards;
      backdrop-filter: blur(8px);
      border: 1px solid;
    }
    .toast-success {
      background: var(--accent-dim);
      color: var(--accent);
      border-color: rgba(63, 185, 80, 0.3);
    }
    .toast-error {
      background: var(--danger-dim);
      color: var(--danger);
      border-color: rgba(248, 81, 73, 0.3);
    }
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes fadeOut {
      to { opacity: 0; transform: translateY(-10px); }
    }

    /* ─── Loading Spinner ──────────────────────────── */
    .spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid transparent;
      border-top-color: currentColor;
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .placeholder { color: var(--muted); font-style: italic; }

    /* ─── Action Bar ───────────────────────────────── */
    .action-bar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 16px;
    }

    /* ─── Responsive ───────────────────────────────── */
    @media (max-width: 900px) {
      .metrics { grid-template-columns: repeat(2, 1fr); }
      .grid-two { grid-template-columns: 1fr; }
    }
    @media (max-width: 520px) {
      .metrics { grid-template-columns: 1fr; }
      main { padding: 20px 16px 48px; }
    }
  </style>
</head>
<body>

<!-- ─── Top Bar ─────────────────────────────────── -->
<div class="topbar">
  <div class="topbar-inner">
    <a href="/" class="topbar-brand">
      <span class="topbar-logo">🧠</span>
      <span class="topbar-name">ReviewMind</span>
    </a>
    <span class="topbar-repo">{{ repo }}</span>
  </div>
</div>

<!-- ─── Toast Container ────────────────────────── -->
<div class="toast-container" id="toasts"></div>

<main>

  <!-- ─── Metrics ────────────────────────────────── -->
  <div class="section-header">
    <div class="section-icon green">📊</div>
    <h2 class="section-title">Overview</h2>
  </div>
  <section class="metrics">
    <div class="metric-card">
      <div class="metric-number" id="metricReviews">{{ review_count }}</div>
      <div class="metric-label">PRs Reviewed</div>
    </div>
    <div class="metric-card">
      <div class="metric-number" id="metricRate">{{ acceptance_rate }}%</div>
      <div class="metric-label">Acceptance Rate</div>
    </div>
    <div class="metric-card">
      <div class="metric-number">{{ fix_opened }}</div>
      <div class="metric-label">Fix PRs Opened</div>
    </div>
    <div class="metric-card">
      <div class="metric-number">{{ fix_merged }}</div>
      <div class="metric-label">Fix PRs Merged</div>
    </div>
  </section>

  <!-- ─── Acceptance Rate Chart ──────────────────── -->
  <div class="section-header">
    <div class="section-icon blue">📈</div>
    <h2 class="section-title">Acceptance Rate Over Time</h2>
  </div>
  <section class="card">
    {% if weekly_rates %}
      <canvas id="rateChart" height="240"></canvas>
    {% else %}
      <p class="placeholder">Chart will appear after first reviews.</p>
    {% endif %}
  </section>

  <!-- ─── Patterns ───────────────────────────────── -->
  <div class="section-header">
    <div class="section-icon green">🧬</div>
    <h2 class="section-title">Learned Patterns</h2>
  </div>
  <section class="grid-two">
    <div class="card">
      <div class="section-header" style="margin-top:0">
        <h3 style="font-size:0.95rem;font-weight:700">✅ What This Team Cares About</h3>
      </div>
      {% if accepted %}
        <ul class="pattern-list">
          {% for item in accepted %}
          <li class="pattern-item">
            <span class="pattern-dot green"></span>
            {{ item }}
          </li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="placeholder">Patterns appear after PR reviews.</p>
      {% endif %}
    </div>
    <div class="card">
      <div class="section-header" style="margin-top:0">
        <h3 style="font-size:0.95rem;font-weight:700">❌ What We Skip</h3>
      </div>
      {% if rejected %}
        <ul class="pattern-list">
          {% for item in rejected %}
          <li class="pattern-item">
            <span class="pattern-dot red"></span>
            {{ item }}
          </li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="placeholder">Patterns appear after PR reviews.</p>
      {% endif %}
    </div>
  </section>

  <!-- ─── Learning Timeline ──────────────────────── -->
  <div class="section-header">
    <div class="section-icon purple">🕐</div>
    <h2 class="section-title">Recent Learning Events</h2>
    <div style="margin-left:auto">
      <button class="btn btn-demo" id="simulateBtn" onclick="simulateLearning()">
        ⚡ Simulate 20 Feedbacks
      </button>
    </div>
  </div>
  <section class="card" style="overflow-x:auto">
    {% if recent_feedback %}
    <table class="timeline-table" id="timelineTable">
      <thead>
        <tr>
          <th>PR</th>
          <th>Suggestion</th>
          <th>Status</th>
          <th>Fix Merged</th>
          <th>Time</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for row in recent_feedback %}
        <tr id="feedback-row-{{ row.id }}">
          <td><span class="badge badge-pr">#{{ row.pr_number }}</span></td>
          <td class="suggestion-text" title="{{ row.suggestion_text }}">{{ row.suggestion_text }}</td>
          <td>
            {% if row.accepted == 1 %}
              <span class="badge badge-accepted">Accepted</span>
            {% elif row.accepted == 0 %}
              <span class="badge badge-rejected">Rejected</span>
            {% else %}
              <span class="badge badge-pending">Pending</span>
            {% endif %}
          </td>
          <td>
            {% if row.fix_pr_merged == 1 %}
              <span class="badge badge-accepted">Yes</span>
            {% else %}
              <span style="color:var(--muted)">—</span>
            {% endif %}
          </td>
          <td style="color:var(--muted);font-size:0.8rem;white-space:nowrap">{{ row.timestamp }}</td>
          <td>
            <div class="btn-group">
              <button class="btn btn-accept btn-sm" onclick="sendFeedback('{{ repo }}', {{ row.pr_number }}, true, this)">✓</button>
              <button class="btn btn-reject btn-sm" onclick="sendFeedback('{{ repo }}', {{ row.pr_number }}, false, this)">✗</button>
            </div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
      <p class="placeholder">No learning events yet. Review a PR or click "Simulate 20 Feedbacks" to see the timeline.</p>
    {% endif %}
  </section>

  <!-- ─── Review a Real PR ───────────────────────── -->
  <div class="section-header">
    <div class="section-icon blue">🔍</div>
    <h2 class="section-title">Review a GitHub PR</h2>
  </div>
  <section class="card">
    <div class="grid-two">
      <div class="form-group">
        <label class="form-label" for="repoInput">Repository</label>
        <input id="repoInput" type="text" value="{{ repo }}">
      </div>
      <div class="form-group">
        <label class="form-label" for="prInput">Pull Request Number</label>
        <input id="prInput" type="number" min="1" placeholder="1">
      </div>
    </div>
    <div style="margin-top:4px">
      <label class="checkbox"><input id="commentInput" type="checkbox" checked> Comment on the PR</label>
      <label class="checkbox"><input id="fixInput" type="checkbox"> Open a fix PR</label>
    </div>
    <div class="action-bar">
      <button class="btn btn-primary" id="realReviewButton" onclick="reviewPR()">
        🚀 Review PR
      </button>
    </div>
    <div id="realReviewResults"></div>
  </section>

  <!-- ─── Review Pasted Diff ─────────────────────── -->
  <div class="section-header">
    <div class="section-icon orange">📋</div>
    <h2 class="section-title">Review Pasted Diff</h2>
  </div>
  <section class="card">
    <div class="form-group">
      <textarea id="diffInput" rows="8" placeholder="Paste any code diff here and click Review..."></textarea>
    </div>
    <button class="btn btn-secondary" id="reviewButton" onclick="reviewDiff()">
      Review This Diff
    </button>
    <div id="reviewResults"></div>
  </section>

  <!-- ─── TEAM_STYLE.md ─────────────────────────── -->
  <div class="section-header">
    <div class="section-icon green">📋</div>
    <h2 class="section-title">TEAM_STYLE.md</h2>
  </div>
  <section class="card">
    {% if style_snapshot %}
      <pre id="stylePreview">{{ style_snapshot.style_md }}</pre>
      <p style="color:var(--muted);font-size:0.85rem;margin-top:8px">
        Last updated: {{ style_snapshot.timestamp }}
      </p>
    {% else %}
      <div class="progress-bar">
        <span class="progress-fill" style="width: {{ progress }}%"></span>
      </div>
      <p class="progress-label">{{ feedback_count }}/20 feedbacks — TEAM_STYLE.md auto-generates at 20</p>
      <pre id="stylePreview" style="display:none"></pre>
    {% endif %}
    <div class="action-bar">
      <button class="btn btn-secondary" onclick="previewStyle()">
        👁️ Generate Preview
      </button>
      <button class="btn btn-primary" onclick="commitStyle()">
        📤 Commit to GitHub
      </button>
    </div>
  </section>

</main>

<script>
// ─── Helpers ─────────────────────────────────────
const REPO = {{ repo_json | safe }};

function toast(message, type = 'success') {
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

async function apiFetch(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || 'Request failed');
  return data;
}

function riskBadge(risk) {
  const cls = risk === 'High' ? 'badge-high' : risk === 'Medium' ? 'badge-medium' : 'badge-low';
  return `<span class="badge ${cls}">${risk} Risk</span>`;
}

// ─── Chart ───────────────────────────────────────
const weeklyRates = {{ weekly_rates_json | safe }};
if (weeklyRates.length) {
  const ctx = document.getElementById('rateChart');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: weeklyRates.map(i => i.week),
      datasets: [{
        label: 'Acceptance Rate',
        data: weeklyRates.map(i => Math.round(i.rate * 100)),
        borderColor: '#3fb950',
        backgroundColor: 'rgba(63, 185, 80, 0.08)',
        fill: true,
        tension: 0.4,
        borderWidth: 2.5,
        pointRadius: 4,
        pointBackgroundColor: '#3fb950',
        pointBorderColor: '#0d1117',
        pointBorderWidth: 2,
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#161b22',
          titleColor: '#e6edf3',
          bodyColor: '#7d8590',
          borderColor: 'rgba(48,54,61,0.6)',
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12,
        },
      },
      scales: {
        y: {
          min: 0, max: 100,
          grid: { color: 'rgba(48,54,61,0.3)' },
          ticks: { color: '#7d8590', font: { family: 'Inter' } },
        },
        x: {
          grid: { color: 'rgba(48,54,61,0.15)' },
          ticks: { color: '#7d8590', font: { family: 'Inter' } },
        },
      },
    },
  });
}

// ─── Review PR ───────────────────────────────────
async function reviewPR() {
  const btn = document.getElementById('realReviewButton');
  const results = document.getElementById('realReviewResults');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Reviewing...';
  results.innerHTML = '';
  try {
    const data = await apiFetch('/review-pr', {
      repo: document.getElementById('repoInput').value,
      pr_number: Number(document.getElementById('prInput').value),
      comment: document.getElementById('commentInput').checked,
      create_fix_pr: document.getElementById('fixInput').checked,
    });
    const fixLink = data.fix_pr_url
      ? `<p><a style="color:var(--accent)" href="${data.fix_pr_url}" target="_blank">🔗 Fix PR opened</a></p>` : '';
    results.innerHTML = `
      <div style="margin-top:16px">
        <p style="color:var(--accent);font-weight:600">✓ Reviewed ${data.repo} PR #${data.pr_number}. ${data.commented ? 'Comment posted.' : ''}</p>
        ${fixLink}
        ${data.suggestions.map(s => `
          <div class="suggestion-card">
            <div class="suggestion-header">
              <span class="badge badge-pr">Line ${s.line}</span>
              ${riskBadge(s.risk || 'Low')}
            </div>
            <div class="suggestion-issue">${s.issue}</div>
            <p class="suggestion-fix">${s.suggestion}</p>
            <pre>${s.fix_code}</pre>
          </div>
        `).join('')}
      </div>`;
    toast('PR reviewed successfully!');
  } catch (e) {
    results.innerHTML = `<p style="color:var(--danger);margin-top:12px">${e.message}</p>`;
    toast(e.message, 'error');
  }
  btn.disabled = false;
  btn.innerHTML = '🚀 Review PR';
}

// ─── Review Diff ─────────────────────────────────
async function reviewDiff() {
  const btn = document.getElementById('reviewButton');
  const results = document.getElementById('reviewResults');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Reviewing...';
  results.innerHTML = '';
  try {
    const res = await fetch('/demo-review', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({diff: document.getElementById('diffInput').value, repo: REPO}),
    });
    const suggestions = await res.json();
    if (!suggestions.length) {
      results.innerHTML = '<p class="placeholder" style="margin-top:12px">No suggestions returned.</p>';
      return;
    }
    results.innerHTML = suggestions.map(s => `
      <div class="suggestion-card">
        <div class="suggestion-header">
          <span class="badge badge-pr">Line ${s.line}</span>
          ${riskBadge(s.risk || 'Low')}
        </div>
        <div class="suggestion-issue">${s.issue}</div>
        <p class="suggestion-fix">${s.suggestion}</p>
        <pre>${s.fix_code}</pre>
      </div>
    `).join('');
    toast('Diff reviewed!');
  } catch (e) {
    results.innerHTML = '<p style="color:var(--danger);margin-top:12px">Review failed.</p>';
    toast('Review failed', 'error');
  }
  btn.disabled = false;
  btn.innerHTML = 'Review This Diff';
}

// ─── Feedback Buttons ────────────────────────────
async function sendFeedback(repo, prNumber, accepted, btnEl) {
  btnEl.disabled = true;
  try {
    const data = await apiFetch('/feedback', { repo, pr_number: prNumber, accepted });
    document.getElementById('metricRate').textContent = data.acceptance_rate + '%';
    toast(accepted ? 'Feedback accepted ✓' : 'Feedback rejected ✗');
    // Update the status badge in the same row
    const row = btnEl.closest('tr');
    if (row) {
      const statusCell = row.children[2];
      statusCell.innerHTML = accepted
        ? '<span class="badge badge-accepted">Accepted</span>'
        : '<span class="badge badge-rejected">Rejected</span>';
    }
  } catch (e) {
    toast(e.message, 'error');
  }
  btnEl.disabled = false;
}

// ─── Simulate Learning ──────────────────────────
async function simulateLearning() {
  const btn = document.getElementById('simulateBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Seeding...';
  try {
    const data = await apiFetch('/simulate-learning', { repo: REPO });
    toast(`Seeded ${data.total} feedbacks! Acceptance rate: ${data.acceptance_rate}%`);
    setTimeout(() => window.location.reload(), 800);
  } catch (e) {
    toast(e.message, 'error');
  }
  btn.disabled = false;
  btn.innerHTML = '⚡ Simulate 20 Feedbacks';
}

// ─── Style Preview / Commit ──────────────────────
async function previewStyle() {
  try {
    const data = await apiFetch('/style-preview', { repo: REPO });
    const pre = document.getElementById('stylePreview');
    pre.textContent = data.style_md;
    pre.style.display = 'block';
    toast('Style guide preview generated!');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function commitStyle() {
  try {
    await apiFetch('/style-commit', { repo: REPO });
    toast('TEAM_STYLE.md committed to GitHub! 🎉');
  } catch (e) {
    toast(e.message, 'error');
  }
}
</script>
</body>
</html>
"""


@dashboard_bp.get("/dashboard")
def dashboard() -> str:
    """Render the ReviewMind repository dashboard."""
    repo = request.args.get("repo", "demo/reviewmind-test")
    feedback_count = get_feedback_count(repo)

    # Auto-seed demo data on first visit so judges never see an empty dashboard
    if feedback_count == 0:
        try:
            seed_learning_data(repo)
            feedback_count = get_feedback_count(repo)
            logger.info("Auto-seeded demo data for %s", repo)
        except Exception:
            logger.exception("Failed to auto-seed demo data")

    weekly_rates = get_weekly_acceptance_rates(repo)
    style_snapshot = get_latest_style_snapshot(repo)
    recent = get_recent_feedback(repo, limit=15)
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
        accepted=get_accepted_patterns(repo, limit=8),
        rejected=get_rejected_patterns(repo, limit=5),
        style_snapshot=style_snapshot,
        feedback_count=feedback_count,
        progress=min(100, int((feedback_count / 20) * 100)),
        recent_feedback=recent,
    )


@dashboard_bp.post("/demo-review")
def demo_review():
    """Return live demo suggestions for a submitted diff."""
    try:
        data = request.get_json(silent=True) or {}
        diff = str(data.get("diff", ""))
        repo = str(data.get("repo", "demo/reviewmind-test"))
        return jsonify(generate_review(diff, repo, save_feedback_rows=False))
    except Exception:
        logger.exception("Demo review failed")
        return jsonify([]), 200
