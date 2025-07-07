import uuid
import datetime
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer

from .models import Base, JobRole, SkillInterest, Company # adjust import path if needed
from app.core.config import settings
# Database configuration
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:5432/{settings.POSTGRES_DB}"
)

# Sentence Transformer model
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Create a synchronous engine & session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure all tables are created before inserting
Base.metadata.create_all(engine)

# Load the model once
model = SentenceTransformer(MODEL_NAME)

def populate_table_from_file(table_class, file_path):
    """
    Reads each line from file_path, encodes it with SentenceTransformer,
    and inserts a new row into table_class(name, embedding, valid_from, valid_to).
    Skips any duplicates (by name).
    """
    session = SessionLocal()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    far_future = datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc)

    print(now_utc)
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            name = line.strip()
            if not name:
                continue

            # 1) Check if name already exists (skip duplicates)
            exists = (
                session
                .query(table_class)
                .filter(table_class.name == name)
                .first()
            )
            if exists:
                print(f"Skipped {name} (already exists in {table_class.__tablename__})")
                continue

            # 2) Generate embedding (sync)
            embedding = model.encode(name)

            # 3) Create and add record
            
            record = table_class(
                name=name,
                type = "place_holder",
                embedding=embedding,
                valid_from=now_utc,
                valid_to=far_future
            )
            session.add(record)
            print(f"Queued INSERT for '{name}' into {table_class.__tablename__}")

    # Commit all inserts at once
    try:
        session.commit()
        print(f"Committed all entries for {table_class.__tablename__}")
    except Exception as e:
        session.rollback()
        print(f"Error committing {table_class.__tablename__}: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    # Populate JobRole
    # jobroles_path = os.path.join("data", "jobroles_only.txt")
    # if os.path.isfile(jobroles_path):
    #     populate_table_from_file(JobRole, jobroles_path)
    # else:
    #     print(f"File not found: {jobroles_path}")

    # Populate SkillInterest
    # skills_path = os.path.join("data", "skills_only.txt")
    # if os.path.isfile(skills_path):
    #     populate_table_from_file(SkillInterest, skills_path)
    # else:
    #     print(f"File not found: {skills_path}")

    # If you want to populate Company later, uncomment:
    companies_path = os.path.join("data", "companies_only.txt")
    if os.path.isfile(companies_path):
        populate_table_from_file(Company, companies_path)
    else:
        print(f"File not found: {companies_path}")
