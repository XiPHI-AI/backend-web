from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from postgres.models import User, UserSkill, UserInterest, UserJobRole, UserCompany, SkillInterest, JobRole, Company
from app.models.person import UserCreate, UserRead, UserUpdateSchema
from app.db.database import get_db
from app.db.neo4j import create_user_node, create_or_update_user_skill_neo4j
from app.services.process import find_closest_skill_id
from datetime import datetime
import uuid
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import BaseModel
import logging
from sqlalchemy.sql import func

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

from neo4j import GraphDatabase
from app.core.config import settings

neo4j_driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

# Pydantic schema for login request
class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/", response_model=UserRead)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == user.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        user_id=uuid.uuid4(),
        email=user.email,
        password_hash=user.password_hash,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
        biography=user.biography,
        phone=user.phone,
        registration_category=user.registration_category
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Async fire-and-forget Neo4j node creation
    asyncio.create_task(create_user_node(
        user_id=str(new_user.user_id),
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name
    ))

    return new_user

@router.post("/update")
async def update_user_data(payload: UserUpdateSchema, db: AsyncSession = Depends(get_db)):
    user_id = payload.user_id

    # --- Update Skills ---
    if payload.user_skills:
        for skill in payload.user_skills:
            id = await find_closest_skill_id(db, skill.skill_name)
            stmt = select(UserSkill).filter_by(
                user_id=user_id,
                skill_interest_id=id["skill_interest_id"]
            )

            # Execute the query asynchronously
            result = await db.execute(stmt)

            # Fetch the first matching record
            existing = result.scalars().first()
            if not existing:
                await db.merge(UserSkill(
                    user_id=user_id,
                    skill_interest_id=id["skill_interest_id"],
                    assigned_at=skill.assigned_at or datetime.utcnow(),
                    valid_from=skill.valid_from or datetime.utcnow(),
                    valid_to=skill.valid_to or datetime.max
                ))
            else:
                continue
            asyncio.create_task(create_or_update_user_skill_neo4j(str(user_id), id["name"]))

    # --- Update Interests ---
    if payload.user_interests:
        for interest in payload.user_interests:
            await db.merge(UserInterest(
                user_id=user_id,
                skill_interest_id=interest.skill_interest_id,
                assigned_at=interest.assigned_at or datetime.utcnow(),
                valid_from=interest.valid_from or datetime.utcnow(),
                valid_to=interest.valid_to or datetime.max
            ))

    # --- Update Job Roles ---
    if payload.user_job_roles:
        for role in payload.user_job_roles:
            await db.merge(UserJobRole(
                user_id=user_id,
                job_role_id=role.job_role_id,
                valid_from=role.valid_from or datetime.utcnow(),
                valid_to=role.valid_to or datetime.max
            ))

    # --- Update Company ---
    if payload.user_company:
        company = payload.user_company
        await db.merge(UserCompany(
            user_id=user_id,
            company_id=company.company_id,
            joined_at=company.joined_at or datetime.utcnow(),
            valid_from=company.valid_from or datetime.utcnow(),
            valid_to=company.valid_to or datetime.max
        ))

    await db.commit()
    return {"msg": "User update successful"}

@router.post("/login")
async def login_user(user: UserLogin, db: AsyncSession = Depends(get_db)):
    # Query the user by email
    result = await db.execute(select(User).filter(User.email == user.email))
    db_user = result.scalars().first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Compare the provided password with the stored password_hash
    # Assuming password_hash is plain text for simplicity; adjust if hashed
    if db_user.password_hash != user.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Return user details with a mock token
    return {
        "user_id": str(db_user.user_id),
        "email": db_user.email,
        "first_name": db_user.first_name,
        "last_name": db_user.last_name,
        "registration_category": db_user.registration_category,
        "token": f"mock-token-{db_user.user_id}"  # Mock token; replace with real auth if needed
    }

@router.get("/{user_id}")
async def get_user_data(user_id: str, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch user details
        result = await db.execute(select(User).filter(User.user_id == user_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Current timestamp for validity checks
        current_time = datetime.utcnow()
        logger.info(f"Current time for validity checks: {current_time}")

        # Fetch user interests and join with skill_interests to get names
        try:
            interests_result = await db.execute(
                select(UserInterest, SkillInterest.name)
                .join(SkillInterest, UserInterest.skill_interest_id == SkillInterest.skill_interest_id)
                .filter(
                    UserInterest.user_id == user_id,
                    UserInterest.valid_from <= current_time,
                    (UserInterest.valid_to == None) | (UserInterest.valid_to > current_time),
                    SkillInterest.valid_from <= current_time,
                    (SkillInterest.valid_to == None) | (SkillInterest.valid_to > current_time)
                )
            )
            interests = interests_result.all()
            logger.info(f"Raw interests data for user {user_id}: {interests}")
            interest_names = [interest[1] for interest in interests if interest[1] is not None]
        except SQLAlchemyError as e:
            logger.error(f"Error fetching interests for user {user_id}: {str(e)}")
            interest_names = []

        # Fetch user skills and join with skill_interests to get names
        try:
            skills_result = await db.execute(
                select(UserSkill, SkillInterest.name)
                .join(SkillInterest, UserSkill.skill_interest_id == SkillInterest.skill_interest_id)
                .filter(
                    UserSkill.user_id == user_id,
                    UserSkill.valid_from <= current_time,
                    (UserSkill.valid_to == None) | (UserSkill.valid_to > current_time),
                    SkillInterest.valid_from <= current_time,
                    (SkillInterest.valid_to == None) | (SkillInterest.valid_to > current_time)
                )
            )
            skills = skills_result.all()
            logger.info(f"Raw skills data for user {user_id}: {skills}")
            skill_names = [skill[1] for skill in skills if skill[1] is not None]
        except SQLAlchemyError as e:
            logger.error(f"Error fetching skills for user {user_id}: {str(e)}")
            skill_names = []

        # Fetch user job roles and join with job_roles to get names
        try:
            job_roles_result = await db.execute(
                select(UserJobRole, JobRole.name)
                .join(JobRole, UserJobRole.job_role_id == JobRole.job_role_id)
                .filter(
                    UserJobRole.user_id == user_id,
                    UserJobRole.valid_from <= current_time,
                    (UserJobRole.valid_to == None) | (UserJobRole.valid_to > current_time),
                    JobRole.valid_from <= current_time,
                    (JobRole.valid_to == None) | (JobRole.valid_to > current_time)
                )
            )
            job_roles = job_roles_result.all()
            logger.info(f"Raw job roles data for user {user_id}: {job_roles}")
            job_role_names = [job_role[1] for job_role in job_roles if job_role[1] is not None]
        except SQLAlchemyError as e:
            logger.error(f"Error fetching job roles for user {user_id}: {str(e)}")
            job_role_names = []

        # Fetch user company and join with companies to get name
        try:
            company_result = await db.execute(
                select(UserCompany, Company.name)
                .join(Company, UserCompany.company_id == Company.company_id)
                .filter(
                    UserCompany.user_id == user_id,
                    UserCompany.valid_from <= current_time,
                    (UserCompany.valid_to == None) | (UserCompany.valid_to > current_time),
                    Company.valid_from <= current_time,
                    (Company.valid_to == None) | (Company.valid_to > current_time)
                )
            )
            companies = company_result.all()
            logger.info(f"Raw company data for user {user_id}: {companies}")
            # Since a user might be associated with multiple companies, we'll take the first one for now
            company_name = companies[0][1] if companies and companies[0][1] is not None else None
        except SQLAlchemyError as e:
            logger.error(f"Error fetching company for user {user_id}: {str(e)}")
            company_name = None

        response = {
            "user_id": str(user.user_id),
            "name": f"{user.first_name} {user.last_name}".strip(),
            "email": user.email,
            "interests": interest_names,
            "skills": skill_names,
            "job_roles": job_role_names,
            "company": company_name
        }
        logger.info(f"Response for user {user_id}: {response}")
        return response

    except Exception as e:
        logger.error(f"Unexpected error in get_user_data for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")