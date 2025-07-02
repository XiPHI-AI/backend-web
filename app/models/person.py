# app/models/person.py

from pydantic import BaseModel, EmailStr, HttpUrl, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum as PyEnum # Use PyEnum to avoid clash with Pydantic's Field

# --- ENUMS (SYNCHRONIZED) ---
class RegistrationCategory(str, PyEnum):
    attendee = "attendee"
    speaker = "speaker"
    organizer = "organizer"
    exhibitor = "exhibitor"
    presenter = "presenter"

class EventType(str, PyEnum):
    conference = "conference"
    presentation = "presentation"
    exhibition = "exhibition"
    workshop = "workshop"
    panel = "panel"
    keynote = "keynote"
    networking_event = "networking_event"
    product_launch = "product_launch"
    poster_session = "poster_session" # Added for consistency with broader event types
    award_ceremony = "award_ceremony" # Added for consistency
    other = "other"

# --- SHARED ENTITY SCHEMAS ---
class SingleUserSkill(BaseModel):
    skill_name : str
    assigned_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

class SingleUserInterest(BaseModel):
    interest_name : str
    assigned_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

class SingleUserJobRole(BaseModel):
    job_role_title : str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

class SingleUserCompany(BaseModel):
    company_name: str
    assigned_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


# --- USER SCHEMAS (UNCHANGED from your provided) ---
class UserCreate(BaseModel):
    registration_id: str
    email: EmailStr
    password_hash: str
    full_name: str
    avatar_url: Optional[HttpUrl] = None
    biography: Optional[str] = None
    phone: Optional[str] = None
    registration_category: RegistrationCategory = RegistrationCategory.attendee

class UserRead(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    registration_category: RegistrationCategory
    model_config = ConfigDict(from_attributes=True)

class UserUpdateSchema(BaseModel):
    user_id: UUID
    user_skills: Optional[List[SingleUserSkill]] = None
    user_job_roles: Optional[List[SingleUserJobRole]] = None
    user_interests: Optional[List[SingleUserInterest]] = None
    user_company: Optional[SingleUserCompany] = None
    location: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# --- CONFERENCE SCHEMAS (UNCHANGED from your provided) ---
class ConferenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    location_name: Optional[str] = None
    organizer_id: Optional[UUID] = None
    logo_url: Optional[HttpUrl] = None
    website_url: Optional[HttpUrl] = None
    venue_details:Optional[str]=None

class ConferenceRead(ConferenceCreate):
    conference_id: UUID
    model_config = ConfigDict(from_attributes=True)


# --- EVENT SCHEMAS (UPDATED based on your last provided EventCreate and corrections) ---
class EventCreate(BaseModel):
    conference_id: UUID
    title: str
    description: Optional[str] = None
    event_type: EventType
    start_time: datetime
    end_time: datetime
    venue_details: Optional[str] = None
    topics: Optional[List[str]] = Field(None, description="List of topic/interest names covered by the event.")
    # Corrected types to List[str] as per CSV parsing and your explicit request
    presenter_reg_ids: Optional[List[str]] = None
    exhibitor_reg_ids: Optional[List[str]] = None
    speaker_reg_ids: Optional[List[str]] = None # This is distinct from presenter_reg_ids in your schema


class EventRead(EventCreate):
    event_id: UUID
    model_config = ConfigDict(from_attributes=True)


# --- USER REGISTRATION SCHEMAS (UPDATED to include organizer_supplied fields) ---
class UserRegistrationBase(BaseModel):
    reg_id: str = Field(..., min_length=1, max_length=100, description="Unique registration code for the attendee.")
    conference_id: UUID
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    email: Optional[EmailStr] = None # Assuming this is organizer_supplied_email

    

class UserRegistrationRead(UserRegistrationBase):
    user_id: Optional[UUID] = None
    registered_by_organizer_at: datetime
    claimed_by_user_at: Optional[datetime] = None
    status: str
    model_config = ConfigDict(from_attributes=True)


# --- NEW SCHEMAS FOR USER EVENT FEEDBACK AND ATTENDANCE (as provided by you) ---
class UserEventFeedbackCreate(BaseModel):
    user_id: UUID
    event_id: UUID
    is_interested: bool
    comment: Optional[str] = None

class UserEventFeedbackRead(UserEventFeedbackCreate):
    feedback_id: UUID
    feedback_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserEventAttendanceCreate(BaseModel):
    user_id: UUID
    event_id: UUID
    status: str = "attended"

class UserEventAttendanceRead(UserEventAttendanceCreate):
    attendance_id: UUID
    attended_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- OTHER API SPECIFIC SCHEMAS (UNCHANGED from your provided) ---
class BulkRegistrationUploadResponse(BaseModel):
    conference_id: UUID
    file_name: str
    total_ids_in_file: int
    successfully_registered: int
    skipped_duplicates: int
    failed_entries: List[str] = Field(default_factory=list)
    message: str

class AttendeeClaimRegistrationRequest(BaseModel):
    reg_id: str = Field(..., min_length=1, max_length=100)

class AttendeeClaimRegistrationResponse(BaseModel):
    message: str
    proceed: bool