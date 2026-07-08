import os
import json
import httpx
import re
import logging
from typing import List, Dict, Tuple, Any
from datetime import datetime

logger = logging.getLogger("AIAnalyzer")

# Graceful imports for scientific libraries
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer = None
    cosine_similarity = None
    logger.warning("Scikit-Learn not found. Similarity checks will use token overlap models.")

async def call_azure_openai_analyzer(resume_text: str, jd_text: str, filename: str) -> Dict[str, Any]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not all([endpoint, deployment_name, api_version, api_key]) or api_key == "your_azure_openai_api_key_here":
        raise ValueError("Azure OpenAI credentials are not fully configured.")

    endpoint_clean = endpoint.rstrip("/")
    url = f"{endpoint_clean}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an expert Applicant Tracking System (ATS) optimization engine.\n"
        "Analyze the provided Resume Text against the target Job Description (JD).\n"
        "You must output a JSON object containing the complete analysis. Do not include markdown formatting or backticks around the JSON.\n\n"
        "Required JSON Schema:\n"
        "{\n"
        '  "ats_score": 75, // integer between 20 and 100 representing overall compatibility\n'
        '  "scores_breakdown": {\n'
        '    "skills_match": 80.0, // float between 0 and 100\n'
        '    "experience_match": 75.0, // float between 0 and 100\n'
        '    "education_match": 90.0, // float between 0 and 100\n'
        '    "keyword_match": 70.0 // float between 0 and 100\n'
        '  },\n'
        '  "matched_skills": ["PYTHON", "FASTAPI"], // list of uppercase skills found in both resume and JD\n'
        '  "missing_keywords": ["DOCKER", "KUBERNETES"], // list of uppercase skills found in JD but missing in resume\n'
        '  "experience_summary": "Extremely relevant years match",\n'
        '  "education_summary": "Matches required degree criteria",\n'
        '  "format_check": {\n'
        '    "has_contact_info": true, // boolean\n'
        '    "has_summary": true, // boolean\n'
        '    "has_experience": true, // boolean\n'
        '    "has_education": true, // boolean\n'
        '    "is_length_optimal": true, // boolean\n'
        '    "issues": [] // list of formatting issues found\n'
        '  },\n'
        '  "suggestions": [\n'
        '    "Incorporate core missing skills: DOCKER, KUBERNETES.",\n'
        '    "Detail metrics-driven STAR statements."\n'
        '  ],\n'
        '  "keyword_optimizations": [\n'
        '    {\n'
        '      "keyword": "DOCKER",\n'
        '      "status": "Missing",\n'
        '      "fix": "Add this core competency under your Skills or Experience section."\n'
        '    }\n'
        '  ],\n'
        '  "ai_cover_letter": "..." // A professional cover letter tailored to the job description and resume\n'
        "}"
    )

    user_content = f"Resume Text:\n{resume_text}\n\nJob Description:\n{jd_text}"

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        content = result["choices"][0]["message"]["content"]
        content_clean = content.strip()
        if content_clean.startswith("```"):
            content_clean = re.sub(r"^```[a-zA-Z]*\n", "", content_clean)
            content_clean = re.sub(r"\n```$", "", content_clean)
            content_clean = content_clean.strip()

        data = json.loads(content_clean)
        
        data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["filename"] = filename
        
        defaults = {
            "ats_score": 70,
            "scores_breakdown": {"skills_match": 70.0, "experience_match": 70.0, "education_match": 70.0, "keyword_match": 70.0},
            "matched_skills": [],
            "missing_keywords": [],
            "experience_summary": "Moderately aligned structure",
            "education_summary": "Degree parameters partially matched",
            "format_check": {"has_contact_info": True, "has_summary": True, "has_experience": True, "has_education": True, "is_length_optimal": True, "issues": []},
            "suggestions": [],
            "keyword_optimizations": [],
            "ai_cover_letter": ""
        }
        
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
                
        data["matched_skills"] = [str(s).upper() for s in data["matched_skills"]]
        data["missing_keywords"] = [str(s).upper() for s in data["missing_keywords"]]
        
        return data

async def improve_resume_with_azure_openai(resume_text: str, missing_keywords: List[str], suggestions: List[str], job_description: str = None) -> str:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not all([endpoint, deployment_name, api_version, api_key]) or api_key == "your_azure_openai_api_key_here":
        raise ValueError("Azure OpenAI credentials are not fully configured.")

    endpoint_clean = endpoint.rstrip("/")
    url = f"{endpoint_clean}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an expert professional resume writer and ATS optimization engine.\n"
        "Your task is to rewrite the candidate's Resume Text to improve its quality, flow, and ATS alignment.\n"
        "You must output ONLY the rewritten resume text. Do not include markdown code blocks, intro, or outro text.\n\n"
        "Guidelines:\n"
        "1. Incorporate the following missing keywords naturally into experience bullet points and skills: " + ", ".join(missing_keywords) + "\n"
        "2. Address the following suggestions: " + "; ".join(suggestions) + "\n"
        "3. Format experience bullets using the STAR method (Situation, Task, Action, Result) with active verbs and quantifiable metrics (percentages, values, time savings) where appropriate.\n"
        "4. Preserve the overall sections, structure, and original content, but elevate the phrasing to sound premium, metrics-driven, and highly professional."
    )

    user_content = f"Original Resume Text:\n{resume_text}"
    if job_description:
        user_content += f"\n\nTarget Job Description:\n{job_description}"

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.5
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()
            
        return content

# Industry skills taxonomy for structural extraction
SKILLS_TAXONOMY = [
    # Programming Languages
    "javascript", "typescript", "python", "java", "c++", "c#", "go", "golang", 
    "rust", "ruby", "php", "swift", "kotlin", "sql", "nosql", "html", "css", "r", "scala",
    # Web Frameworks
    "react", "next.js", "nextjs", "vue", "vuejs", "angular", "svelte", "express", 
    "node", "node.js", "nodejs", "fastapi", "django", "flask", "spring boot", "laravel",
    # Cloud & DevOps
    "aws", "amazon web services", "azure", "gcp", "google cloud", "docker", 
    "kubernetes", "k8s", "terraform", "ansible", "jenkins", "git", "github", 
    "ci/cd", "ci-cd", "pipelines", "actions", "nginx", "linux",
    # Data & Database
    "postgresql", "postgres", "mongodb", "mysql", "redis", "elasticsearch", 
    "dynamodb", "sqlite", "oracle", "snowflake", "spark", "hadoop", "kafka",
    # AI & Machine Learning
    "openai", "gpt", "llm", "langchain", "tensorflow", "pytorch", "keras", 
    "pandas", "numpy", "scikit-learn", "nlp", "computer vision", "pinecone", "chroma",
    # General Tech / Agile
    "agile", "scrum", "jira", "graphql", "rest", "restful", "grpc", "websockets", "microservices"
]

def clean_text(text: str) -> str:
    """Preprocess raw text by lowercasing and stripping non-alphanumeric patterns."""
    if not text:
        return ""
    text = text.lower()
    # Replace special characters and extra whitespaces
    text = re.sub(r'[\r\n\t]', ' ', text)
    text = re.sub(r'[^\w\s\-\.\@\+\#]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_skills(cleaned_text: str) -> List[str]:
    """Extract known taxonomy skills matching keywords in the text."""
    found_skills = []
    # Tokenize by word and check overlap
    # We also check exact substrings for multi-word skills like "spring boot"
    for skill in SKILLS_TAXONOMY:
        pattern = rf'\b{re.escape(skill)}\b'
        if re.search(pattern, cleaned_text):
            found_skills.append(skill)
    return sorted(list(set(found_skills)))

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity score between two texts using TF-IDF or Jaccard overlap."""
    if not text1 or not text2:
        return 0.0

    # 1. Primary: Scikit-Learn TF-IDF Vecs
    if TfidfVectorizer and cosine_similarity:
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(max(0.0, min(1.0, sim)))
        except Exception as e:
            logger.error(f"Error computing TF-IDF: {e}")
            
    # 2. Fallback: Jaccard Token Overlap
    tokens1 = set(text1.split())
    tokens2 = set(text2.split())
    if not tokens1 or not tokens2:
        return 0.0
    return len(tokens1.intersection(tokens2)) / len(tokens1.union(tokens2))

async def run_ats_analysis(resume_text: str, jd_text: str, filename: str = "resume.pdf") -> Dict[str, Any]:
    """Execute complete multi-layered ATS scoring against JD & Resume using Azure OpenAI (or local fallback)."""
    try:
        logger.info("Attempting Azure OpenAI ATS analysis...")
        return await call_azure_openai_analyzer(resume_text, jd_text, filename)
    except Exception as e:
        logger.warning(f"Azure OpenAI analysis failed ({e}). Falling back to local heuristic analysis.")
        return run_ats_analysis_local(resume_text, jd_text, filename)

def run_ats_analysis_local(resume_text: str, jd_text: str, filename: str = "resume.pdf") -> Dict[str, Any]:
    """Execute complete multi-layered ATS scoring against JD & Resume using local heuristics."""
    raw_resume_clean = clean_text(resume_text)
    raw_jd_clean = clean_text(jd_text)
    
    # 1. SKILLS MATCH (40%)
    resume_skills = extract_skills(raw_resume_clean)
    jd_skills = extract_skills(raw_jd_clean)
    
    matched_skills = [skill for skill in resume_skills if skill in jd_skills]
    missing_keywords = [skill for skill in jd_skills if skill not in resume_skills]
    
    if len(jd_skills) > 0:
        skills_score = (len(matched_skills) / len(jd_skills)) * 100
    else:
        # Default fallback if JD doesn't contain standard keywords
        skills_score = 65.0
    
    # 2. KEYWORD MATCH (20%)
    # Compute similarity between entire JD and Resume texts
    keyword_score = calculate_cosine_similarity(raw_resume_clean, raw_jd_clean) * 100
    
    # 3. EXPERIENCE MATCH (30%)
    # Extract years of experience and compare overlap patterns
    exp_sim = calculate_cosine_similarity(
        " ".join([w for w in raw_resume_clean.split() if any(c.isdigit() or c in ['year', 'exp', 'lead', 'senior', 'work'] for c in w)]),
        " ".join([w for w in raw_jd_clean.split() if any(c.isdigit() or c in ['year', 'exp', 'lead', 'senior', 'require'] for c in w)])
    )
    experience_score = exp_sim * 100
    if experience_score < 40:
        experience_score = min(skills_score + 10, 85.0) # Graceful relative scale
    
    # 4. EDUCATION MATCH (10%)
    # Check for degrees and field overlap
    edu_terms = ["bachelor", "master", "phd", "b.s.", "m.s.", "degree", "computer science", "engineering", "graduated", "university"]
    resume_edu = [w for w in edu_terms if w in raw_resume_clean]
    jd_edu = [w for w in edu_terms if w in raw_jd_clean]
    
    matched_edu = [w for w in resume_edu if w in jd_edu]
    if len(jd_edu) > 0:
        education_score = (len(matched_edu) / len(jd_edu)) * 100
    else:
        education_score = 90.0 if "university" in raw_resume_clean or "bachelor" in raw_resume_clean else 50.0

    # 5. INTEGRITY FORMAT CHECK
    format_issues = []
    has_contact = "@" in raw_resume_clean or "phone" in raw_resume_clean
    has_summary = any(kw in raw_resume_clean for kw in ["summary", "profile", "about", "objective"])
    has_exp = any(kw in raw_resume_clean for kw in ["experience", "work", "history", "employment"])
    has_edu = any(kw in raw_resume_clean for kw in ["education", "university", "college", "school"])
    
    words_count = len(resume_text.split())
    is_length_optimal = 300 <= words_count <= 850
    
    if not has_contact: format_issues.append("Missing email or contact coordinates.")
    if not has_summary: format_issues.append("Consider adding a professional summary section.")
    if not has_exp: format_issues.append("Professional experience section not detected.")
    if not has_edu: format_issues.append("Education history section not found.")
    if not is_length_optimal:
        if words_count < 300:
            format_issues.append("Resume is brief. Add more context to pass automated filters.")
        else:
            format_issues.append("Too wordy! Streamline to fit a single page.")

    # 6. TOTAL ATS SCORE COMPILER (Weights: 40% skills, 30% exp, 20% keywords, 10% edu)
    final_score = int(
        (0.40 * skills_score) + 
        (0.30 * experience_score) + 
        (0.20 * keyword_score) + 
        (0.10 * education_score)
    )
    final_score = max(20, min(100, final_score)) # clamp boundaries

    # 7. GENERATE DYNAMIC SUGGESTIONS
    suggestions = []
    if missing_keywords:
        suggestions.append(f"Incorporate missing core skills: {', '.join(missing_keywords[:4]).upper()}.")
    if format_issues:
        suggestions.extend(format_issues[:2])
    if final_score < 70:
        suggestions.append("Incorporate metrics-driven STAR statements detailing quantifiable savings/throughput.")
    else:
        suggestions.append("ATS matching is highly competitive! Add custom keywords tailored directly to this job's unique objectives.")

    # 8. KEYWORD OPTIMIZATIONS
    optimizations = []
    for keyword in missing_keywords[:5]:
        optimizations.append({
            "keyword": keyword.upper(),
            "status": "Missing",
            "fix": f"Add this core competency under your Skills or Experience section to increase ATS indexing match."
        })
    for keyword in matched_skills[:5]:
        optimizations.append({
            "keyword": keyword.upper(),
            "status": "Matched",
            "fix": "Well represented! Ensure this skill is linked to a concrete professional project outcome."
        })

    # 9. GENERATE TAILORED COVER LETTER
    cover_letter = generate_cover_letter_mock(resume_text, jd_text, matched_skills)

    return {
        "ats_score": final_score,
        "scores_breakdown": {
            "skills_match": round(skills_score, 1),
            "experience_match": round(experience_score, 1),
            "education_match": round(education_score, 1),
            "keyword_match": round(keyword_score, 1)
        },
        "matched_skills": [s.upper() for s in matched_skills],
        "missing_keywords": [s.upper() for s in missing_keywords],
        "experience_summary": "Extremely relevant years match" if experience_score > 70 else "Moderately aligned structure",
        "education_summary": "Matches required degree criteria" if education_score > 60 else "Degree parameters partially matched",
        "format_check": {
            "has_contact_info": has_contact,
            "has_summary": has_summary,
            "has_experience": has_exp,
            "has_education": has_edu,
            "is_length_optimal": is_length_optimal,
            "issues": format_issues
        },
        "suggestions": suggestions,
        "keyword_optimizations": optimizations,
        "ai_cover_letter": cover_letter,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename
    }

def generate_cover_letter_mock(resume_text: str, jd_text: str, matched_skills: List[str]) -> str:
    """Craft a premium, structured cover letter based on parsed overlaps."""
    # Try to extract candidate name or use default
    name_match = re.search(r'^([A-Z][a-z]+ [A-Z][a-z]+)', resume_text.strip())
    name = name_match.group(1) if name_match else "Professional Candidate"
    
    skills_para = ", ".join([s.upper() for s in matched_skills[:4]]) if matched_skills else "Full-stack Software Architecture"
    
    letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the open position outlined in your job listing. As an experienced professional with a proven track record of engineering scalable systems and spearheading technical projects, I am confident that my qualifications align exceptionally well with your team's objectives.

Throughout my career, I have developed expertise in core areas including {skills_para}. In my previous engagements, I have focused on translating complex business requirements into elegant, robust, and high-performance software systems. My development philosophy revolves around clean code practices, data-driven optimization, and cross-functional team collaboration.

I am particularly excited about this opportunity because your team is solving highly interesting technical challenges. I am eager to apply my skills in modern application engineering to help drive key product initiatives and achieve outstanding results.

Thank you for your time and consideration. I welcome the opportunity to discuss how my background, technical competencies, and passion for excellence can contribute to your team.

Sincerely,

{name}"""
    return letter
