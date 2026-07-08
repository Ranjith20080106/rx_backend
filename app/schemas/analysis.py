from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class ResumeAnalysisRequest(BaseModel):
    job_description: str
    resume_text: Optional[str] = None # Or uploaded via multipart

class MatchScoreDetails(BaseModel):
    skills_match: float = Field(..., description="Weight 40%")
    experience_match: float = Field(..., description="Weight 30%")
    education_match: float = Field(..., description="Weight 10%")
    keyword_match: float = Field(..., description="Weight 20%")

class ATSFormatChecker(BaseModel):
    has_contact_info: bool
    has_summary: bool
    has_experience: bool
    has_education: bool
    is_length_optimal: bool
    issues: List[str]

class AnalysisResponse(BaseModel):
    id: str
    user_id: str
    ats_score: int
    scores_breakdown: MatchScoreDetails
    matched_skills: List[str]
    missing_keywords: List[str]
    experience_summary: str
    education_summary: str
    format_check: ATSFormatChecker
    suggestions: List[str]
    keyword_optimizations: List[Dict[str, str]]
    ai_cover_letter: str
    timestamp: str
    filename: str
