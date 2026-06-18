from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated

import models
from database import get_db
from schemas import UserCreate, UserPublic, UserPrivate, UserUpdate, Token

from fastapi.security import OAuth2PasswordRequestForm
from auth import hash_password, verify_password, create_access_token, get_current_user


router = APIRouter()

@router.get("", response_model=list[UserPublic])
def get_users_api(db: Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User))

    users = result.scalars().all()

    return users

@router.get("/me", response_model=UserPrivate)
def read_user_me(current_user: Annotated[models.User, Depends(get_current_user)]):
    """Returns the profile of the currently logged-in user."""
    return current_user

@router.get("/{user_id}", response_model=UserPublic)
def get_user_api(user_id: int, db: Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))

    user=result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    return user

@router.post(
    "",
    response_model = UserPrivate,
    status_code = status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):

    result1 = db.execute(select(models.User).where(models.User.username==user.username))

    if result1.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    
    result2 = db.execute(select(models.User).where(models.User.email==user.email))

    if result2.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email already registered")

    new_user = models.User(username=user.username, email=user.email, hashed_password=hash_password(user.password))

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@router.post("/token", response_model=Token)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(get_db)]):

    user = db.execute(select(models.User).where(models.User.username==form_data.username)).scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}  # Standard requirement for 401 token responses
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}


@router.patch("/{user_id}", response_model=UserPrivate)
def update_user_api(user_id: int, user_data: UserUpdate, db: Annotated[Session, Depends(get_db)]):

    user = db.execute(select(models.User).where(models.User.id==user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)

    if "password" in update_data:
        password = update_data.pop("password")
        update_data["hashed_password"] = hash_password(password)

    for key,value in update_data.items():
        setattr(user,key,value)
    
    db.commit()
    db.refresh(user)
    
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_api(user_id: int, db: Annotated[Session, Depends(get_db)]):

    user=db.execute(select(models.User).where(user_id==models.User.id)).scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()