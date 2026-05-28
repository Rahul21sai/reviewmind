"""Script to generate a 4-page PDF pitch deck for ReviewMind."""

import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def draw_slide_background(canvas, doc):
    """Draw a dark modern tech background for each slide."""
    canvas.saveState()
    
    # 1. Base Dark Background (Slate-900)
    canvas.setFillColor(colors.HexColor("#0f172a"))
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    # 2. Subtle decorative top accent line (Green-500)
    canvas.setFillColor(colors.HexColor("#22c55e"))
    canvas.rect(0, doc.pagesize[1] - 8, doc.pagesize[0], 8, fill=True, stroke=False)
    
    if canvas._pageNumber == 1:
        # Title slide decoration
        canvas.setFillColor(colors.HexColor("#1e293b")) # Slate-800
        # Draw a large decorative dark panel on the left side
        canvas.rect(0, 0, 18, doc.pagesize[1], fill=True, stroke=False)
        canvas.setFillColor(colors.HexColor("#22c55e"))
        canvas.rect(18, 0, 6, doc.pagesize[1], fill=True, stroke=False)
    else:
        # Standard slide footer
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#94a3b8")) # Muted
        canvas.drawString(36, 24, "ReviewMind | Phase 1 MVP Submission")
        canvas.drawRightString(doc.pagesize[0] - 36, 24, f"Slide {canvas._pageNumber} of 4")
        
    canvas.restoreState()

def build_pdf():
    # Setup document in Landscape mode (11 x 8.5 inches = 792 x 612 pt)
    pdf_filename = "reviewmind_pitch_deck.pdf"
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=44,
        bottomMargin=44
    )
    
    styles = getSampleStyleSheet()
    
    # 1. Custom Typography Style Definitions
    normal_style = styles['Normal']
    normal_style.textColor = colors.HexColor("#e2e8f0") # Slate-200
    normal_style.fontSize = 10.5
    normal_style.leading = 15
    
    # Slide 1 (Title) Styles
    main_title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=38,
        leading=46,
        textColor=colors.white,
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#22c55e"), # Green-500
        spaceAfter=30
    )
    
    title_meta_label = ParagraphStyle(
        'TitleMetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#94a3b8")
    )
    
    title_meta_val = ParagraphStyle(
        'TitleMetaVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.white
    )
    
    # Slide Header Style
    slide_title_style = ParagraphStyle(
        'SlideTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#22c55e"),
        spaceAfter=8
    )
    
    slide_desc_style = ParagraphStyle(
        'SlideDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=17,
        textColor=colors.HexColor("#94a3b8"),
        spaceAfter=20
    )
    
    # Card Content Styles
    card_title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.white,
        spaceAfter=8
    )
    
    card_text_style = ParagraphStyle(
        'CardText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=colors.HexColor("#cbd5e1")
    )
    
    card_bullet_style = ParagraphStyle(
        'CardBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#cbd5e1"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=6
    )
    
    story = []
    
    # ==========================================
    # SLIDE 1: Title & Concept Introduction
    # ==========================================
    story.append(Spacer(1, 100))
    story.append(Paragraph("ReviewMind", main_title_style))
    story.append(Paragraph("AI-Powered PR Reviewer That Learns Your Team's Coding Taste", subtitle_style))
    story.append(Spacer(1, 20))
    
    # Metadata Box at the bottom of the title slide
    meta_data = [
        [
            Paragraph("PRODUCT TYPE:", title_meta_label),
            Paragraph("AI-Powered GitHub Agent", title_meta_val),
            Paragraph("BUILDER:", title_meta_label),
            Paragraph("Vudumula Naga Sai Rahul", title_meta_val)
        ],
        [
            Paragraph("SUBMISSION:", title_meta_label),
            Paragraph("Phase 1 Working MVP", title_meta_val),
            Paragraph("GITHUB REPO:", title_meta_label),
            Paragraph("Rahul21sai/reviewmind", title_meta_val)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[100, 220, 100, 220])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(PageBreak())
    
    # ==========================================
    # SLIDE 2: The Problem (Pain Points)
    # ==========================================
    story.append(Paragraph("The Problem We Are Solving", slide_title_style))
    story.append(Paragraph("Current software engineering workflows face severe code review friction.", slide_desc_style))
    
    # 3 Cards Layout: Columns 0, 2, 4 are Cards. Columns 1, 3 are Spacer Gaps.
    # Total Printable Width = 720. Widths: 226, 20, 226, 20, 226. (226*3 + 40 = 718)
    card1_content = [
        Paragraph("1. Time-Consuming Reviews", card_title_style),
        Spacer(1, 6),
        Paragraph("Manual code reviews consume hours of developer time daily. Reviewers are forced to repeat simple syntax suggestions and style guidelines over and over, distracting them from architecture and business logic reviews.", card_text_style)
    ]
    card2_content = [
        Paragraph("2. Style Disconnects", card_title_style),
        Spacer(1, 6),
        Paragraph("Different teams have unique stylistic preferences. Standard static style guides are quickly forgotten, and code quality suffers when style expectations are only communicated verbally or through ad-hoc PR comments.", card_text_style)
    ]
    card3_content = [
        Paragraph("3. Static Linters Do Not Learn", card_title_style),
        Spacer(1, 6),
        Paragraph("Traditional static analysis tools check rigid rules. They do not adapt to your decisions. If a team intentionally overrides a pattern, static tools continue flags and noise indefinitely, leading to alert fatigue.", card_text_style)
    ]
    
    problems_data = [[card1_content, "", card2_content, "", card3_content]]
    problems_table = Table(problems_data, colWidths=[226, 20, 226, 20, 226])
    problems_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Card 1 Styling
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#1e293b")),
        ('BOX', (0, 0), (0, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (0, 0), (0, 0), 16),
        ('BOTTOMPADDING', (0, 0), (0, 0), 16),
        ('LEFTPADDING', (0, 0), (0, 0), 16),
        ('RIGHTPADDING', (0, 0), (0, 0), 16),
        
        # Card 2 Styling
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#1e293b")),
        ('BOX', (2, 0), (2, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (2, 0), (2, 0), 16),
        ('BOTTOMPADDING', (2, 0), (2, 0), 16),
        ('LEFTPADDING', (2, 0), (2, 0), 16),
        ('RIGHTPADDING', (2, 0), (2, 0), 16),
        
        # Card 3 Styling
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor("#1e293b")),
        ('BOX', (4, 0), (4, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (4, 0), (4, 0), 16),
        ('BOTTOMPADDING', (4, 0), (4, 0), 16),
        ('LEFTPADDING', (4, 0), (4, 0), 16),
        ('RIGHTPADDING', (4, 0), (4, 0), 16),
    ]))
    
    story.append(problems_table)
    story.append(PageBreak())
    
    # ==========================================
    # SLIDE 3: Proposed Solution & User Journey
    # ==========================================
    story.append(Paragraph("Proposed Solution & User Journey", slide_title_style))
    story.append(Paragraph("ReviewMind combines AI-powered code reviews with adaptive machine learning.", slide_desc_style))
    
    # Left Column: Solution Core Features; Right Column: The User Journey Step-by-Step
    # Total Printable Width = 720. Widths: 348, 24, 348. (348*2 + 24 = 720)
    sol_col_content = [
        Paragraph("ReviewMind: The Adaptive Reviewer", card_title_style),
        Spacer(1, 10),
        Paragraph("• <b>Context-Aware Reviews</b>: Analyzes changes, naming, error handling, and performance using <i>gpt-4o-mini</i>.", card_bullet_style),
        Paragraph("• <b>Adaptive Memory</b>: Learns from merged code/developer actions and stores decisions in SQLite.", card_bullet_style),
        Paragraph("• <b>Automated Fix PRs</b>: Automatically opens secondary pull requests with code modifications, reducing developer friction.", card_bullet_style),
        Paragraph("• <b>Dynamic Style Writing</b>: Compiles accepted reviews into a live style guide (<b>TEAM_STYLE.md</b>) committed back to the repo.", card_bullet_style),
    ]
    
    journey_col_content = [
        Paragraph("The 4-Step Developer Journey", card_title_style),
        Spacer(1, 10),
        Paragraph("<b>Step 1: Code Pushed</b><br/>Developer opens/updates a PR. GitHub triggers the ReviewMind Flask Webhook.", card_bullet_style),
        Paragraph("<b>Step 2: AI Analyzes</b><br/>ReviewMind reviews the diff, comments suggestions on GitHub, and opens a Fix PR.", card_bullet_style),
        Paragraph("<b>Step 3: Feedback Loops</b><br/>Dev merges the Fix PR (Auto-Accept) or comments <i>reviewmind reject</i> to train the model.", card_bullet_style),
        Paragraph("<b>Step 4: Style Evolution</b><br/>Once 20 feedbacks are gathered, ReviewMind writes and commits the <i>TEAM_STYLE.md</i> guide.", card_bullet_style),
    ]
    
    solution_data = [[sol_col_content, "", journey_col_content]]
    solution_table = Table(solution_data, colWidths=[348, 24, 348])
    solution_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Left Card Styling
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#1e293b")),
        ('BOX', (0, 0), (0, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (0, 0), (0, 0), 16),
        ('BOTTOMPADDING', (0, 0), (0, 0), 16),
        ('LEFTPADDING', (0, 0), (0, 0), 16),
        ('RIGHTPADDING', (0, 0), (0, 0), 16),
        
        # Right Card Styling
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#1e293b")),
        ('BOX', (2, 0), (2, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (2, 0), (2, 0), 16),
        ('BOTTOMPADDING', (2, 0), (2, 0), 16),
        ('LEFTPADDING', (2, 0), (2, 0), 16),
        ('RIGHTPADDING', (2, 0), (2, 0), 16),
    ]))
    
    story.append(solution_table)
    story.append(PageBreak())
    
    # ==========================================
    # SLIDE 4: Tech Stack, Target Audience & Metrics
    # ==========================================
    story.append(Paragraph("Tech Stack, Audience & Phase 1 Metrics", slide_title_style))
    story.append(Paragraph("A lightweight, production-ready design built with robust integrations.", slide_desc_style))
    
    # Left Column: Tech Stack; Right Column: Target Audience & MVP Metrics
    stack_col_content = [
        Paragraph("Tools & Technologies Used", card_title_style),
        Spacer(1, 10),
        Paragraph("• <b>Backend Framework</b>: Python & Flask (manages webhooks, API logic, and HTML template endpoints)", card_bullet_style),
        Paragraph("• <b>Database Storage</b>: SQLite (manages code diffs, reviews, learning patterns, and snapshots)", card_bullet_style),
        Paragraph("• <b>APIs & Libraries</b>: <i>PyGithub</i> (fetches diffs, creates fix branches, posts comments) and <i>OpenAI API</i> (generates reviews)", card_bullet_style),
        Paragraph("• <b>Dashboard Frontend</b>: Vanilla HTML5, CSS Variables, and <i>Chart.js</i> (displays acceptance graphs and style trends)", card_bullet_style),
    ]
    
    audience_metrics_content = [
        Paragraph("Target Audience & MVP Status", card_title_style),
        Spacer(1, 10),
        Paragraph("<b>Target Audience</b>: Software developers, engineering teams, and tech leaders striving to maintain clean, standardized code without manual review overhead.", card_bullet_style),
        Spacer(1, 4),
        Paragraph("<b>Phase 1 MVP Production Run Results</b>:", card_bullet_style),
        Paragraph("  - <b>Total Reviews</b>: 22 PRs reviewed", card_bullet_style),
        Paragraph("  - <b>Feedback Database Records</b>: 22 learning rows stored", card_bullet_style),
        Paragraph("  - <b>Acceptance Rate</b>: 68% (based on real human interaction)", card_bullet_style),
        Paragraph("  - <b>Fix PRs Opened / Merged</b>: 15 / 15", card_bullet_style),
        Paragraph("  - <b>TEAM_STYLE.md</b>: Successfully generated and committed", card_bullet_style),
    ]
    
    stack_data = [[stack_col_content, "", audience_metrics_content]]
    stack_table = Table(stack_data, colWidths=[348, 24, 348])
    stack_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Left Card Styling
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#1e293b")),
        ('BOX', (0, 0), (0, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (0, 0), (0, 0), 16),
        ('BOTTOMPADDING', (0, 0), (0, 0), 16),
        ('LEFTPADDING', (0, 0), (0, 0), 16),
        ('RIGHTPADDING', (0, 0), (0, 0), 16),
        
        # Right Card Styling
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#1e293b")),
        ('BOX', (2, 0), (2, 0), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (2, 0), (2, 0), 16),
        ('BOTTOMPADDING', (2, 0), (2, 0), 16),
        ('LEFTPADDING', (2, 0), (2, 0), 16),
        ('RIGHTPADDING', (2, 0), (2, 0), 16),
    ]))
    
    story.append(stack_table)
    
    # Build the document and draw custom background on all pages
    doc.build(story, onFirstPage=draw_slide_background, onLaterPages=draw_slide_background)
    print(f"Successfully generated {pdf_filename}")

if __name__ == "__main__":
    build_pdf()
