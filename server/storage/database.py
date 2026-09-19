import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server.storage.models import Base

# By default, attempt to connect to a local postgres DB. 
# In production, this should come from an environment variable.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/plylo")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
