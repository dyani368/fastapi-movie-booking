"""Create a small demo catalog with dated bookable screenings."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import models
from app.database import SessionLocal

DEMO_MOVIES = [
    ("The Last Horizon", "Mira Sol", 84),
    ("Midnight in Kyoto", "Kenji Watanabe", 62),
    ("Little Big Summer", "Anya Brooks", 110),
    ("Orbit 9", "Ravi Nair", 47),
    ("The Paper Garden", "Leah Morgan", 73),
    ("After the Rain", "Ishaan Mehta", 91),
]


def main() -> None:
    with SessionLocal() as db:
        for title, director, _ in DEMO_MOVIES:
            movie = db.execute(select(models.Movie).where(models.Movie.title == title)).scalars().first()
            if movie is None:
                movie = models.Movie(title=title, director=director, seats_available=0)
                db.add(movie)
                db.flush()
            has_screenings = db.execute(select(models.Screening.id).where(models.Screening.movie_id == movie.id).limit(1)).first()
            if has_screenings:
                continue
            local_tz = ZoneInfo("Asia/Kolkata")
            day = (datetime.now(local_tz) + timedelta(days=1)).date()
            for hour, price in ((11, 25000), (15, 30000), (19, 35000)):
                starts = datetime(day.year, day.month, day.day, hour, 0, tzinfo=local_tz).astimezone(timezone.utc)
                db.add(models.Screening(movie_id=movie.id, starts_at=starts, auditorium="Screen 1", capacity=80, seats_reserved=0, price_paise=price))
                movie.seats_available += 80
        db.commit()
        print(f"Demo catalog ready with {len(DEMO_MOVIES)} movies and upcoming screenings.")


if __name__ == "__main__":
    main()
