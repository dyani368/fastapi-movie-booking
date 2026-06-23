from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_8kXUgRQpYi4E@ep-purple-mud-ah8a7e82.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL    
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db

