from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from app.database import get_db
from app.routers import bookings, calendar, movies, payments, tmdb, users

app = FastAPI(title="Cinebook API", version="1.0.0")
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(tmdb.router, prefix="/api/tmdb", tags=["tmdb"])

PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
if FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="frontend-assets")
app.mount("/static", StaticFiles(directory=PROJECT_DIR / "static"), name="static")
if (PROJECT_DIR / "media").is_dir():
    app.mount("/media", StaticFiles(directory=PROJECT_DIR / "media"), name="media")


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable") from exc
    return {"status": "healthy"}


@app.exception_handler(IntegrityError)
def database_conflict_handler(request: Request, exception: IntegrityError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "The request conflicts with existing data"})


@app.exception_handler(OperationalError)
def database_unavailable_handler(request: Request, exception: OperationalError):
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": "Database connection is temporarily unavailable. Check Neon and retry."})


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exception: StarletteHTTPException):
    return JSONResponse(status_code=exception.status_code, content={"detail": exception.detail})


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend build not found. Run the Vite development server or build frontend/.")
