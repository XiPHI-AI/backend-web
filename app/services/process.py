# app/services/process.py (Updated find_or_create_location)
import numpy as np
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer
from postgres.models import Location, Company, JobRole, SkillInterest # Combined imports
import uuid
from datetime import datetime, timezone


model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embedding(text: str) -> list[float]:
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()




async def find_or_create_skill_interest(db: AsyncSession, entity_name: str, entity_type: str) -> Dict[str, Any]:
    """
    Finds the closest existing skill/interest or creates a new one if no sufficient match.
    Uses vector search + full-text search.
    Args:
        db: The async database session.
        entity_name: The raw skill or interest name provided by the user.
        entity_type: 'skill' or 'interest' (could be used for filtering in the future if needed)
    Returns:
        A dictionary with 'interest_id' (UUID string) and 'name' (normalized name).
        (Note: Renamed from skill_interest_id in return for consistency with 'interest' use-case)
    """
    embedding = generate_embedding(entity_name)

    # Step 1: Exact lexical match
    exact_match_query = select(SkillInterest).filter(SkillInterest.name == entity_name).limit(1)
    exact_match_result = await db.execute(exact_match_query)
    exact_entity_obj = exact_match_result.scalars().first()

    found_match = None
    if exact_entity_obj:
        found_match = exact_entity_obj
        print(f"Found existing {entity_type} via exact match: {found_match.name}")
    else:
        # Step 2: Vector search if no exact match
        vector_query = (
            select(
                SkillInterest.skill_interest_id,
                SkillInterest.name,
                SkillInterest.embedding
            )
            .where(SkillInterest.embedding.isnot(None)) # Only compare with entities that have embeddings
            .order_by(SkillInterest.embedding.l2_distance(embedding))
            .limit(5)
        )
        result = await db.execute(vector_query)
        top_entities_from_vector = result.fetchall()

        if top_entities_from_vector:
            top_vector_match_row = top_entities_from_vector[0]
            # You might add a similarity threshold here: e.g., if L2 distance > X, treat as no match
            # For simplicity, just taking the top one for now.
            found_match = top_vector_match_row
            print(f"Using top vector match for {entity_type}: {found_match.name}")

    if found_match:
        # This branch executes if either exact or vector match was found
        # Ensure the embedding is returned correctly (from ORM object or Row object)
        found_embedding = None
        if hasattr(found_match, 'embedding') and found_match.embedding is not None:
             found_embedding = found_match.embedding.tolist() if isinstance(found_match.embedding, np.ndarray) else list(found_match.embedding)

        return {
            "skill_interest_id": str(found_match.skill_interest_id), # <<< CORRECTED KEY NAME HERE
            "name": found_match.name,
            "embedding": found_embedding # Return embedding from the found match
        }
    else:
        # No close match found (either vector search empty or no sufficiently close match)
        print(f"No close match found for {entity_name}. Creating new {entity_type}.")
        new_id = uuid.uuid4()
        new_entity = SkillInterest(
            skill_interest_id=new_id,
            name=entity_name,
            category=entity_type, # IMPORTANT: Set the category if your SkillInterest table has it
            embedding=embedding # Use the embedding generated from the input
        )
        db.add(new_entity)
        await db.flush()
        return {
            "skill_interest_id": str(new_id), # <<< CORRECTED KEY NAME HERE
            "name": entity_name,
            "embedding": embedding # Return the embedding of the newly created entity
        }
# --- New functions for normalizing Companies and Job Roles (no change) ---

async def find_or_create_company(db: AsyncSession, company_name: str) -> Dict[str, Any]:
    """
    Finds an existing company by name or creates a new one.
    This could be extended with fuzzy matching if needed.
    """
    result = await db.execute(select(Company).filter(Company.name == company_name))
    existing_company = result.scalars().first()

    if existing_company:
        print(f"Found existing company: {existing_company.name}")
        return {
            "company_id": str(existing_company.company_id),
            "name": existing_company.name
        }
    else:
        print(f"Creating new company: {company_name}")
        new_id = uuid.uuid4()
        new_company = Company(
            company_id=new_id,
            name=company_name
        )
        db.add(new_company)
        await db.flush() # Flush to get the ID
        return {
            "company_id": str(new_id),
            "name": company_name
        }

async def find_or_create_job_role(db: AsyncSession, job_role_title: str) -> Dict[str, Any]:
    """
    Finds an existing job role by title or creates a new one.
    This could be extended with fuzzy matching if needed.
    """
    result = await db.execute(select(JobRole).filter(JobRole.name == job_role_title))
    existing_job_role = result.scalars().first()

    if existing_job_role:
        print(f"Found existing job role: {existing_job_role.name}")
        return {
            "job_role_id": str(existing_job_role.job_role_id),
            "title": existing_job_role.name
        }
    else:
        print(f"Creating new job role: {job_role_title}")
        new_id = uuid.uuid4()
        new_job_role = JobRole(
            job_role_id=new_id,
            name=job_role_title
        )
        db.add(new_job_role)
        await db.flush()
        return {
            "job_role_id": str(new_id),
            "title": job_role_title
        }


async def find_or_create_location(db: AsyncSession, location_name: str) -> Dict[str, Any]:
    """
    Finds the closest existing location by name (using embedding similarity) or creates a new one.
    Stores embeddings for new locations.
    Args:
        db: The async database session.
        location_name: The raw location name provided by the user.
    Returns:
        A dictionary with 'location_id' (UUID string), 'name' (normalized name), and 'embedding' (list[float]).
    """
    input_embedding = generate_embedding(location_name)

    # First, try to find an exact match by name, regardless of embedding presence
    exact_match_query = select(Location).filter(Location.name == location_name)
    exact_match_result = await db.execute(exact_match_query)
    found_location_obj = exact_match_result.scalars().first()

    if found_location_obj:
        print(f"Found existing Location via exact name match: {found_location_obj.name}")
        # If it's an exact match, but lacks an embedding, consider updating it.
        # For now, we'll just return its current state.
        embedding_list = found_location_obj.embedding.tolist() if isinstance(found_location_obj.embedding, np.ndarray) else list(found_location_obj.embedding) if found_location_obj.embedding is not None else []
        return {
            "location_id": str(found_location_obj.location_id),
            "name": found_location_obj.name,
            "embedding": embedding_list # This might be an empty list if embedding was None
        }

    # If no exact name match, proceed with vector search
    # Only search among locations that *have* embeddings
    vector_query = (
        select(
            Location.location_id,
            Location.name,
            Location.embedding
        )
        .where(Location.embedding.isnot(None)) # Only compare with locations that have embeddings
        .order_by(Location.embedding.l2_distance(input_embedding))
        .limit(5) # Get top 5 semantic matches
    )
    result = await db.execute(vector_query)
    top_locations_from_vector = result.fetchall()

    if top_locations_from_vector:
        # If vector search yielded results (meaning there are existing embeddings)
        top_vector_location_row = top_locations_from_vector[0]
        print(f"Found existing Location via vector search: {top_vector_location_row.name}")
        embedding_list = top_vector_location_row.embedding.tolist() if isinstance(top_vector_location_row.embedding, np.ndarray) else list(top_vector_location_row.embedding)
        return {
            "location_id": str(top_vector_location_row.location_id),
            "name": top_vector_location_row.name,
            "embedding": embedding_list
        }
    else:
        # No exact name match found, AND no suitable vector matches (either no embeddings or no close ones)
        print(f"No exact match or close semantic match found for '{location_name}'. Creating new Location.")
        new_id = uuid.uuid4()
        new_location_obj = Location(
            location_id=new_id,
            name=location_name,
            embedding=input_embedding # Store the embedding of the new entity
        )
        db.add(new_location_obj)
        await db.flush()

        return {
            "location_id": str(new_id),
            "name": location_name,
            "embedding": input_embedding
        }
def parse_delimited_string(text: Optional[str]) -> List[str]:
    """
    Parses a comma-separated string into a list of stripped strings.
    Handles None or empty strings gracefully.
    """
    if not text:
        return []
    # Split by comma, strip whitespace from each item, and filter out any empty strings
    return [item.strip() for item in text.split(',') if item.strip()]
