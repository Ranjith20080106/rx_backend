from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta
from typing import Dict, Any

from app.database.connection import async_session_factory, User
from app.auth.jwt import get_current_user

router = APIRouter(tags=["Subscription"])

@router.post("/subscription/upgrade")
async def upgrade_subscription(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Upgrade user subscription to premium for 30 days (simulated payment validation)."""
    user_id = str(current_user.get("id"))
    email = current_user.get("email")
    
    # Sandbox fallback for mock/sandbox users
    if current_user.get("is_mock") or user_id == "mock_user_id" or not user_id.isdigit():
        from app.auth.jwt import UPGRADED_MOCK_USERS
        if user_id:
            UPGRADED_MOCK_USERS.add(user_id)
        if email:
            UPGRADED_MOCK_USERS.add(email)
        expiry = (datetime.utcnow() + timedelta(days=30)).isoformat()
        return {
            "status": "success",
            "message": "Subscription upgraded to Premium successfully (Sandbox Mock).",
            "is_premium": True,
            "premium_expiry": expiry
        }
    
    try:
        async with async_session_factory() as session:
            # Convert user_id to integer
            int_user_id = int(user_id)
            db_user = await session.get(User, int_user_id)
            
            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found."
                )
                
            db_user.is_premium = True
            db_user.premium_expiry = datetime.utcnow() + timedelta(days=30)
            
            await session.commit()
            
            return {
                "status": "success",
                "message": "Subscription upgraded to Premium successfully.",
                "is_premium": True,
                "premium_expiry": db_user.premium_expiry.isoformat()
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upgrade subscription: {str(e)}"
        )
