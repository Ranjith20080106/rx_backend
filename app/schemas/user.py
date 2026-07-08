from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    is_premium: bool = False
    premium_expiry: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class GoogleAuthRequest(BaseModel):
    credential: str
