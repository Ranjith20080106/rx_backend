import os
import logging
from datetime import datetime
import urllib.parse

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    JSON,
    Boolean,
    text
)

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DatabaseConnection")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
connect_args = {}

if DATABASE_URL:
    # Convert standard PostgreSQL URIs to asyncpg
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

    # Strip sslmode and channel_binding from URL query params, pass via connect_args
    if "postgresql+asyncpg" in DATABASE_URL:
        if "?" in DATABASE_URL:
            base_url, query_params = DATABASE_URL.split("?", 1)
            if "sslmode" in query_params or "channel_binding" in query_params:
                DATABASE_URL = base_url
                connect_args["ssl"] = True
else:
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_SERVER = os.getenv("DB_SERVER")
    DB_NAME = os.getenv("DB_NAME")
    DB_PORT = os.getenv("DB_PORT", "1433")

    if not DB_SERVER:
        raise ValueError("DB_SERVER or DATABASE_URL environment variable is missing")

    if not DB_NAME:
        raise ValueError("DB_NAME environment variable is missing")

    # Escape password to handle special characters (like '@' in the password)
    safe_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""

    DATABASE_URL = (
        f"mssql+aioodbc://{DB_USER}:{safe_password}"
        f"@{DB_SERVER}:{DB_PORT}/{DB_NAME}"
        "?driver=ODBC+Driver+17+for+SQL+Server"
    )

# Async Engine
engine = create_async_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Async Session Factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# --- SQLAlchemy Database Models ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)
    premium_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    resume_id = Column(String(100), nullable=False)
    ats_score = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    filename = Column(String(255), nullable=False)
    
    matched_skills = Column(JSON, nullable=False)
    missing_keywords = Column(JSON, nullable=False)
    scores_breakdown = Column(JSON, nullable=False)
    format_check = Column(JSON, nullable=False)
    suggestions = Column(JSON, nullable=False)
    keyword_optimizations = Column(JSON, nullable=True)
    ai_cover_letter = Column(Text, nullable=True)


# Keep compatibility stub to prevent app crashes if imported directly
class DummyDB:
    pass

dummy_db = DummyDB()

def get_database():
    """Fallback dummy database reference for backwards compatibility."""
    return dummy_db

# ==========================
# Session Dependency
# ==========================

async def get_db():
    async with async_session_factory() as session:
        yield session

# ==========================
# Database Initialization
# ==========================

async def connect_to_mongo():
    """Create all tables in database. Replaces MongoDB initialization."""
    logger.info("Connecting to database and verifying tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Ensure columns from schema changes are present in existing tables
            await conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS keyword_optimizations JSON;"))
            await conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS ai_cover_letter TEXT;"))
        logger.info("Successfully connected to database and tables verified.")
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        logger.warning("FastAPI backend will run, but database operations will fail.")

async def close_mongo_connection():
    """Dispose of database engine connection pool."""
    logger.info("Closing database connection pool...")
    await engine.dispose()
    logger.info("Database connection pool closed.")

# Health Check / Compatibility Stubs
async def connect_to_database():
    await connect_to_mongo()

async def close_database_connection():
    await close_mongo_connection()

async def test_connection():
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            logger.info(f"Database connection test successful: {result.scalar()}")
            return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
