# schemas.py
from pydantic import BaseModel, EmailStr, HttpUrl, conlist
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

class RegistrationCategory(str, Enum):
    attendee = "attendee"
    speaker = "speaker"
    organizer = "organizer"

class UserCreate(BaseModel):
    email: EmailStr
    password_hash: str
    first_name: str
    last_name: str
    avatar_url: Optional[HttpUrl] = None
    biography: Optional[str] = None
    phone: Optional[str] = None
    registration_category: RegistrationCategory = RegistrationCategory.attendee

class UserRead(BaseModel):
    user_id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    registration_category: RegistrationCategory

    class Config:
        orm_mode = True


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
    job_role : str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

class SingleUserCompany(BaseModel):
    company_name: str
    joined_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

class UserUpdateSchema(BaseModel):
    user_id: UUID
    user_skills: Optional[List[SingleUserSkill]] = None
    user_job_roles: Optional[List[SingleUserJobRole]] = None
    user_interests: Optional[List[SingleUserInterest]] = None
    user_company: Optional[SingleUserCompany] = None

    class Config:
        orm_mode = True