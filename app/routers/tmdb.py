from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.services import tmdb_movie_details, tmdb_search
from app.schemas import TMDBMovieImport

router = APIRouter()


@router.get("/search")
async def search(query: str, current_user: Annotated[models.User, Depends(get_current_user)]):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    if len(query.strip()) < 2:
        raise HTTPException(422, "Search query must have at least 2 characters")
    results = await tmdb_search(query.strip())
    return [{"tmdb_id": item.get("id"), "title": item.get("title") or "Untitled", "overview": item.get("overview"), "release_date": item.get("release_date"), "rating": item.get("vote_average"), "poster_path": item.get("poster_path")} for item in results[:20]]


@router.post("/import", status_code=201)
async def import_movie(payload: TMDBMovieImport, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    if db.execute(select(models.Movie.id).where(models.Movie.tmdb_id == payload.tmdb_id)).first():
        raise HTTPException(409, "This TMDB movie is already in the catalog")
    details = await tmdb_movie_details(payload.tmdb_id)
    director = next((person.get("name") for person in details.get("credits", {}).get("crew", []) if person.get("job") == "Director"), "Unknown")
    movie = models.Movie(
        title=str(details.get("title") or payload.title)[:255],
        director=str(director)[:255],
        seats_available=0,
        tmdb_id=payload.tmdb_id,
        overview=str(details.get("overview") or "")[:5000],
        release_date=details.get("release_date"),
        rating=details.get("vote_average"),
        tmdb_poster_path=details.get("poster_path"),
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie
