# app/api/v1/endpoints/events.py

from fastapi import APIRouter, Depends, HTTPException, status,UploadFile, File, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import ARRAY 
from sqlalchemy import or_
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session 
import csv
import io
import logging
logger = logging.getLogger(__name__) # Good practice for logging
from app.db.neo4j import create_user_conference_registration_neo4j
from app.models.person import AttendeeClaimRegistrationRequest, AttendeeClaimRegistrationResponse, ClaimUserIdRegistration
# Import Postgres models related to events/conferences/sessions
# YOU MUST ADAPT THESE IMPORTS BASED ON YOUR ACTUAL POSTGRES MODEL FILE
from postgres.models import Event as PgEvent # Your 'events' table model
from postgres.models import Conference as PgConference # Your 'conferences' table model
from postgres.models import User # To link organizers/presenters/users
from app.models.person import BulkRegistrationUploadResponse
# Import Pydantic schemas for Conference and Event creation
from app.models.person import ConferenceCreate, ConferenceRead, EventCreate, EventRead, EventType,UserRegistrationBase # Import EventType Enum
from postgres.models import UserRegistration,EventTopic
from postgres.models import RegistrationCategory 
from postgres.models import Location
from pydantic import ValidationError, HttpUrl
from sqlalchemy.orm import selectinload
from sqlalchemy import update
# Import Neo4j CRUD functions for Conference/Event
from neo4j.exceptions import ServiceUnavailable
from app.db.neo4j import (
    create_event_node_neo4j,
    create_conference_node_if_not_exists,
    link_user_to_conference,
    create_presenter_event_link_neo4j, create_exhibitor_event_link_neo4j,
    create_user_conference_registration_neo4j,create_speaker_event_link_neo4j,update_user_node_neo4j
)
from app.services.process import ( # Assuming these are defined in app.services.process.py
    find_or_create_skill_interest,
    find_or_create_company,
    find_or_create_job_role,
    find_or_create_location,
    parse_delimited_string
)


# NEW IMPORT: Import the helper for finding/creating locations
# Ensure this function is defined in app/services/process.py

# Assuming get_db provides AsyncSession for Postgres
from app.db.database import get_db

router = APIRouter()


# @router.post("/conferences/", response_model=ConferenceRead, status_code=status.HTTP_201_CREATED)
# async def create_conference_api(conference_payload: ConferenceCreate, db: AsyncSession = Depends(get_db)):
#     """
#     Creates a new Conference record in PostgreSQL (conferences table) and synchronizes it to Neo4j.
#     Location is now canonicalized via find_or_create_location.
#     """
#     new_conference_uuid = uuid.uuid4()

#     organizer_pg_id = None
#     if conference_payload.organizer_id:
#         organizer_result = await db.execute(select(User).filter(User.user_id == conference_payload.organizer_id))
#         organizer_pg = organizer_result.scalars().first()
#         if not organizer_pg:
#             raise HTTPException(status_code=404, detail=f"Organizer User with ID {conference_payload.organizer_id} not found.")
#         organizer_pg_id = organizer_pg.user_id

#     # Process location_name to get canonical location_id
#     location_pg_id = None
#     neo4j_location_name = None
#     if conference_payload.location_name:
#         location_info = await find_or_create_location(db, conference_payload.location_name)
#         location_pg_id = UUID(location_info["location_id"])
#         neo4j_location_name = location_info["name"]

#     # Create record in Postgres 'conferences' table
#     pg_conference = PgConference(
#         conference_id=new_conference_uuid,
#         name=conference_payload.name,
#         description=conference_payload.description,
#         start_date=conference_payload.start_date,
#         end_date=conference_payload.end_date,
#         location_id=location_pg_id, # Store the canonical location ID
#         venue_details=conference_payload.venue_details,
#         organizer_id=organizer_pg_id,
#         logo_url=str(conference_payload.logo_url) if conference_payload.logo_url else None,
#         website_url=str(conference_payload.website_url) if conference_payload.website_url else None
#     )
#     db.add(pg_conference)
#     await db.commit() # Commit the new conference to the DB

#     # --- FIX FOR MISSINGGREENLET ERROR ---
#     # After commit, the object is detached or relationships might not be loaded.
#     # Re-query the object and eagerly load the 'location_rel' relationship.
#     stmt_loaded_conference = select(PgConference).options(selectinload(PgConference.location_rel)).filter(
#         PgConference.conference_id == pg_conference.conference_id # Filter by the ID of the conference we just created
#     )
#     result_loaded_conference = await db.execute(stmt_loaded_conference)
#     pg_conference_loaded = result_loaded_conference.scalar_one_or_none()
    
#     if not pg_conference_loaded: # This should ideally not happen after a successful commit
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve newly created conference with location data for response.")

#     # Synchronize to Neo4j (use the eagerly loaded object for its properties)
#     await create_conference_node_neo4j(
#         conference_id=str(pg_conference_loaded.conference_id), # Use loaded object
#         name=pg_conference_loaded.name,
#         description=pg_conference_loaded.description,
#         start_date=pg_conference_loaded.start_date,
#         end_date=pg_conference_loaded.end_date,
#         location=pg_conference_loaded.location_name, # Accesses the @property which now has loaded relationship
#         organizer_id=str(organizer_pg_id) if organizer_pg_id else None,
#         logo_url=pg_conference_loaded.logo_url,
#         website_url=pg_conference_loaded.website_url
#     )
#     # Return using the eagerly loaded object
#     return ConferenceRead.from_orm(pg_conference_loaded)

# ... (rest of the file remains unchanged) ...
# --- Endpoint to Create a New Event (Component) for a Conference ---

# Upload Event Csv
@router.post("/conferences/{conference_id}/events/upload-csv", status_code=status.HTTP_202_ACCEPTED)
async def upload_events_csv(
    conference_id: UUID,
    organizer_id: UUID, # Included for authorization
    file: UploadFile = File(..., description="CSV file containing event details."),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Uploads a CSV file containing event details for a specific conference.
    Events are processed in a background task.
    CSV columns are expected to match EventCreate fields (e.g., 'title', 'start_time', 'topics' as comma-separated).
    """
    stmt = select(PgConference).filter(PgConference.conference_id == conference_id, PgConference.organizer_id == organizer_id)
    conference = await db.scalar(stmt)
    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found or not managed by this organizer.")

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV files are allowed.")

    content = await file.read()
    try:
        csv_string = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Could not decode CSV file. Ensure it's UTF-8 encoded.")

    background_tasks.add_task(process_event_csv_background, conference_id, csv_string)

    return {"message": f"Event CSV upload for conference {conference_id} initiated. Processing in background."}


async def process_event_csv_background(conference_id: UUID, csv_string: str):
    """
    Background task to process event CSV data, insert into Postgres, and sync to Neo4j.
    Stores organizer role identifiers directly on the Event table.
    """
    csv_file = io.StringIO(csv_string)
    reader = csv.DictReader(csv_file)

    async for db_session in get_db():
        db: AsyncSession = db_session
        processed_count = 0
        failed_entries = []

        try:
            conf_exists = await db.scalar(select(PgConference).filter(PgConference.conference_id == conference_id))
            if not conf_exists:
                print(f"Background Task Error: Conference {conference_id} not found during event CSV processing. Aborting.")
                return

            for i, row in enumerate(reader):
                current_row_info = f"CSV Row {i+2} (Title: {row.get('title', 'N/A')})"
                topic_id_map: Dict[str, str] = {}
                try:
                    # --- 1. Data Preparation for Pydantic (STRICTLY using fields from YOUR concise EventCreate) ---
                    event_data = {
                        "conference_id": str(conference_id),
                        "title": row.get("title"),
                        "description": row.get("description"),
                        "event_type": row.get("event_type"),
                        "start_time": row.get("start_time"),
                        "end_time": row.get("end_time"),
                        "venue_details": row.get("venue_details"),
                        "topics": parse_delimited_string(row.get("topics")),
                        # Mapping CSV columns to EventCreate Pydantic fields
                        "presenter_reg_ids": parse_delimited_string(row.get("presenter_reg_ids")), # Matches CSV column to Pydantic field
                        "exhibitor_reg_ids": parse_delimited_string(row.get("exhibitor_reg_ids")), # Matches CSV column to Pydantic field
                        "speaker_reg_ids": parse_delimited_string(row.get("speaker_reg_ids")), # Matches CSV column to Pydantic field
                    }

                    event_payload = EventCreate(**event_data)
                    new_event_uuid = uuid.uuid4()

                    # --- 2. Postgres Event Table Insertion ---
                    pg_event = PgEvent(
                        event_id=new_event_uuid,
                        conference_id=event_payload.conference_id,
                        title=event_payload.title,
                        description=event_payload.description,
                        event_type=event_payload.event_type.value,
                        start_time=event_payload.start_time,
                        end_time=event_payload.end_time,
                        venue_details=event_payload.venue_details,
                        # Store identifier lists directly on the Event model using the correct column names
                        presenter_reg_ids=event_payload.presenter_reg_ids,
                        exhibitor_reg_ids=event_payload.exhibitor_reg_ids,
                        speaker_reg_ids=event_payload.speaker_reg_ids,
                    )
                    db.add(pg_event)
                    await db.flush()

                    # --- 3. Process Interests and link in Postgres (EventInterest) ---
                    for interest_name in event_payload.topics:
                        interest_info = await find_or_create_skill_interest(db, interest_name,entity_type='interest')
                        topic_id_map[interest_name] = interest_info["skill_interest_id"] # Store name -> Postgres interest_id

                        pg_event_interest = EventTopic(event_id=pg_event.event_id, topic_id=UUID(interest_info[
                            "skill_interest_id"]))
                        db.add(pg_event_interest)

                    await db.commit() # Commit all changes for this event to Postgres

                    # --- 4. Synchronize to Neo4j AFTER Postgres commit ---
                    neo4j_event_type = event_payload.event_type.value
                    await create_event_node_neo4j(
                        event_id=str(pg_event.event_id),
                        conference_id=str(pg_event.conference_id),
                        title=pg_event.title,
                        description=pg_event.description,
                        event_type=neo4j_event_type,
                        start_time=pg_event.start_time,
                        end_time=pg_event.end_time,
                        venue_details=pg_event.venue_details,
                        topics=event_payload.topics, # List of names for Neo4j
                        topic_id_map=topic_id_map, # Map for Neo4j Topic node ID
                        # Pass organizer identifiers directly to Neo4j function
                        
                    )

                    processed_count += 1
                    print(f"Successfully processed {current_row_info}")

                except ValidationError as e:
                    error_details = e.errors()
                    print(f"Validation error for {current_row_info}: {error_details}")
                    failed_entries.append(f"{current_row_info} (Validation Error): {error_details}")
                    await db.rollback()
                except Exception as e:
                    print(f"Error processing {current_row_info}: {e}")
                    failed_entries.append(f"{current_row_info} (Processing Error): {str(e)}")
                    await db.rollback()

            print(f"Background Task Complete: Processed {processed_count} events for conference {conference_id}.")
            if failed_entries:
                print(f"Failed entries: {len(failed_entries)}. Details: {failed_entries}")
        except Exception as e:
            print(f"FATAL Background Task Error for conference {conference_id}: {e}")
            await db.rollback()
        finally:
            await db.close()

# --- User Registration Upload (existing code) ---
@router.post(
    "/api/v1/organizers/{organizer_id}/conferences/{conference_id}/attendees/upload-csv",
    response_model=BulkRegistrationUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload CSV of Attendee Registration IDs and details for a Conference by Organizer ID"
)
async def upload_attendees_csv(
    organizer_id: UUID,
    conference_id: UUID,
    file: UploadFile = File(..., description="CSV file containing registration IDs and user details."),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(PgConference).filter(PgConference.conference_id == conference_id, PgConference.organizer_id == organizer_id)
    conference = await db.scalar(stmt)

    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found or not managed by this organizer.")

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV files are allowed.")

    content = await file.read()
    try:
        csv_string = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Could not decode CSV file. Ensure it's UTF-8 encoded.")

    csv_file = io.StringIO(csv_string)
    reader = csv.DictReader(csv_file)

    successfully_registered_count = 0
    skipped_duplicates_count = 0
    failed_entries_list = []
    total_ids_in_file_count = 0

    new_user_registrations = []

    try:
        for i, row in enumerate(reader):
            total_ids_in_file_count += 1
            try:
                # Prepare data for Pydantic validation for UserRegistrationBase
                # Ensure CSV column names match the Pydantic fields
                reg_data = {
                    "reg_id": row.get("reg_id"),
                    "conference_id": str(conference_id),
                    "valid_from": row.get("valid_from"),
                    "valid_to": row.get("valid_to"),
                  
                }
                reg_payload = UserRegistrationBase(**reg_data)

                stmt = select(UserRegistration).filter(
                    UserRegistration.reg_id == reg_payload.reg_id
                )
                result = await db.execute(stmt)
                existing_registration = result.scalars().first()

                if existing_registration:
                    skipped_duplicates_count += 1
                    continue

                new_registration = UserRegistration(
                    reg_id=reg_payload.reg_id,
                    conference_id=conference_id,
                    user_id=None,
                    registered_by_organizer_at=datetime.now(timezone.utc),
                    status="pre_registered",
                    valid_from=reg_payload.valid_from,
                    valid_to=reg_payload.valid_to,
                    # Populate new organizer_supplied fields
                    
                )
                new_user_registrations.append(new_registration)
                successfully_registered_count += 1

            except ValidationError as e:
                print(f"Validation error for row {i+2} in UserReg CSV: {e}")
                failed_entries_list.append(f"Row {i+2} (Validation Error): {e.errors()}")
            except Exception as e:
                print(f"Error processing row {i+2} in UserReg CSV: {e}")
                failed_entries_list.append(f"Row {i+2} (Processing Error): {str(e)}")

        db.add_all(new_user_registrations)
        await db.commit()

    except Exception as e:
        await db.rollback()
        print(f"FATAL: Database error during bulk user registration insert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected database error occurred during bulk registration. Error: {e}"
        )

    return BulkRegistrationUploadResponse(
        conference_id=conference_id,
        file_name=file.filename,
        total_ids_in_file=total_ids_in_file_count,
        successfully_registered=successfully_registered_count,
        skipped_duplicates=skipped_duplicates_count,
        failed_entries=failed_entries_list,
        message=f"CSV upload processed. Successfully pre-registered {successfully_registered_count} users for conference {conference_id}."
    )



# app/api/v1/endpoints/events.py

# ... (existing imports) ...

# app/api/v1/endpoints/events.py

# ... (existing imports) ...

# app/api/v1/endpoints/events.py

# ... (existing imports, ensure selectinload is *not* imported if no longer used elsewhere in this file) ...
# from sqlalchemy.orm import selectinload # <--- REMOVE THIS LINE if not used by other parts of events.py

# ... (rest of the file) ...


@router.post(
    "/api/v1/users/me/check-claim-status",
    response_model=AttendeeClaimRegistrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate User and Claim Registration ID",
    description="""Allows a user to log in with their email and password, and simultaneously claim their unique registration ID (reg_id) for a conference.
    If the reg_id is already claimed by this user, it will act as a successful login/confirmation.
    **(Currently uses plain-text password comparison for development)**
    """
)
async def check_registration_claim_status(
    request_payload: AttendeeClaimRegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        # --- 1. Fetch Registration Record ---
        stmt = select(UserRegistration).filter(
            UserRegistration.reg_id == request_payload.reg_id
        )
        result = await db.execute(stmt)
        registration_record = result.scalars().first()

        # --- 2. Handle Not Found ---
        if not registration_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid registration ID."
            )

        # --- 3. Handle Already Claimed ---
        if registration_record.user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This registration ID has already been claimed."
            )

        # --- 4. Handle Invalid Status ---
        if registration_record.status != 'pre_registered':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration ID is not claimable (status = {registration_record.status})."
            )

        # --- 5. Valid & Unclaimed ---
        action_message = "Registration ID is unclaimed and valid"
        
        return AttendeeClaimRegistrationResponse(
            message=action_message,
            proceed = True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error while checking claim status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )

@router.post("/users/{user_id}/claim-registration")
async def claim_registration(
    user_id: UUID,
    reg_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        # --- 1. Fetch User from Token ---
        # Placeholder: replace with actual token validation
        

        # --- 2. Fetch Registration Record ---
        stmt = select(UserRegistration).filter(
            UserRegistration.reg_id == reg_id
        )
        result = await db.execute(stmt)
        registration_record = result.scalars().first()

        # --- 3. Handle Not Found ---
        if not registration_record:
            raise HTTPException(
                status_code=400,
                detail="Invalid registration ID."
            )

        # --- 4. Handle Already Claimed ---
        if registration_record.user_id is not None:
            raise HTTPException(
                status_code=409,
                detail="This registration ID has already been claimed."
            )

        # --- 5. Handle Invalid Status ---
        if registration_record.status != 'pre_registered':
            raise HTTPException(
                status_code=400,
                detail=f"Registration ID is not claimable (status = {registration_record.status})."
            )

        # --- 6. Claim the Registration ---
        await db.execute(
            update(UserRegistration)
            .where(UserRegistration.reg_id == reg_id)
            .values(
                user_id=user_id,
                status="claimed",
                valid_from=datetime.now(timezone.utc),
                valid_to=datetime.max.replace(tzinfo=timezone.utc)
            )
        )
        await db.commit()
        # Fetch full registration after update
        result = await db.execute(
            select(UserRegistration).filter(UserRegistration.reg_id == reg_id)
        )
        updated_registration = result.scalars().first()
        print(updated_registration)
        if updated_registration and updated_registration.conference_id:
            # Derive relationship type
            relationship = {
                "attendee": "ATTENDS",
                "exhibitor": "EXHIBITS",
                "speaker": "SPEAKS_AT"
            }.get(updated_registration.registration_category.name, "PARTICIPATES")

    # Make sure Neo4j node exists
            try:
                await create_conference_node_if_not_exists(
                    conference_id=str(updated_registration.conference_id)
                )

    # Create Neo4j relationship
                await link_user_to_conference(
                    user_id=str(user_id),
                    conference_id=str(updated_registration.conference_id),
                    relationship_type=relationship
                )
            except ServiceUnavailable:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not connect to Neo4j database."
                )

        # --- 7. Return True ---
        action_message = "Registration ID is unclaimed and valid"
        
        return AttendeeClaimRegistrationResponse(
            message=action_message,
            proceed = True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error while claiming registration: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred."
        ) 

""""
FOR CREATiNG SINGLE EVENt PER CONF
@router.post("/conferences/{conference_id_from_url}/events/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event_api(
   
    event_payload: EventCreate,
    db: AsyncSession = Depends(get_db)
):
 
    # 1. Validate conference_id consistency (URL vs. Payload)
   
   
    # 3. Generate new UUID for this event record (event_id in Postgres)
    new_event_uuid = uuid.uuid4()

    # (No location processing logic for events here, as event_details is a direct string)

    # 4. Create record in Postgres 'events' table
    pg_event = PgEvent(
        event_id=new_event_uuid,
        conference_id=event_payload.conference_id,
        title=event_payload.title,
        description=event_payload.description,
        event_type=event_payload.event_type.value,
        start_time=event_payload.start_time,
        end_time=event_payload.end_time,
        
        # --- NEW: Save event_details directly as a string ---
        venue_details=event_payload.venue_details, # Pass the string from payload
        # location_id is no longer part of PgEvent here

        # organizer_id is not taken from payload in EventCreate now, set as per your model
    )
    db.add(pg_event)
    await db.commit()
    await db.refresh(pg_event)

    neo4j_event_type = None
    if pg_event.event_type:
        if isinstance(pg_event.event_type, EventType):
            neo4j_event_type = pg_event.event_type.value
        else:
            neo4j_event_type = str(pg_event.event_type)

    # 5. Synchronize to Neo4j
    await create_event_node_neo4j(
        event_id=str(pg_event.event_id),
        conference_id=str(pg_event.conference_id),
        title=pg_event.title,
        event_type=neo4j_event_type,
        start_time=pg_event.start_time,
        end_time=pg_event.end_time,
        # --- REMOVED: location=pg_event.venue_detail ---
        # As per your instruction not to store event venue_detail in Neo4j
    )
    
    # ... (Link presenters/exhibitors to event) ...

    return EventRead.from_orm(pg_event)
"""
