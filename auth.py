from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt
from config import settings
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated
from database import get_db
import models

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password) 

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()

    # 1. Set the ticket's expiration time (defaulting to 30 minutes from now)

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm
    )

    return encoded_jwt

def verify_access_token(token: str) -> int | None:

    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm]
        )

        user_id: str | None = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)

    except ( jwt.InvalidTokenError, ValueError):
        return None

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> models.User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = verify_access_token(token)
    if user_id is None:
        raise credentials_exception
    
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if user is None:
        raise credentials_exception
    
    return user


def get_current_user_from_cookie(
    request: Request, 
    db: Annotated[Session, Depends(get_db)]
) -> models.User:
    
    # 1. Grab the cookie
    token_str = request.cookies.get("access_token")
    if not token_str or not token_str.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    
    # 2. Chop off "Bearer " to get just the token
    token = token_str.split(" ")[1]
    
    # 3. Verify it (using the logic you already wrote!)
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
    return user

def get_optional_current_user(
    request: Request, 
    db: Annotated[Session, Depends(get_db)]
) -> models.User:
    
    # 1. Grab the cookie
    token_str = request.cookies.get("access_token")
    if not token_str or not token_str.startswith("Bearer "):
        return None
    
    # 2. Chop off "Bearer " to get just the token
    token = token_str.split(" ")[1]
    
    # 3. Verify it (using the logic you already wrote!)
    user_id = verify_access_token(token)
    if not user_id:
        return None
        
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if not user:
        return None
        
    return user

def get_admin_user(current_user: Annotated[models.User, Depends(get_current_user_from_cookie)]):

    if current_user.is_admin == False:
        raise HTTPException(status_code=403, detail="not an admin")
    
    return current_user


    


