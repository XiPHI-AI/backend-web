
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# Ensure User models are correctly imported
from postgres.models import User, UserSkill,UserLocation, UserInterest, UserJobRole, UserCompany, Event as PgEvent, Conference as PgConference, UserRegistration, Location # NEW: Import UserRegistration
from app.models.person import UserCreate, UserRead, UserUpdateSchema, RegistrationCategory, UserLoginResponse, UserLoginPayload, ConferenceResponse, ConferencePayload, ClaimUserIdRegistration
from app.db.database import get_db
from datetime import datetime, timezone
import uuid
import asyncio
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

# Import Neo4j CRUD functions
from app.db.neo4j import (
    create_user_node, create_or_update_user_skill_neo4j,
    create_or_update_user_interest_neo4j, create_or_update_user_job_role_neo4j,
    create_or_update_user_company_neo4j, update_user_location_neo4j,
    create_conference_node_if_not_exists,
    link_user_to_conference # For user-conference registration
)

from app.services.process import ( # Assuming these are defined in app.services.process.py
    find_or_create_skill_interest,
    find_or_create_company,
    find_or_create_job_role,
    find_or_create_location
)

from typing import Dict, Any, List, Optional # Ensure Optional is imported for type hints
from services.services.person_service import PeopleService


router = APIRouter()

async def get_people_service_dependency(db: AsyncSession = Depends(get_db)):
    from app.db.neo4j import get_neo4j_async_driver # Local import
    neo4j_driver_instance = await get_neo4j_async_driver()
    return PeopleService(db=db, neo4j_driver_async=neo4j_driver_instance)


# --- User CRUD Endpoints ---

@router.post("/", response_model=UserRead)
async def create_user(user_create_payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # Import main module inside the function to avoid circular dependency
    import main as main_app_module 

    # 1. Check for existing user
    result = await db.execute(select(User).filter(User.email == user_create_payload.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Create new User in Postgres
    
    new_user = User(
        user_id=uuid.uuid4(),
        email=user_create_payload.email,
        password_hash=user_create_payload.password_hash,
        full_name = user_create_payload.full_name,
        avatar_url=user_create_payload.avatar_url,
        biography=user_create_payload.biography,
        phone=user_create_payload.phone,
        registration_category=user_create_payload.registration_category
    )
    result = await db.execute(
        select(UserRegistration).filter(UserRegistration.reg_id == user_create_payload.registration_id)
    )
    
    

    db.add(new_user)

    await db.commit()
    await db.refresh(new_user)

    registration = result.scalars().first()
    registration.user_id = new_user.user_id
    registration.claimed_by_user_at = datetime.now(timezone.utc)
    registration.status = "claimed"

    await db.commit()
    await db.refresh(registration)

    neo4j_registration_category = None
    if new_user.registration_category:
    # Check if it's an Enum instance, and if so, get its value.
    # Otherwise, assume it's already a string (less likely to be hit if ORM rehydrates).
        if isinstance(new_user.registration_category, RegistrationCategory):
            neo4j_registration_category = new_user.registration_category.value
        else:
        # This case handles scenarios where it might already be a string for some reason
            neo4j_registration_category = str(new_user.registration_category) 
        # Using str() is a robust way to ensure it's a string for non-enum cases too.

    await create_user_node(
    user_id=str(new_user.user_id),
    email=new_user.email,
    full_name = new_user.full_name,
    avatar_url=new_user.avatar_url,
    biography=new_user.biography,
    phone=new_user.phone,
    registration_category=neo4j_registration_category # <--- Pass the explicitly converted string here
)
    # REVERTED: No initial connections based on UserCreate payload for now, or reg_id linking
    # These functions now await correctly in update_user_data.

    if registration and registration.conference_id:
        relationship = {
            "attendee": "ATTENDS",
            "exhibitor": "EXHIBITS",
            "speaker": "SPEAKS_AT"
        }.get(neo4j_registration_category.lower(), "PARTICIPATES")

        await create_conference_node_if_not_exists(
        conference_id=str(registration.conference_id)
        )

        await link_user_to_conference(
            user_id=str(new_user.user_id),
            conference_id=str(registration.conference_id),
            relationship_type=relationship
        )

    # Ensure UserRead returns correct data (reg_id will be None initially)
    new_user_read_response = UserRead.from_orm(new_user)
    # new_user_read_response.reg_id will be None as per Postgres model
    # new_user_read_response.conference_id will be None
    
    return new_user_read_response


@router.post("/update")
async def update_user_data(payload: UserUpdateSchema, db: AsyncSession = Depends(get_db)):
    user_id = str(payload.user_id) # Ensure user_id is string UUID

    now_utc = datetime.now(timezone.utc)
    infinity_date = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)

    # --- Update Skills (remains unchanged) ---
    if payload.user_skills:
        for skill_payload in payload.user_skills:
            skill_info = await find_or_create_skill_interest(db, skill_payload.skill_name, entity_type='skill')
            if skill_info:
                await db.merge(UserSkill(user_id=user_id, skill_interest_id=skill_info["skill_interest_id"], assigned_at=skill_payload.assigned_at or now_utc, valid_from=skill_payload.valid_from or now_utc, valid_to=skill_payload.valid_to or infinity_date))
                await create_or_update_user_skill_neo4j(user_id, skill_info["name"])
                data_was_updated = True

    # --- Update Interests (remains unchanged) ---
    if payload.user_interests:
        for interest_payload in payload.user_interests:
            interest_info = await find_or_create_skill_interest(db, interest_payload.interest_name, entity_type='interest')
            if interest_info:
                await db.merge(UserInterest(user_id=user_id, skill_interest_id=interest_info["skill_interest_id"], assigned_at=interest_payload.assigned_at or now_utc, valid_from=interest_payload.valid_from or now_utc, valid_to=interest_payload.valid_to or infinity_date))
                await create_or_update_user_interest_neo4j(user_id, interest_info["name"])
                data_was_updated = True

    # --- Update Job Roles (remains unchanged) ---
    if payload.user_job_roles:
        for role_payload in payload.user_job_roles:
            job_role_info = await find_or_create_job_role(db, role_payload.job_role_title)
            if job_role_info:
                await db.merge(UserJobRole(user_id=user_id, job_role_id=job_role_info["job_role_id"], assigned_at=role_payload.valid_from or now_utc, valid_from=role_payload.valid_from or now_utc, valid_to=role_payload.valid_to or infinity_date))
                await create_or_update_user_job_role_neo4j(user_id, job_role_info["title"])
                data_was_updated = True

    # --- Update Company (remains unchanged) ---
    if payload.user_company:
        company_payload = payload.user_company
        company_info = await find_or_create_company(db, company_payload.company_name)
        if company_info:
            await db.merge(UserCompany(user_id=user_id, company_id=company_info["company_id"], assigned_at=company_payload.assigned_at or now_utc, valid_from=company_payload.valid_from or now_utc, valid_to=company_payload.valid_to or infinity_date))
            await create_or_update_user_company_neo4j(user_id, company_info["name"], is_current=True)
            data_was_updated = True

    if payload.location: # 'location' is the string name from UserUpdateSchema
        # 1. Find or Create the canonical Location entity in Postgres (and get its ID)
        location_info = await find_or_create_location(db, payload.location)
        
        # 2. Create/Update record in user_location table (Postgres)
        # This links the user to the canonical location entity.
        pg_user_location =UserLocation(
            user_id=UUID(user_id), # The user being updated
            location_id=UUID(location_info["location_id"]), # The canonical location ID
            assigned_at=now_utc,
            valid_from=now_utc,
            valid_to=infinity_date # Mark as current indefinitely
        )
        db.add(pg_user_location) # Stage the new user-location association record
        await update_user_location_neo4j(user_id, location_info["name"])
        # IMPORTANT: The old `await update_user_location_neo4j` call is REMOVED from here,
        # as per your request to separate knowledge graph generation for location.
        # You would later add a new Neo4j call for location here if needed.
        
        data_was_updated = True
        print(f"User {user_id} successfully linked to Location {location_info['name']} (ID: {location_info['location_id']}) in PostgreSQL.")

    await db.commit() # This commit will now save the UserLocation record too.
    
    # ... (rest of your endpoint code) ...
    return {"msg": "User update successful"}

@router.post("/login", response_model=UserLoginResponse)
async def login_user(payload: UserLoginPayload, db: AsyncSession = Depends(get_db)):
    # 1. Check if user exists
    result = await db.execute(select(User).filter(User.email == payload.email))
    user = result.scalars().first()
    if not user or user.password_hash != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # 2. Generate token (opaque string UUID for now)
    token = str(uuid.uuid4())

    # 3. Return user info + token
    return UserLoginResponse(
        user_id=str(user.user_id),
        name=user.full_name,
        email=user.email,
        token=token,
        registration_category=user.registration_category
    )



@router.get("/users/{user_id}/conferences", response_model=List[ConferenceResponse])
async def get_user_conferences(
    user_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    # Query UserRegistration for active registrations
    result = await db.execute(
        select(UserRegistration.conference_id)
        .where(
            UserRegistration.user_id == user_id,
            UserRegistration.status.in_(["claimed"]),
            UserRegistration.valid_to > datetime.now(timezone.utc)
        )
        .limit(limit)
        .offset(offset)
    )
    registrations = result.scalars().all()
    print(f"Registrations:{registrations}")
    if not registrations:
        return []

    # Get conference IDs
    conference_ids = [reg for reg in registrations]

    # Query Conferences with joined Location
    result = await db.execute(
        select(PgConference)
        .options(joinedload(PgConference.location_rel))  # Eagerly load location_rel
        .where(
            PgConference.conference_id.in_(conference_ids),
            PgConference.valid_to > datetime.now(timezone.utc)
        )
        .limit(limit)
        .offset(offset)
    )
    conferences = result.scalars().all()
    return conferences

@router.get("/recommendations/reg_id/{user_id}", response_model=Dict[str, Any])
async def get_recommendations_attendee(
    user_id: str,
    limit: int = 100, # Allow a higher limit for the unified list
    people_service: PeopleService = Depends(get_people_service_dependency)
):
    """
    Fetches unified recommendations by combining demographic, interest, and skill similarities
    with weighted and conditional logic, and ensures commonalities are fully populated.
    """
    try:
        # Step 1: Fetch recommendations from all specialized categories
        # Fetch more than the final limit, as some might be filtered/ranked lower
        fetch_limit_per_category = limit * 3 

        demographics_recs = await people_service.get_demographics_based_recommendations(user_id, limit=fetch_limit_per_category)
        interests_recs = await people_service.get_similar_interests_recommendations(user_id, limit=fetch_limit_per_category)
        skills_recs = await people_service.get_similar_skills_recommendations(user_id, limit=fetch_limit_per_category)

        # Step 2: Combine and Deduplicate (and store individual scores)
        combined_users: Dict[str, Dict[str, Any]] = {} # Key: UserID, Value: user_data dict

        def add_rec_data(rec_list, category_key):
            for rec in rec_list:
                uid = rec['UserID']
                if uid not in combined_users:
                    # Initialize with base data and default scores/empty commonalities
                    combined_users[uid] = {
                        'UserID': uid,
                        'RecommendedUser': rec['RecommendedUser'],
                        'Role': rec.get('Role'),
                        'YearsExperience': rec.get('YearsExperience'),
                        'Scores': { 'Demographics': 0.0, 'Interests': 0.0, 'Skills': 0.0 },
                        'CommonalityRaw': {} # Store raw commonality lists to deduplicate later
                    }
                # Update specific score
                combined_users[uid]['Scores'][category_key] = rec['SimilarityScore']
                
                # Store raw commonalities from this specific query for later deduplication
                for key in ['SharedCompanies', 'SharedLocations', 'SharedUniversities', 'CommonInterests', 'CommonSkills']:
                    if key in rec and rec[key]: # Only add if key exists and list is not empty
                        combined_users[uid]['CommonalityRaw'].setdefault(key, []).extend(rec[key])

        add_rec_data(demographics_recs, 'Demographics')
        add_rec_data(interests_recs, 'Interests')
        add_rec_data(skills_recs, 'Skills')

        # Step 3: Calculate Final Score and Process Commonalities
        final_recommendations_list = []
        for _, user_data in combined_users.items():
            demo_score = user_data['Scores']['Demographics']
            interest_score = user_data['Scores']['Interests']
            skill_score = user_data['Scores']['Skills']

            final_weighted_score = 0.0
            
            
            final_weighted_score = (demo_score * 0.60) + (interest_score * 0.20) + (skill_score * 0.20)
            
            
            user_data['FinalScore'] = final_weighted_score

            # Deduplicate and finalize commonalities for display
            final_common_data = {}
            for key, raw_list in user_data['CommonalityRaw'].items():
                final_common_data[key] = list(set(raw_list)) # Use set to deduplicate

            user_data['Commonalities'] = final_common_data # Replace raw with final deduplicated
            del user_data['CommonalityRaw'] # Remove temporary raw data

            # Add to the list to be sorted
            final_recommendations_list.append(user_data)

        # Step 4: Rank and Return Top 'limit' Recommendations
        final_recommendations_list.sort(key=lambda x: x['FinalScore'], reverse=True)

        return {
            "user_id": user_id,
            "category": "Unified Recommendations",
            "recommendations": final_recommendations_list[:limit]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching unified recommendations: {e}")