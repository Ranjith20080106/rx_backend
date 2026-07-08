import io
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def generate_report_pdf(analysis: Dict[str, Any], user_name: str) -> io.BytesIO:
    """Generate a clean, professional, styled PDF analysis report using ReportLab flowables."""
    buffer = io.BytesIO()
    
    # 1. Page Setup
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    story = []
    
    # 2. Styles Setup
    styles = getSampleStyleSheet()
    
    # Custom Palette - Coordinates with ResumeX SaaS Premium warm Bauhaus linen and luxury indigo theme
    primary_color = colors.HexColor("#4f46e5") # Royal Indigo
    text_color = colors.HexColor("#1c1a17")    # Warm Luxury Ink
    light_bg = colors.HexColor("#f8f6f0")      # Warm Ivory Linen
    border_color = colors.HexColor("#d6d0c2")  # Soft Bronze/Copper border
    text_muted = colors.HexColor("#5e574d")    # Muted brass-charcoal
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=primary_color,
        alignment=TA_LEFT,
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=6,
        borderPadding=4
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=text_color,
        leading=14,
        spaceAfter=6
    )
    
    bold_body = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        textColor=text_muted
    )
    
    # 3. Premium Header Banner (Matching the navbar of the web app!)
    header_data = [
        [Paragraph("ResumeX", ParagraphStyle('LogoText', parent=body_style, fontSize=20, textColor=colors.white, fontName='Helvetica-Bold')),
         Paragraph("ATS OPTIMIZATION REPORT", ParagraphStyle('ReportType', parent=body_style, fontSize=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER))]
    ]
    header_table = Table(header_data, colWidths=[250, 250])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), primary_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    story.append(Paragraph(f"<b>Candidate:</b> {user_name} | <b>Date:</b> {analysis.get('timestamp', datetime.now().strftime('%Y-%m-%d'))}", meta_style))
    story.append(Paragraph(f"<b>Analyzed Resume:</b> {analysis.get('filename', 'resume.pdf')}", meta_style))
    story.append(Spacer(1, 15))
    
    # 4. Score Block (Callout Table)
    score = analysis.get("ats_score", 0)
    score_text = f"<b>ATS Compatibility Score: {score}/100</b>"
    
    if score >= 80:
        badge_bg = colors.HexColor("#d1fae5")
        badge_border = colors.HexColor("#10b981")
        badge_text = "EXCELLENT MATCH"
    elif score >= 60:
        badge_bg = colors.HexColor("#fef3c7")
        badge_border = colors.HexColor("#f59e0b")
        badge_text = "GOOD ALIGNMENT"
    else:
        badge_bg = colors.HexColor("#fee2e2")
        badge_border = colors.HexColor("#ef4444")
        badge_text = "IMPROVEMENT REQUIRED"
        
    score_table_data = [
        [Paragraph(score_text, ParagraphStyle('ScoreText', parent=body_style, fontSize=16, textColor=primary_color)),
         Paragraph(f"<b>Status: {badge_text}</b>", ParagraphStyle('BadgeText', parent=body_style, fontSize=11, alignment=TA_CENTER))]
    ]
    
    score_table = Table(score_table_data, colWidths=[300, 200])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), badge_bg),
        ('BOX', (0,0), (-1,-1), 1.5, badge_border),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
    ]))
    
    story.append(score_table)
    story.append(Spacer(1, 15))
    
    # 5. Breakdown Grid
    story.append(Paragraph("Score Breakdown Analysis", h2_style))
    breakdown = analysis.get("scores_breakdown", {})
    
    breakdown_data = [
        [Paragraph("<b>Evaluation Category</b>", bold_body), Paragraph("<b>Match Weight</b>", bold_body), Paragraph("<b>Calculated Score</b>", bold_body)],
        [Paragraph("Skills & Core Competencies", body_style), Paragraph("40%", body_style), Paragraph(f"{breakdown.get('skills_match', 0)}%", body_style)],
        [Paragraph("Experience Relevance", body_style), Paragraph("30%", body_style), Paragraph(f"{breakdown.get('experience_match', 0)}%", body_style)],
        [Paragraph("Keyword Synonyms Overlap", body_style), Paragraph("20%", body_style), Paragraph(f"{breakdown.get('keyword_match', 0)}%", body_style)],
        [Paragraph("Education & Degrees Match", body_style), Paragraph("10%", body_style), Paragraph(f"{breakdown.get('education_match', 0)}%", body_style)]
    ]
    
    breakdown_table = Table(breakdown_data, colWidths=[240, 130, 130])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), light_bg),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
    ]))
    
    story.append(breakdown_table)
    story.append(Spacer(1, 15))
    
    # 6. Format Checks & Discovered Keywords
    story.append(Paragraph("ATS Structural Formatting Check", h2_style))
    checks = analysis.get("format_check", {})
    
    format_data = [
        [Paragraph("<b>Integrity Check Item</b>", bold_body), Paragraph("<b>Status</b>", bold_body)],
        [Paragraph("Contact Coordinates Identified (Email/Phone)", body_style), Paragraph("PASSED" if checks.get("has_contact_info") else "FAILED", bold_body)],
        [Paragraph("Professional Bio / Career Summary Presence", body_style), Paragraph("PASSED" if checks.get("has_summary") else "FAILED", bold_body)],
        [Paragraph("Work Experience Section Validation", body_style), Paragraph("PASSED" if checks.get("has_experience") else "FAILED", bold_body)],
        [Paragraph("Education Framework Verification", body_style), Paragraph("PASSED" if checks.get("has_education") else "FAILED", bold_body)],
        [Paragraph("Word Count Range Optimization", body_style), Paragraph("PASSED" if checks.get("is_length_optimal") else "FAILED", bold_body)]
    ]
    
    format_table = Table(format_data, colWidths=[350, 150])
    format_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), light_bg),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(format_table)
    story.append(Spacer(1, 15))

    # 7. Actionable Suggestions
    story.append(Paragraph("Improvement Recommendations", h2_style))
    suggestions = analysis.get("suggestions", [])
    
    if suggestions:
        for idx, suggestion in enumerate(suggestions):
            story.append(Paragraph(f"• {suggestion}", body_style))
    else:
        story.append(Paragraph("Outstanding! No critical format or indexing issues found.", body_style))
        
    story.append(Spacer(1, 10))
    
    # 8. Keywords Optimization
    story.append(Paragraph("Target Skill Keyword Analysis (Top Missing)", h2_style))
    missing = analysis.get("missing_keywords", [])
    if missing:
        story.append(Paragraph(f"The following identified keywords are requested in the JD, but missing in your resume. Insert these terms to increase ATS relevance: <b>{', '.join(missing[:8])}</b>", body_style))
    else:
        story.append(Paragraph("Excellent! All key skills listed in the job description are present in your resume.", body_style))
        
    # Build Document
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_resume_pdf(resume_text: str, user_name: str) -> io.BytesIO:
    """Generate a clean, professional, styled resume PDF document from plain text."""
    buffer = io.BytesIO()
    
    # Page Setup
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )
    story = []
    
    # Styles Setup
    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#111827")   # Deep Slate Gray
    accent_color = colors.HexColor("#4f46e5")    # Indigo Accent
    text_color = colors.HexColor("#374151")      # Charcoal body text
    text_muted = colors.HexColor("#6b7280")      # Muted Gray contact/meta
    
    name_style = ParagraphStyle(
        'ResumeName',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=primary_color,
        alignment=1, # Centered
        spaceAfter=4
    )
    
    contact_style = ParagraphStyle(
        'ResumeContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        textColor=text_muted,
        alignment=1, # Centered
        spaceAfter=12
    )
    
    section_style = ParagraphStyle(
        'ResumeSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=accent_color,
        spaceBefore=10,
        spaceAfter=4,
        borderPadding=2
    )
    
    body_style = ParagraphStyle(
        'ResumeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=text_color,
        leading=14,
        spaceAfter=4
    )
    
    bullet_style = ParagraphStyle(
        'ResumeBullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )
    
    left_align_style = ParagraphStyle(
        'LeftJobTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=primary_color,
        leading=14
    )
    
    right_align_style = ParagraphStyle(
        'RightJobDate',
        parent=left_align_style,
        fontName='Helvetica-Bold',
        alignment=2, # Right-aligned
        textColor=accent_color
    )
    
    lines = resume_text.split('\n')
    
    first_line = True
    contact_info_written = False
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
            
        line_lower = line_strip.lower()
        
        # 1. Format candidate name (first non-empty line of the resume text)
        if first_line and not any(h in line_lower for h in ["experience", "work history", "skills", "technical skills", "education", "summary", "projects"]):
            story.append(Paragraph(line_strip, name_style))
            first_line = False
            continue
            
        first_line = False
        
        # 2. Format Contact Info (second line if it contains email, phone, or location indicators)
        if not contact_info_written and any(indicator in line_lower for indicator in ["@", "phone", "email", "+91", "location", "address", "|", "district"]):
            # Normalize pipe spacing for aesthetics
            cleaned_contact = line_strip.replace("|", " • ")
            # Standardize spacing around bullets
            cleaned_contact = " ".join(cleaned_contact.split())
            story.append(Paragraph(cleaned_contact, contact_style))
            contact_info_written = True
            continue
            
        # 3. Detect and format Section Headers
        is_header = False
        headers = ["experience", "work history", "employment history", "skills", "technical skills", "core competencies", "education", "projects", "summary", "profile", "objective"]
        if len(line_strip) < 40 and any(line_lower.startswith(h) or line_lower == h for h in headers):
            # Add section divider bar with Indigo accent color
            divider = Table([[""]], colWidths=[522], rowHeights=[1.5])
            divider.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), accent_color),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(Spacer(1, 6))
            story.append(divider)
            story.append(Paragraph(line_strip.upper(), section_style))
            is_header = True
            
        # 4. Detect and format Left-Right Layout for Jobs, Education, and Projects
        # e.g., "Senior Software Engineer | TechVibe Innovations | Mar 2021 – Dec 2023"
        # or "B.S. in Computer Science | University of Texas | Graduated: May 2020"
        elif not line_strip.startswith(('-', '*', '•')) and ('|' in line_strip or ',' in line_strip) and any(d in line_lower for d in ["present", "201", "202", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
            separator = '|' if '|' in line_strip else ','
            parts = [p.strip() for p in line_strip.split(separator)]
            if len(parts) >= 2:
                # Find the part that acts as the date
                date_part = ""
                other_parts = []
                for p in parts:
                    p_lower = p.lower()
                    has_date_indicator = any(d in p_lower for d in ["present", "201", "202", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])
                    if has_date_indicator and not date_part:
                        date_part = p
                    else:
                        other_parts.append(p)
                
                if date_part and other_parts:
                    # Bold the primary title (e.g. Job Title or Degree)
                    left_html = f"<b>{other_parts[0]}</b>"
                    if len(other_parts) > 1:
                        left_html += " — " + " — ".join(other_parts[1:])
                        
                    left_p = Paragraph(left_html, left_align_style)
                    right_p = Paragraph(date_part, right_align_style)
                    
                    row_table = Table([[left_p, right_p]], colWidths=[390, 132])
                    row_table.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 0),
                        ('TOPPADDING', (0,0), (-1,-1), 2),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                    ]))
                    story.append(row_table)
                    continue
            
            # If split logic didn't output a table, fall back to standard rendering
            story.append(Paragraph(line_strip, body_style))
            
        # 5. Detect and format Bullet Points
        elif line_strip.startswith('-') or line_strip.startswith('*') or line_strip.startswith('•'):
            bullet_text = line_strip[1:].strip()
            story.append(Paragraph(f"• {bullet_text}", bullet_style))
            
        # 6. Format standard body text
        else:
            story.append(Paragraph(line_strip, body_style))
            
    doc.build(story)
    buffer.seek(0)
    return buffer

