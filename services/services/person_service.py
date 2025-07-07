# services/services/person_service.py

# Standard imports
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone # Use timezone for consistent UTC now
from uuid import UUID
import uuid
import asyncio 

# SQLAlchemy specific imports
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.future import select 
from fastapi import HTTPException # Used for raising exceptions

# Project-specific models and schemas
from postgres.models import User, UserSkill, UserInterest, UserJobRole, UserCompany
from app.models.person import UserCreate, UserRead, UserUpdateSchema, RegistrationCategory

# Import Neo4j CRUD functions (recommendation functions are NOT imported here anymore)
from app.db.neo4j import (
    create_user_node,
    create_or_update_user_skill_neo4j,
    create_or_update_user_interest_neo4j,
    create_or_update_user_job_role_neo4j,
    create_or_update_user_company_neo4j,
    update_user_location_neo4j,
    get_neo4j_async_driver # Used to get the driver if self.neo4j_driver is None
)

# Import entity normalization functions
from app.services.process import (
    find_or_create_skill_interest,
    find_or_create_company,
    find_or_create_job_role
)


class PeopleService:
    def __init__(self, db: AsyncSession, neo4j_driver_async: Any):
        self.db = db  # PostgreSQL async session
        self.neo4j_driver = neo4j_driver_async # Store the ASYNC driver instance

    # --- User CRUD Methods ---

    async def create_person(self, user_create_payload: UserCreate) -> UserRead: 
        # Postgres check for existing user
        result = await self.db.execute(select(User).filter(User.email == user_create_payload.email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user_uuid = UUID(uuid.uuid4().hex) # Convert to UUID type for Postgres model
        new_user = User(
            user_id=new_user_uuid,
            email=user_create_payload.email,
            password_hash=user_create_payload.password_hash,
            full_name=user_create_payload.full_name,
            avatar_url=user_create_payload.avatar_url,
            biography=user_create_payload.biography,
            phone=user_create_payload.phone,
            registration_category=user_create_payload.registration_category.value # Use .value for Enum
        )

        self.db.add(new_user)
        await self.db.commit() # Commit the new user for its ID to be available
        await self.db.refresh(new_user)

        # Call Neo4j node creation
        await create_user_node(
            user_id=str(new_user.user_id),
            full_name=new_user.full_name,
            email=new_user.email,
            biography=new_user.biography # Pass biography here
        )
        
        return UserRead.from_orm(new_user)


    async def get_person(self, person_id: str) -> Optional[UserRead]:
        result = await self.db.execute(select(User).filter(User.user_id == UUID(person_id)))
        user_db = result.scalars().first()
        if not user_db:
            return None
        return UserRead.from_orm(user_db)


    async def update_person(self, user_id: uuid, update_data: UserUpdateSchema) -> Optional[UserRead]:
        result = await self.db.execute(select(User).filter(User.user_id == user_id))
        user_db = result.scalars().first()

        if not user_db:
            return None

        # Update fields from payload for Postgres User model
        for key, value in update_data.dict(exclude_unset=True).items():
            if key in ["user_skills", "user_interests", "user_job_roles", "user_company", "current_location_name"]:
                continue
            if hasattr(user_db, key): 
                setattr(user_db, key, value)
        
        # Prepare common timestamps
        now_utc = datetime.now(timezone.utc)
        infinity_date = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
        user_id_str = str(user_id) # Ensure UUID is string for Neo4j calls

        # Handle skill updates
        if update_data.user_skills:
            for skill_payload in update_data.user_skills:
                skill_info = await find_or_create_skill_interest(self.db, skill_payload.skill_name, entity_type='skill')
                if skill_info:
                    await self.db.merge(UserSkill(
                        user_id=user_id,
                        skill_interest_id=skill_info["skill_interest_id"],
                        assigned_at=skill_payload.assigned_at or now_utc,
                        valid_from=skill_payload.valid_from or now_utc,
                        valid_to=skill_payload.valid_to or infinity_date
                    ))
                    await create_or_update_user_skill_neo4j(user_id_str, skill_info["name"])

        # Handle interest updates
        if update_data.user_interests:
            for interest_payload in update_data.user_interests:
                interest_info = await find_or_create_skill_interest(self.db, interest_payload.interest_name, entity_type='interest')
                if interest_info:
                    await self.db.merge(UserInterest(
                        user_id=user_id,
                        skill_interest_id=interest_info["skill_interest_id"],
                        assigned_at=interest_payload.assigned_at or now_utc,
                        valid_from=interest_payload.valid_from or now_utc,
                        valid_to=interest_payload.valid_to or infinity_date
                    ))
                    await create_or_update_user_interest_neo4j(user_id_str, interest_info["name"])

        # Handle job role updates
        if update_data.user_job_roles:
            for role_payload in update_data.user_job_roles:
                job_role_info = await find_or_create_job_role(self.db, role_payload.job_role_title)
                if job_role_info:
                    await self.db.merge(UserJobRole(
                        user_id=user_id,
                        job_role_id=job_role_info["job_role_id"],
                        assigned_at=role_payload.valid_from or now_utc,
                        valid_from=role_payload.valid_from or now_utc,
                        valid_to=role_payload.valid_to or infinity_date
                    ))
                    await create_or_update_user_job_role_neo4j(user_id_str, job_role_info["title"])

        # Handle company update (single object)
        if update_data.user_company:
            company_payload = update_data.user_company
            company_info = await find_or_create_company(self.db, company_payload.company_name)
            if company_info:
                await self.db.merge(UserCompany(
                    user_id=user_id,
                    company_id=company_info["company_id"],
                    assigned_at=company_payload.assigned_at or now_utc,
                    valid_from=company_payload.valid_from or now_utc,
                    valid_to=company_payload.valid_to or infinity_date,
                ))
                await create_or_update_user_company_neo4j(user_id_str, company_info["name"])

        # Handle location update
        if hasattr(update_data, 'current_location_name') and update_data.current_location_name:
            await update_user_location_neo4j(user_id_str, update_data.current_location_name) # Fix typo if not already: update_user_location_neo4j

        await self.db.commit() # Commit all Postgres changes
        await self.db.refresh(user_db) # Refresh user_db to reflect any changes

        return UserRead.from_orm(user_db)


    async def delete_person(self, person_id: str) -> bool:
        # Delete from Postgres
        result = await self.db.execute(select(User).filter(User.user_id == UUID(person_id)))
        user_db = result.scalars().first()
        if not user_db:
            return False
        await self.db.delete(user_db)
        await self.db.commit()

        # Delete from Neo4j (using the async driver)
        async with self.neo4j_driver.session() as session: # Use self.neo4j_driver
            query = "MATCH (u:User {userID: $user_id}) DETACH DELETE u"
            await session.run(query, user_id=person_id)
        return True


    # --- Recommendation Retrieval Methods (ALL QUERIES EMBEDDED HERE - COMMENTS REMOVED FROM QUERIES) ---

    async def get_demographics_based_recommendations(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recommends people based on strong demographic similarity (company, location, university)
        by executing the Neo4j query directly here.
        """
        results = []
        async with self.neo4j_driver.session() as session:
            query = """
            MATCH (me:User {userID: $user_id})
            OPTIONAL MATCH (me)-[:WORKS_AT]->(myCompany:Company)
            OPTIONAL MATCH (me)-[:LIVES_IN]->(myLocation:Location)
            OPTIONAL MATCH (me)-[:STUDIED_AT]->(myUniversity:University)

            MATCH (other:User)
            WHERE other <> me

            OPTIONAL MATCH (other)-[:HAS_CURRENT_ROLE]->(otherJobRole:JobRole)
            OPTIONAL MATCH (other)-[:WORKS_AT {isCurrent: TRUE}]->(otherCurrentCompany:Company)

            OPTIONAL MATCH (other)-[:LIVES_IN]->(otherMatchLocation:Location)
            OPTIONAL MATCH (other)-[:STUDIED_AT]->(otherMatchUniversity:University)
            
            WITH other, me, myCompany, myLocation, myUniversity, otherJobRole, otherCurrentCompany,
                 otherMatchLocation, otherMatchUniversity 

            WITH other, me,
                 CASE WHEN myCompany IS NOT NULL AND otherCurrentCompany IS NOT NULL AND myCompany = otherCurrentCompany THEN 1 ELSE 0 END AS sameCompanyScore,
                 CASE WHEN myLocation IS NOT NULL AND otherMatchLocation IS NOT NULL AND myLocation = otherMatchLocation THEN 1 ELSE 0 END AS sameLocationScore,
                 CASE WHEN myUniversity IS NOT NULL AND otherMatchUniversity IS NOT NULL AND myUniversity = otherMatchUniversity THEN 1 ELSE 0 END AS sameUniversityScore,
                 
                 CASE WHEN myCompany IS NOT NULL AND otherCurrentCompany IS NOT NULL AND myCompany = otherCurrentCompany THEN [otherCurrentCompany.name] ELSE [] END AS sharedCompanies,
                 CASE WHEN myLocation IS NOT NULL AND otherMatchLocation IS NOT NULL AND myLocation = otherMatchLocation THEN [otherMatchLocation.name] ELSE [] END AS sharedLocations,
                 CASE WHEN myUniversity IS NOT NULL AND otherMatchUniversity IS NOT NULL AND myUniversity = otherMatchUniversity THEN [otherMatchUniversity.name] ELSE [] END AS sharedUniversities,
                 
                 otherJobRole.title AS OtherRole,
                 otherCurrentCompany.name AS OtherCompanyName

            WITH other,
                 (sameCompanyScore * 0.4 + sameLocationScore * 0.4 + sameUniversityScore * 0.2) AS SimilarityScore,
                 sharedCompanies, sharedLocations, sharedUniversities,
                 OtherRole, OtherCompanyName
            WHERE SimilarityScore > 0
            ORDER BY SimilarityScore DESC
            RETURN other.userID AS UserID,
                   other.fullName AS RecommendedUser,
                   other.biography AS Biography,
                   OtherRole AS Role,
                   OtherCompanyName AS Company,
                   SimilarityScore,
                   sharedCompanies, sharedLocations, sharedUniversities
            LIMIT $limit
            """
            result_obj = await session.run(query, user_id=user_id, limit=limit)
            records = await result_obj.data()
            results = [record for record in records]
        return results


    async def get_similar_interests_recommendations(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recommends people based on shared interests by executing the Neo4j query directly here.
        """
        results = []
        async with self.neo4j_driver.session() as session:
            query = """
            MATCH (me:User {userID: $user_id})-[s:SIMILAR_INTEREST]-(other:User)
            WHERE other.userID <> me.userID AND s.score > 0.0

            OPTIONAL MATCH (me)-[:HAS_INTEREST]->(myInterest:Interest)<-[:HAS_INTEREST]-(other)

            OPTIONAL MATCH (other)-[:HAS_CURRENT_ROLE]->(otherJobRole:JobRole)
            OPTIONAL MATCH (other)-[:WORKS_AT {isCurrent: TRUE}]->(otherCurrentCompany:Company)
            
            WITH other, COUNT(DISTINCT myInterest) AS sharedInterestCount, COLLECT(DISTINCT myInterest.name) AS commonInterests,
                 otherJobRole.title AS OtherRole,
                 otherCurrentCompany.name AS OtherCompanyName,
                 s.score AS SimilarityScore 
            WHERE sharedInterestCount > 0
            ORDER BY SimilarityScore DESC
            RETURN other.userID AS UserID, 
                   other.fullName AS RecommendedUser,
                   other.biography AS Biography,
                   OtherRole AS Role,
                   OtherCompanyName AS Company,
                   SimilarityScore,
                   commonInterests AS CommonInterests
            LIMIT $limit
            """
            result_obj = await session.run(query, user_id=user_id, limit=limit)
            records = await result_obj.data()
            results = [record for record in records]
        return results


    async def get_similar_skills_recommendations(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recommends people based on shared skills by executing the Neo4j query directly here.
        """
        results = []
        async with self.neo4j_driver.session() as session:
            query = """
            MATCH (me:User {userID: $user_id})-[s:SIMILAR_SKILL]-(other:User)
            WHERE other.userID <> me.userID AND s.score > 0.0

            OPTIONAL MATCH (me)-[:HAS_SKILL]->(mySkill:Skill)<-[:HAS_SKILL]-(other)

            OPTIONAL MATCH (other)-[:HAS_CURRENT_ROLE]->(otherJobRole:JobRole)
            OPTIONAL MATCH (other)-[:WORKS_AT {isCurrent: TRUE}]->(otherCurrentCompany:Company)
            
            WITH other, COUNT(DISTINCT mySkill) AS sharedSkillCount, COLLECT(DISTINCT mySkill.name) AS commonSkills,
                 otherJobRole.title AS OtherRole,
                 otherCurrentCompany.name AS OtherCompanyName,
                 s.score AS SimilarityScore 
            WHERE sharedSkillCount > 0
            ORDER BY SimilarityScore DESC
            RETURN other.userID AS UserID, 
                   other.fullName AS RecommendedUser,
                   other.biography AS Biography,
                   OtherRole AS Role,
                   OtherCompanyName AS Company,
                   SimilarityScore,
                   commonSkills AS CommonSkills
            LIMIT $limit
            """
            result_obj = await session.run(query, user_id=user_id, limit=limit)
            records = await result_obj.data()
            results = [record for record in records]
        return results