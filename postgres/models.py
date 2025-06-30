# postgres/models.py

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Enum, # For SQLAlchemy Enum type
    Boolean,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID, ARRAY # ARRAY for generic Python arrays, if you use it
from sqlalchemy.sql import func, text
from pgvector.sqlalchemy import Vector # For vector type
import uuid
import enum # For Python's enum.Enum
import datetime # For datetime.datetime and datetime.timezone

from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID 
from sqlalchemy.orm import Mapped, mapped_column, relationship
# No need for from sqlalchemy.dialects.postgresql import UUID as PG_UUID
# just use UUID if it's from sqlalchemy.dialects.postgresql
# If you used PG_UUID in other files, ensure consistency.
# Here, directly using UUID from sqlalchemy.dialects.postgresql should be fine.

Base = declarative_base()

# ────────────────────────────────────────────────────────────────────────────────
# ENUM DEFINITIONS (Python enums)
# ────────────────────────────────────────────────────────────────────────────────

class RegistrationCategory(enum.Enum):
    attendee = "attendee"
    organizer = "organizer"
    exhibitor = "exhibitor"
    presenter = "presenter"

class EventType(enum.Enum):
    presentation = "presentation"
    exhibition = "exhibition"
    workshop = "workshop"
    panel = "panel"
    keynote = "keynote"
    concert = "concert"

class ConnectionStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"
    ignored = "ignored"

class MessageDirection(enum.Enum):
    sent = "sent"
    received = "received"

class NotificationType(enum.Enum):
    event_reminder = "event_reminder"
    connection_request = "connection_request"
    interest_match = "interest_match"
    content_suggestion = "content_suggestion"
    announcement = "announcement"

class ContentType(enum.Enum):
    popular = "popular"
    library = "library"

class AttendanceStatus(enum.Enum):
    interested = "interested"
    going = "going"


# ────────────────────────────────────────────────────────────────────────────────
# MODELS
# ────────────────────────────────────────────────────────────────────────────────

class JobRole(Base):
    __tablename__ = "job_roles"

    job_role_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(String(255), nullable=False, unique=True)
    embedding = Column(Vector(384), nullable=True) # Assuming nullable=True for new column
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(String(255), nullable=False, unique=True)
    type =Column(String(255),nullable=False,unique=True)
    embedding = Column(Vector(384), nullable=True) # Assuming nullable=True for new column
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class Recommendations(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    recommended_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    score = Column(Integer, nullable=False)
    context = Column(String(255))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class User(Base):
    __tablename__ = "users"

    user_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )
    email = Column(String(255), nullable=True, unique=True)
    password_hash = Column(Text, nullable=True)
    first_name = Column(Text, nullable= True)
    last_name = Column(Text, nullable=True)
    avatar_url = Column(Text)
    biography = Column(Text)
    phone = Column(Text)
    registration_category = Column(
        Enum(
            RegistrationCategory,
            name="registration_category"
        ),
        nullable=False,
        default=RegistrationCategory.attendee
    )

    job_role = relationship("UserJobRole", backref="user")
    current_company = relationship("UserCompany", backref="user")
    
    # Assuming location_associations relationship will be added by UserLocation backref
    # location_associations = relationship("UserLocation", backref="user") # Can define explicitly here if preferred

    @property
    def current_job_role(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        return next(
            (r for r in self.job_role if r.valid_to > now),
            None
        )

    @property
    def current_company(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        return next(
            (c for c in self.company if c.valid_to > now),
            None
        )


class UserRegistration(Base):
    __tablename__ = "user_registrations"

    # reg_id is the Primary Key as per our final agreement and your existing table structure
    reg_id = Column(String(255), primary_key=True, nullable=False) # FIX: Removed redundant unique=True

    # user_id (attendee_user_id in our discussions) MUST BE NULLABLE INITIALLY
    # It's only populated when the user claims the reg_id.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True
    )

    conference_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conferences.conference_id", ondelete="CASCADE"),
        nullable=False
    )
    # Renamed/Added timestamp columns as per our schema
    registered_by_organizer_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    claimed_by_user_at = Column(DateTime(timezone=True), nullable=True) # Null until user claims it

    # Added status column
    status = Column(String(50), nullable=False, default="pre_registered") # e.g., 'pre_registered', 'claimed', 'cancelled'

    # valid_from and valid_to with your specified defaults and nullable=False
    valid_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to = Column(DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))

    # Relationships
    user = relationship("User", backref="registrations_link")
    conference = relationship("Conference", backref="user_registrations")

    def __repr__(self):
        return f"<UserRegistration(reg_id='{self.reg_id}', conference_id='{self.conference_id}', user_id='{self.user_id}', status='{self.status}')>"

class Tag(Base):
    __tablename__ = "tags"

    tag_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(Text, nullable=False)
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class UserTag(Base):
    __tablename__ = "user_tags"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        primary_key=True
    )
    tag_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tags.tag_id", ondelete="CASCADE"), # Added ondelete
        primary_key=True
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )
    assigned_at= Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


class SkillInterest(Base):
    __tablename__ = "skills_interests"

    skill_interest_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    embedding = Column(Vector(384), nullable=True)
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class UserSkill(Base):
    __tablename__ = "user_skills"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    skill_interest_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "skills_interests.skill_interest_id",
            ondelete="CASCADE"
        ),
        primary_key=True
    )
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class UserInterest(Base):
    __tablename__ = "user_interests"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    skill_interest_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "skills_interests.skill_interest_id",
            ondelete="CASCADE"
        ),
        primary_key=True
    )
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class UserJobRole(Base):
    __tablename__ = "user_job_role"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    job_role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_roles.job_role_id", ondelete="CASCADE"),
        primary_key=True
    )
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class UserCompany(Base):
    __tablename__ = "user_company"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    # Renamed: use company_id to match foreign key clearly
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        primary_key=True
    )
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


# postgres/models.py

# ... (other imports and models remain unchanged) ...

class Conference(Base):
    __tablename__ = "conferences"

    conference_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(Text, nullable=False)
    description = Column(Text)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # --- CHANGE THIS LINE ---
    # location = Column(Text) # <--- REMOVE THIS
    # --- ADD THIS LINE INSTEAD ---
    location_id = Column(
        UUID(as_uuid=True),
        ForeignKey("locations.location_id", ondelete="SET NULL"), # Link to the canonical Location entity
        nullable=True # Set to True if a conference can exist without a linked location, or be explicit.
    )

    venue_details = Column(Text)
    logo_url = Column(Text)
    website_url = Column(Text)
    organizer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )
    
      # --- ADD THIS RELATIONSHIP ---
    # This links the Conference ORM object to its Location ORM object
    location_rel = relationship("Location", backref="conferences") 

    # --- ADD THIS PROPERTY ---
    # This property will be accessed by Pydantic's .from_orm()
    @property
    def location_name(self):
        # Access the name from the linked Location object
        # It relies on the 'location_rel' relationship being loaded
        return self.location_rel.name if self.location_rel else None

# ... (rest of your models remain unchanged) ...
class Location(Base): # <--- This is where the embedding column needs to be added
    __tablename__ = "locations"

    location_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(Text, nullable=False, unique=True) # Changed to unique=True as discussed. Text is fine.
    address = Column(Text)
    # ADD EMBEDDING COLUMN HERE
    embedding = Column(Vector(384), nullable=True) # ADDED THIS COLUMN, assuming nullable=True

    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class UserLocation(Base): # <--- NEW TABLE ADDED
    __tablename__ = "user_location"
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    location_id = Column(
        UUID(as_uuid=True),
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        primary_key=True
    )
    assigned_at = Column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=func.now()
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class Event(Base):
    __tablename__ = "events"

    event_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )
    conference_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conferences.conference_id", ondelete="CASCADE") # Added ondelete
    )
    title = Column(Text, nullable=False)
    description = Column(Text)

    event_type = Column(
        Enum(EventType, name="event_type"), # Name matches ENUM name
        nullable=False
    )
    venue_details = Column(Text)
    presenter_reg_ids = Column(ARRAY(String))
    exhibitor_reg_ids = Column(ARRAY(String))
    speaker_reg_ids=Column(ARRAY(String))
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    organizer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL") # Added ondelete
    )
class EventTopic(Base):
    __tablename__ = "event_topics" # Matches your SQL table name

    # Columns corresponding to the junction table
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.event_id", ondelete="CASCADE"), # Links to events table's primary key
        primary_key=True,
        nullable=False
    )
    topic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills_interests.skill_interest_id", ondelete="CASCADE"), # Links to skills_interests table's primary key
        primary_key=True,
        nullable=False
    )

    # Relationships to the parent models
    # 'Event' here refers to your PgEvent model, and 'SkillInterest' to your skills_interests model
    # These 'relationship' declarations on the junction table itself are less common if
    # you're primarily defining the M2M on the parent models, but included for completeness.
   

class EventAttendance(Base):
    __tablename__ = "event_attendance"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        primary_key=True
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.event_id", ondelete="CASCADE"), # Added ondelete
        primary_key=True
    )

    attendance_status = Column(
        Enum(AttendanceStatus, name="attendancestatus_enum"), # Name matches ENUM name
        nullable=False
    )

    attended_at = Column(DateTime(timezone=True), nullable=True)
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    valid_to = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="infinity"
    )


class Connection(Base):
    __tablename__ = "connections"

    connection_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    requester_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        nullable=False
    )
    requestee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        nullable=False
    )

    status = Column(
        Enum(ConnectionStatus, name="connectionstatus_enum"), # Name matches ENUM name
        nullable=False,
        default=ConnectionStatus.pending
    )

    requested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        nullable=False
    )
    receiver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        nullable=False
    )
    content = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    direction = Column(
        Enum(MessageDirection, name="messagedirection_enum"), # Name matches ENUM name
        nullable=False
    )


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        nullable=False
    )

    notification_type = Column(
        Enum(NotificationType, name="notificationtype_enum"), # Name matches ENUM name
        nullable=False
    )

    content = Column(Text, nullable=False)
    is_read = Column(
        Boolean,
        nullable=False,
        default=False
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


class Content(Base):
    __tablename__ = "content"

    content_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)

    content_type = Column(
        Enum(ContentType, name="contenttype_enum"), # Name matches ENUM name
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True)


class UserContentInteraction(Base):
    __tablename__ = "user_content_interactions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"), # Added ondelete
        primary_key=True
    )
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("content.content_id", ondelete="CASCADE"), # Added ondelete
        primary_key=True
    )
    liked = Column(
        Boolean,
        nullable=False,
        default=False
    )
    viewed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
