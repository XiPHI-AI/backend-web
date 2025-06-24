from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Enum,
    Boolean,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

import uuid
import enum
import datetime
from sqlalchemy import UniqueConstraint

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
    embedding = Column(Vector(384))
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
    embedding = Column(Vector(384))
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
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    avatar_url = Column(Text)
    biography = Column(Text)
    phone = Column(Text)

    # ← Fix: explicitly reference Python enum + give the DB-type a name
    registration_category = Column(
        Enum(
            RegistrationCategory,
            name="registration_category"
        ),
        nullable=False,
        default=RegistrationCategory.attendee
    )

    job_role = relationship("UserJobRole", backref="user")
    company = relationship("UserCompany", backref="user")

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
        ForeignKey("users.user_id"),
        primary_key=True
    )
    tag_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tags.tag_id"),
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
    assigned_at = Column(
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
    __table_args__ = (
        UniqueConstraint("user_id", "skill_interest_id", name="uq_user_skill"),
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
    __table_args__ = (
        UniqueConstraint("user_id", "skill_interest_id", name="uq_user_interest"),
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
    location = Column(Text)
    venue_details = Column(Text)
    logo_url = Column(Text)
    website_url = Column(Text)
    organizer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id")
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


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(Text, nullable=False)
    address = Column(Text)
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
        ForeignKey("conferences.conference_id")
    )
    title = Column(Text, nullable=False)
    description = Column(Text)

    # ← Fix: use Python EventType enum + name
    event_type = Column(
        Enum(EventType, name="eventtype_enum"),
        nullable=False
    )

    location_id = Column(
        UUID(as_uuid=True),
        ForeignKey("locations.location_id")
    )
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    organizer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id")
    )


class EventAttendance(Base):
    __tablename__ = "event_attendance"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        primary_key=True
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.event_id"),
        primary_key=True
    )

    # ← Fix: use Python AttendanceStatus enum + name
    attendance_status = Column(
        Enum(AttendanceStatus, name="attendancestatus_enum"),
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
        ForeignKey("users.user_id"),
        nullable=False
    )
    requestee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )

    # ← Fix: use Python ConnectionStatus enum + name
    status = Column(
        Enum(ConnectionStatus, name="connectionstatus_enum"),
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
        ForeignKey("users.user_id"),
        nullable=False
    )
    receiver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )
    content = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # ← Fix: use Python MessageDirection enum + name
    direction = Column(
        Enum(MessageDirection, name="messagedirection_enum"),
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
        ForeignKey("users.user_id"),
        nullable=False
    )

    # ← Fix: use Python NotificationType enum + name
    notification_type = Column(
        Enum(NotificationType, name="notificationtype_enum"),
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

    # ← Fix: use Python ContentType enum + name
    content_type = Column(
        Enum(ContentType, name="contenttype_enum"),
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
        ForeignKey("users.user_id"),
        primary_key=True
    )
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("content.content_id"),
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
