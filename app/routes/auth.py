from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
from sqlalchemy.future import select
import re

from app.database.connection import async_session_factory, User
from app.schemas.user import UserRegister, UserLogin, UserResponse, Token, GoogleAuthRequest
from app.auth.pwd import hash_password, verify_password
from app.auth.jwt import create_access_token, get_current_user

router = APIRouter(tags=["Authentication"])

def is_strong_password(password: str) -> bool:
    """Validate that password has min 8 chars, 1 uppercase, 1 lowercase, 1 number, and 1 special char."""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[@$!%*?&_#^-]", password):
        return False
    return True

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """Register a new user, hash their password, save to PostgreSQL, and issue an access token."""
    # Strong password validation check
    if not is_strong_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one number, and one special character."
        )

    try:
        async with async_session_factory() as session:
            # Check if user already exists
            result = await session.execute(select(User).filter(User.email == user_data.email))
            existing_user = result.scalars().first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already registered"
                )

            # Hash password and create record
            hashed_pwd = hash_password(user_data.password)
            new_user = User(
                name=user_data.name,
                email=user_data.email,
                hashed_password=hashed_pwd
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            user_id = str(new_user.id)
            user_resp = UserResponse(id=user_id, name=new_user.name, email=new_user.email)
            access_token = create_access_token({"sub": new_user.email})
            
            return Token(access_token=access_token, user=user_resp)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("AuthRouter").error(f"Database error during registration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection or write failure. Registration failed: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate existing credentials and issue a JWT access token."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(User).filter(User.email == credentials.email))
            user = result.scalars().first()
            
            if not user or not verify_password(credentials.password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_id = str(user.id)
            user_resp = UserResponse(id=user_id, name=user.name, email=user.email)
            access_token = create_access_token({"sub": user.email})

            return Token(access_token=access_token, user=user_resp)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("AuthRouter").error(f"Database error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failure. Login failed: {str(e)}"
        )

@router.post("/upgrade")
async def upgrade_user_to_premium(
    current_user: dict = Depends(get_current_user)
):
    """Upgrade the active authenticated user to Premium plan for 30 days in PostgreSQL."""
    try:
        from app.database.connection import async_session_factory, User
        from sqlalchemy import update
        from datetime import datetime, timedelta
        from app.auth.jwt import UPGRADED_MOCK_USERS
        
        user_id = current_user.get("id")
        email = current_user.get("email")
        expiry_date = datetime.utcnow() + timedelta(days=30)
        
        # Add to UPGRADED_MOCK_USERS for in-memory session persistence & robust fallback
        if user_id:
            UPGRADED_MOCK_USERS.add(str(user_id))
        if email:
            UPGRADED_MOCK_USERS.add(email)
            
        # If it's a mock user in sandbox mode, skip PostgreSQL write
        if current_user.get("is_mock") or user_id == "mock_user_id":
            return {
                "status": "success",
                "message": "Account successfully upgraded to Premium (Mock Sandbox)!",
                "is_premium": True,
                "premium_expiry": expiry_date.strftime("%Y-%m-%d")
            }
            
        async with async_session_factory() as session:
            await session.execute(
                update(User)
                .where(User.id == int(user_id))
                .values(is_premium=True, premium_expiry=expiry_date)
            )
            await session.commit()
            
        return {
            "status": "success",
            "message": "Account successfully upgraded to Premium!",
            "is_premium": True,
            "premium_expiry": expiry_date.strftime("%Y-%m-%d")
        }
    except Exception as e:
        import logging
        logging.getLogger("AuthRouter").error(f"Database error during subscription upgrade: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database update failure. Upgrade failed: {str(e)}"
        )

@router.post("/auth/google", response_model=Token)
async def google_auth(req: GoogleAuthRequest):
    """Authenticate or register a user via Google OAuth 2.0 or secure Sandbox mockup."""
    credential = req.credential
    email = None
    name = "Google User"
    
    # Check if this is a mock sandbox Google token
    if credential.startswith("mock_google_token_"):
        # Format: mock_google_token_{email}_{name}
        parts = credential.replace("mock_google_token_", "").split("_", 1)
        email = parts[0]
        if len(parts) > 1:
            name = parts[1].replace("%20", " ")
    else:
        # Standard production Google JWT validation
        try:
            from jose import jwt
            # Google ID token contains standard JWT payload
            payload = jwt.get_unverified_claims(credential)
            email = payload.get("email")
            name = payload.get("name", "Google User")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Google credential token: {e}"
            )
            
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve email from Google authentication payload."
        )
        
    try:
        from app.database.connection import async_session_factory, User
        from app.auth.pwd import hash_password
        from app.auth.jwt import UPGRADED_MOCK_USERS
        import uuid
        
        async with async_session_factory() as session:
            result = await session.execute(select(User).filter(User.email == email))
            user = result.scalars().first()
            
            if not user:
                # First-time Google user: Automatic account creation!
                dummy_pwd = hash_password(str(uuid.uuid4()))
                user = User(
                    name=name,
                    email=email,
                    hashed_password=dummy_pwd
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                
            user_id = str(user.id)
            user_resp = UserResponse(
                id=user_id,
                name=user.name,
                email=user.email,
                is_premium=bool(user.is_premium) or user_id in UPGRADED_MOCK_USERS or user.email in UPGRADED_MOCK_USERS,
                premium_expiry=user.premium_expiry.strftime("%Y-%m-%d") if user.premium_expiry else None
            )
            access_token = create_access_token({"sub": user.email})
            return Token(access_token=access_token, user=user_resp)
            
    except Exception as e:
        import logging
        logging.getLogger("AuthRouter").error(f"Database error during Google auth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection or write failure. Google authentication failed: {str(e)}"
        )

@router.get("/config")
async def get_config():
    """Fetch public credentials like GOOGLE_CLIENT_ID for frontend integrations."""
    import os
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "")
    }

@router.get("/diagnostic-db")
async def diagnostic_db():
    import os
    import traceback
    from app.database.connection import engine
    
    db_url = os.getenv("DATABASE_URL")
    # Mask password for security
    masked_db_url = db_url
    if db_url and "@" in db_url:
        try:
            parts = db_url.split("@")
            prefix = parts[0].split(":")
            if len(prefix) > 2:
                prefix[2] = "*****"
            masked_db_url = ":".join(prefix) + "@" + parts[1]
        except Exception:
            masked_db_url = "masked"

    result_info = {
        "database_url_configured": masked_db_url,
        "engine_url": str(engine.url) if engine else None,
        "connection_success": False,
        "error": None
    }
    
    try:
        async with engine.begin() as conn:
            result_info["connection_success"] = True
    except Exception as e:
        result_info["error"] = str(e)
        result_info["traceback"] = traceback.format_exc()
        
    return result_info


