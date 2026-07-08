import os
import sys
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add parent directory of 'app' to sys.path so we can import 'app' as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import connect_to_mongo, close_mongo_connection
from app.routes import auth, analysis, subscription

# Load env variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage lifecycle database connection pools."""
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="ResumeX - Full-Stack ATS Resume Optimizer API",
    description="Scalable FastAPI backend enabling secure JWT user sessions, PDF/DOCX text extractions, sentence similarity matchings, and custom ReportLab report PDF downloads.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend fetches
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routes
app.include_router(auth.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(subscription.router, prefix="/api")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ResumeX Full-Stack ATS Core Engine",
        "api_docs": "/docs"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Dynamically inject backend directory into PYTHONPATH for uvicorn subprocess reload
    app_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(app_dir)
    
    python_path = os.environ.get("PYTHONPATH", "")
    if python_path:
        os.environ["PYTHONPATH"] = f"{backend_dir}{os.pathsep}{python_path}"
    else:
        os.environ["PYTHONPATH"] = backend_dir
        
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
