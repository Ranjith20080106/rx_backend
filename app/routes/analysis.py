import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.future import select
from sqlalchemy import func

from app.database.connection import async_session_factory, Resume, Analysis
from app.auth.jwt import get_current_user
from app.utils.text_extractor import extract_text_from_file
from app.services.ai_analyzer import run_ats_analysis, improve_resume_with_azure_openai
from app.services.pdf_generator import generate_report_pdf, generate_resume_pdf

logger = logging.getLogger("AnalysisRouter")
router = APIRouter(tags=["Resume Analysis"])

@router.post("/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload a resume file, extract text, run the AI ATS optimizer, and save the report to PostgreSQL."""
    if not file.filename.lower().endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Please upload a PDF, DOCX, or plain text file."
        )
        
    try:
        # 0. Subscription Quota & Limit Checks
        user_id = str(current_user.get("_id", current_user.get("id")))
        is_premium = bool(current_user.get("is_premium", False))
        
        # If database operations fail or are offline, bypass strict backend blocking and allow frontend storage to manage
        try:
            async with async_session_factory() as session:
                if not is_premium:
                    result = await session.execute(
                        select(func.count(Analysis.id)).filter(Analysis.user_id == user_id)
                    )
                    total_count = result.scalar() or 0
                    if total_count >= 3:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You have used all 3 free resume analyses. Please upgrade to Premium to continue analyzing resumes."
                        )
                else:
                    start_of_today = datetime.combine(date.today(), datetime.min.time())
                    result = await session.execute(
                        select(func.count(Analysis.id))
                        .filter(Analysis.user_id == user_id)
                        .filter(Analysis.timestamp >= start_of_today)
                    )
                    today_count = result.scalar() or 0
                    if today_count >= 50:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Premium limit reached: You have analyzed 50 resumes today. Please wait until tomorrow or contact support."
                        )
        except HTTPException:
            raise
        except Exception as db_err:
            logger.warning(f"Database error checking analysis limits: {db_err}")

        # 1. Extract Resume Text
        resume_text = extract_text_from_file(file)
        
        if not resume_text or len(resume_text.strip()) < 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to extract readable text. The document might be scanned or empty."
            )
            
        # Validate that the document is actually a resume by checking standard resume indicators
        text_lower = resume_text.lower()
        resume_indicators = ["experience", "education", "skills", "projects", "summary", "profile", "employment", "history", "career"]
        match_count = sum(1 for indicator in resume_indicators if indicator in text_lower)
        
        if match_count < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded document does not appear to be a valid resume. Please upload a professional resume containing standard sections like experience, education, or skills."
            )
            
        # 2. Trigger AI Core Optimizer
        analysis_report = await run_ats_analysis(resume_text, job_description, filename=file.filename)
        
        # Add user identifier
        analysis_report["user_id"] = str(current_user.get("_id", current_user.get("id")))
        
        # 3. Save to PostgreSQL
        try:
            async with async_session_factory() as session:
                # Save raw resume reference
                resume_record = Resume(
                    user_id=analysis_report["user_id"],
                    filename=file.filename,
                    text=resume_text
                )
                session.add(resume_record)
                await session.commit()
                await session.refresh(resume_record)
                
                # Save analysis results
                new_analysis = Analysis(
                    user_id=analysis_report["user_id"],
                    resume_id=str(resume_record.id),
                    ats_score=analysis_report["ats_score"],
                    filename=file.filename,
                    matched_skills=analysis_report.get("matched_skills", []),
                    missing_keywords=analysis_report.get("missing_keywords", []),
                    scores_breakdown=analysis_report.get("scores_breakdown", {}),
                    format_check=analysis_report.get("format_check", {}),
                    suggestions=analysis_report.get("suggestions", []),
                    keyword_optimizations=analysis_report.get("keyword_optimizations", []),
                    ai_cover_letter=analysis_report.get("ai_cover_letter", "")
                )
                session.add(new_analysis)
                await session.commit()
                await session.refresh(new_analysis)
                
                analysis_report["id"] = str(new_analysis.id)
                analysis_report["resume_id"] = str(resume_record.id)
                analysis_report["resume_text"] = resume_text
        except Exception as db_err:
            logger.error(f"PostgreSQL saving error: {db_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database write failure. Resume analysis could not be saved: {str(db_err)}"
            )

        return analysis_report
        
    except Exception as e:
        logger.error(f"Error in analysis pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during resume analysis: {str(e)}"
        )

@router.get("/history")
async def get_user_history(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve all past resume analysis reports for the authenticated user from PostgreSQL."""
    user_id = str(current_user.get("_id", current_user.get("id")))
    
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Analysis)
                .filter(Analysis.user_id == user_id)
                .order_by(Analysis.timestamp.desc())
            )
            analyses = result.scalars().all()
            history = []
            for doc in analyses:
                resume_text = ""
                try:
                    resume_id_int = int(doc.resume_id)
                    resume_res = await session.execute(select(Resume).filter(Resume.id == resume_id_int))
                    resume_obj = resume_res.scalars().first()
                    if resume_obj:
                        resume_text = resume_obj.text
                except Exception:
                    pass

                history.append({
                    "id": str(doc.id),
                    "user_id": doc.user_id,
                    "resume_id": doc.resume_id,
                    "ats_score": doc.ats_score,
                    "timestamp": doc.timestamp.strftime("%Y-%m-%d %H:%M:%S") if doc.timestamp else "",
                    "filename": doc.filename,
                    "matched_skills": doc.matched_skills,
                    "missing_keywords": doc.missing_keywords,
                    "scores_breakdown": doc.scores_breakdown,
                    "format_check": doc.format_check,
                    "suggestions": doc.suggestions,
                    "keyword_optimizations": doc.keyword_optimizations if hasattr(doc, 'keyword_optimizations') else [],
                    "ai_cover_letter": doc.ai_cover_letter if hasattr(doc, 'ai_cover_letter') else "",
                    "resume_text": resume_text
                })
            return history
    except Exception as e:
        logger.error(f"Database error while querying history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failure. Could not query analysis history: {str(e)}"
        )

@router.get("/profile")
async def get_user_profile_stats(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve aggregate statistics about the user's resumes and ATS score histories from PostgreSQL."""
    user_id = str(current_user.get("_id", current_user.get("id")))
    is_premium = bool(current_user.get("is_premium", False))
    premium_expiry = current_user.get("premium_expiry")
    
    base_stats = {
        "name": current_user.get("name", "Sandbox User"),
        "email": current_user.get("email"),
        "joined": current_user.get("created_at", datetime.utcnow().strftime("%Y-%m-%d"))[:10],
        "total_analyzed": 0,
        "average_score": 0,
        "max_score": 0,
        "is_premium": is_premium,
        "premium_expiry": premium_expiry,
        "today_analyzed": 0,
        "remaining_today": 50 if is_premium else 3
    }

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(
                    func.count(Analysis.id),
                    func.avg(Analysis.ats_score),
                    func.max(Analysis.ats_score)
                ).filter(Analysis.user_id == user_id)
            )
            count, avg_score, max_score = result.fetchone()
            
            if count and count > 0:
                base_stats["total_analyzed"] = count
                base_stats["average_score"] = round(avg_score) if avg_score else 0
                base_stats["max_score"] = max_score if max_score else 0
                
            # 2. Fetch today's analysis count for daily quota tracking
            start_of_today = datetime.combine(date.today(), datetime.min.time())
            today_result = await session.execute(
                select(func.count(Analysis.id))
                .filter(Analysis.user_id == user_id)
                .filter(Analysis.timestamp >= start_of_today)
            )
            today_count = today_result.scalar() or 0
            base_stats["today_analyzed"] = today_count
            
            if is_premium:
                base_stats["remaining_today"] = max(0, 50 - today_count)
            else:
                base_stats["remaining_today"] = max(0, 3 - base_stats["total_analyzed"])
                
            return base_stats
    except Exception as e:
        logger.warning(f"PostgreSQL profile stats error: {e}")
        from app.auth.jwt import MOCK_ANALYSES_DB
        
        # Filter in-memory dynamic analyses database strictly by authenticated user_id
        user_docs = [doc for doc in MOCK_ANALYSES_DB if doc.get("user_id") == user_id]
        
        # If empty and sandbox user, pre-load sandbox candidate profile metrics
        if not user_docs and current_user.get("email") in ["sandbox@example.com", "sandbox"]:
            base_stats["total_analyzed"] = 1
            base_stats["average_score"] = 82
            base_stats["max_score"] = 82
            base_stats["today_analyzed"] = 0
            base_stats["remaining_today"] = 50 if is_premium else 2
            return base_stats
            
        scores = [doc["ats_score"] for doc in user_docs]
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Count reports submitted today
        today_count = sum(1 for doc in user_docs if (doc["timestamp"].strftime("%Y-%m-%d") if isinstance(doc["timestamp"], datetime) else str(doc["timestamp"]).startswith(today_str)) == today_str)
        
        base_stats["total_analyzed"] = len(user_docs)
        base_stats["average_score"] = round(sum(scores) / len(scores)) if scores else 0
        base_stats["max_score"] = max(scores) if scores else 0
        base_stats["today_analyzed"] = today_count
        base_stats["remaining_today"] = max(0, 50 - today_count) if is_premium else max(0, 3 - len(user_docs))
        return base_stats

@router.get("/download-report/{analysis_id}")
async def download_analysis_report(analysis_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Generate and download a beautifully styled PDF document report for a past analysis from PostgreSQL."""
    try:
        async with async_session_factory() as session:
            # Try parsing analysis_id as integer
            try:
                int_id = int(analysis_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invalid analysis report ID format."
                )
                
            result = await session.execute(select(Analysis).filter(Analysis.id == int_id))
            doc = result.scalars().first()
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Analysis report not found."
                )
                
            # Verify ownership
            if str(doc.user_id) != str(current_user.get("_id", current_user.get("id"))):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this report."
                )
                
            # Construct dictionary representing analysis for PDF generator compatibility
            analysis_dict = {
                "id": str(doc.id),
                "ats_score": doc.ats_score,
                "timestamp": doc.timestamp.strftime("%Y-%m-%d") if doc.timestamp else "",
                "filename": doc.filename,
                "matched_skills": doc.matched_skills,
                "missing_keywords": doc.missing_keywords,
                "scores_breakdown": doc.scores_breakdown,
                "format_check": doc.format_check,
                "suggestions": doc.suggestions,
                "keyword_optimizations": doc.keyword_optimizations if hasattr(doc, 'keyword_optimizations') else [],
                "ai_cover_letter": doc.ai_cover_letter if hasattr(doc, 'ai_cover_letter') else ""
            }
            
            pdf_buffer = generate_report_pdf(analysis_dict, current_user.get("name", "Candidate"))
            
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=ATS_Report_{analysis_id}.pdf"}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving PDF download from PostgreSQL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}"
        )


# --- Resume Improvement Models & Routes ---

class ResumeImproveRequest(BaseModel):
    resume_text: str
    missing_keywords: List[str]
    suggestions: List[str]
    job_description: Optional[str] = None

class ResumeDownloadRequest(BaseModel):
    resume_text: str
    name: Optional[str] = "Candidate"

def improve_resume_text_logic(resume_text: str, missing_keywords: List[str], suggestions: List[str]) -> str:
    lines = resume_text.split('\n')
    improved_lines = []
    
    in_skills = False
    in_summary = False
    in_experience = False
    keywords_injected = False
    
    keywords_to_add = [k.upper() for k in missing_keywords if k]
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            improved_lines.append("")
            continue
            
        line_lower = line_strip.lower()
        
        is_header = False
        if len(line_strip) < 40 and any(h in line_lower for h in ["experience", "work history", "employment history"]):
            in_experience = True
            in_skills = False
            in_summary = False
            is_header = True
        elif len(line_strip) < 40 and any(h in line_lower for h in ["skills", "core competencies", "technical skills"]):
            in_skills = True
            in_experience = False
            in_summary = False
            is_header = True
        elif len(line_strip) < 40 and any(h in line_lower for h in ["summary", "profile", "objective", "about me"]):
            in_summary = True
            in_skills = False
            in_experience = False
            is_header = True
        elif len(line_strip) < 40 and any(h in line_lower for h in ["education", "projects", "certifications"]):
            in_skills = False
            in_experience = False
            in_summary = False
            is_header = True
            
        if in_skills and not is_header and not keywords_injected and len(keywords_to_add) > 0:
            line = line + ", " + ", ".join(keywords_to_add)
            keywords_injected = True
            
        elif in_summary and not is_header and len(line_strip) > 20:
            if not any(k.lower() in line_lower for k in keywords_to_add[:3]):
                line = line.rstrip('.') + f", specialized in {', '.join(keywords_to_add[:3])}."
                
        elif in_experience and not is_header and (line_strip.startswith('-') or line_strip.startswith('*') or line_strip.startswith('•')):
            bullet_char = line_strip[0]
            bullet_text = line_strip[1:].strip()
            bullet_lower = bullet_text.lower()
            
            rewrites = {
                "build frontend": "Spearheaded frontend application development using React, enhancing user interface load speeds by 35% and increasing engagement by 20%.",
                "manage a team": "Orchestrated and mentored a high-performing cross-functional team of engineers, increasing development sprint velocity by 25%.",
                "worked on backend": "Architected and deployed highly scalable backend API services, improving system responsiveness and query response time by 40%.",
                "fixed bugs": "Systematically debugged and optimized legacy source code, reducing application runtime errors by 50% and improving reliability.",
                "database design": "Designed and optimized database schemas, increasing data retrieval throughput and query processing efficiency by 30%.",
                "develop features": "Successfully designed and deployed key software features, reducing customer onboarding friction and increasing satisfaction rates by 15%."
            }
            
            rewritten = False
            for trigger, replacement in rewrites.items():
                if trigger in bullet_lower:
                    line = bullet_char + " " + replacement
                    rewritten = True
                    break
            
            if not rewritten and len(bullet_text) < 50:
                line = bullet_char + " Successfully modernized software workflows, achieving a 20% boost in operational efficiency and system stability."
                
        improved_lines.append(line)
        
    if not keywords_injected and keywords_to_add:
        improved_lines.append("\nTECHNICAL SKILLS (ATS OPTIMIZED)")
        improved_lines.append("- " + ", ".join(keywords_to_add))
        
    return "\n".join(improved_lines)

@router.post("/improve-resume")
async def improve_resume(req: ResumeImproveRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Generate an improved version of the resume text based on missing keywords and suggestions."""
    try:
        # Try Azure OpenAI rewrite first, fallback to local heuristics if it fails
        try:
            logger.info("Attempting Azure OpenAI resume rewrite...")
            improved_text = await improve_resume_with_azure_openai(
                req.resume_text, req.missing_keywords, req.suggestions, req.job_description
            )
        except Exception as e:
            logger.warning(f"Azure OpenAI resume rewrite failed ({e}). Falling back to local heuristics.")
            improved_text = improve_resume_text_logic(req.resume_text, req.missing_keywords, req.suggestions)
        
        original_score = 65
        improved_score = 85
        improved_report = None
        
        if req.job_description:
            improved_report = await run_ats_analysis(improved_text, req.job_description, filename="improved_resume.pdf")
            improved_score = improved_report.get("ats_score", 85)
            
            # Get original score
            orig_report = await run_ats_analysis(req.resume_text, req.job_description, filename="original_resume.pdf")
            original_score = orig_report.get("ats_score", 65)
            
        return {
            "original_text": req.resume_text,
            "improved_text": improved_text,
            "original_score": original_score,
            "improved_score": improved_score,
            "improved_report": improved_report
        }
    except Exception as e:
        logger.error(f"Error in improve_resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during resume improvement: {str(e)}"
        )

@router.post("/download-improved-pdf")
async def download_improved_pdf(req: ResumeDownloadRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Stream a beautifully formatted PDF of the optimized resume."""
    try:
        pdf_buffer = generate_resume_pdf(req.resume_text, req.name or current_user.get("name", "Candidate"))
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=Improved_Resume.pdf"}
        )
    except Exception as e:
        logger.error(f"Error serving improved resume PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate resume PDF: {str(e)}"
        )

