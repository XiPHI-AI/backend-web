from neo4j import AsyncGraphDatabase
from app.core.config import settings

NEO4J_URI = f"{settings.NEO4J_URI}"
NEO4J_USER = f"{settings.NEO4J_USER}"
NEO4J_PASSWORD = f"{settings.NEO4J_PASSWORD}"

driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

async def create_user_node(user_id: str, email: str, first_name: str, last_name: str):
    async with driver.session() as session:
        query = """
        CREATE (u:User {user_id: $user_id, email: $email, first_name: $first_name, last_name: $last_name})
        RETURN u
        """
        result = await session.run(query, user_id=user_id, email=email, first_name=first_name, last_name=last_name)
        record = await result.single()
        return record

async def create_or_update_user_skill_neo4j(user_id: str, skill_name: str):
    async with driver.session() as session:
        print(f"{user_id}")
        # user_id: a755b46b-a552-4ea3-83ca-d7999cde362a
        query = """
        MATCH (u:User {user_id: $user_id})
        MERGE (s:Skill {name: $skill_name})
        MERGE (u)-[r:HAS_SKILL]->(s)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, s, r
        """
        result = await session.run(query, user_id=user_id, skill_name=skill_name)
        record = await result.single()
        return record
