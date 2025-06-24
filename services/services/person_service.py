from typing import Dict, Any, List, Optional
from app.db.neo4j import Neo4jConnection
from app.models.person import PersonCreate, PersonUpdate

class PeopleService:
    def __init__(self, db: Neo4jConnection):
        self.db = db

    async def create_person(self, person_data: Dict[str, Any]) -> str:
        query = """
        CREATE (p:Person {id: randomUUID(), name: $name, email: $email, company: $company, location: $location})
        RETURN p.id AS person_id
        """
        with self.db.get_session() as session:
            result = session.run(query, person_data)
            return result.single()["person_id"]

    async def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (p:Person {id: $person_id})
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        OPTIONAL MATCH (p)-[:HAS_EXPERTISE]->(e:Expertise)
        OPTIONAL MATCH (p)-[:INTERESTED_IN]->(i:Interest)
        RETURN p, collect(DISTINCT s.name) as skills,
               collect(DISTINCT e.name) as expertise,
               collect(DISTINCT i.name) as interests
        """
        with self.db.get_session() as session:
            result = session.run(query, {"person_id": person_id}).single()
            if not result:
                return None

            person_node = result["p"]
            return {
                "id": person_node["id"],
                "name": person_node.get("name"),
                "email": person_node.get("email"),
                "company": person_node.get("company"),
                "location": person_node.get("location"),
                "skills": result["skills"],
                "expertise": result["expertise"],
                "interests": result["interests"]
            }

    async def update_person(self, person_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (p:Person {id: $person_id})
        SET p += $properties
        RETURN p
        """
        with self.db.get_session() as session:
            result = session.run(query, {
                "person_id": person_id,
                "properties": {
                    "name": update_data.get("name"),
                    "email": update_data.get("email"),
                    "company": update_data.get("company"),
                    "location": update_data.get("location"),
                }
            })
            if not result.single():
                return None
            return await self.get_person(person_id)

    async def delete_person(self, person_id: str) -> bool:
        query = """
        MATCH (p:Person {id: $person_id})
        DETACH DELETE p
        """
        with self.db.get_session() as session:
            session.run(query, {"person_id": person_id})
        return True

    async def get_recommendations(self, person_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        MATCH (p1:Person {id: $person_id})-[:HAS_SKILL|HAS_EXPERTISE|INTERESTED_IN]->(attr)
        MATCH (p2:Person)-[:HAS_SKILL|HAS_EXPERTISE|INTERESTED_IN]->(attr)
        WHERE p1.id <> p2.id
        WITH p2, COUNT(DISTINCT attr) AS score
        ORDER BY score DESC
        LIMIT $limit
        RETURN p2.id AS id, p2.name AS name, p2.email AS email, score
        """
        with self.db.get_session() as session:
            results = session.run(query, {
                "person_id": person_id,
                "limit": limit
            })
            return [record.data() for record in results]
