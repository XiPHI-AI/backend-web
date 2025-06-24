from typing import Dict, Any, Optional
from app.db.neo4j import Neo4jConnection
from data_processing.transcript.processor import TranscriptProcessor
from app.models.person import PersonUpdate
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class TranscriptService:
    def __init__(self, db: Neo4jConnection, google_api_key: Optional[str] = None):
        self.db = db
        self.processor = TranscriptProcessor(google_api_key=google_api_key)

    def process_transcript(self, transcript: str) -> Dict[str, Any]:
        """Process a transcript and extract structured information."""
        if not transcript or not transcript.strip():
            logger.warning("Empty transcript received for processing.")
            return {}

        extracted_data = self.processor.process_transcript(transcript)

        # Extract fields
        skills = extracted_data.get("skills", [])
        interests = extracted_data.get("interests", [])
        job_roles = extracted_data.get("job_roles", [])
        company = extracted_data.get("company")
        location = extracted_data.get("location")
        education = extracted_data.get("education", [])

        # Optional additional enrichment
        career_goals = extracted_data.get("careerGoals") or ["goal1", "goal2"]
        topics = extracted_data.get("topics") or ["topic1", "topic2"]

        enriched_data = {
            **extracted_data,
            "skills": skills,  # Use skills as-is
            "interests": interests,
            "job_roles": job_roles,
            "careerGoals": career_goals,
            "topics": topics,
            "voiceAgentInteractions": [
                {
                    "interactionID": str(uuid.uuid4()),
                    "summary": "Sample interaction summary",
                    "extractedTopics": topics,
                    "noAttempts": 1
                }
            ],
            "networkingConnections": [
                {
                    "userID": str(uuid.uuid4()),
                    "matchScore": 0.8,
                    "topicsOfInterest": topics,
                    "lastInteraction": datetime.utcnow().isoformat()
                }
            ],
            "growthMilestones": {
                "rolesAchieved": ["role1", "role2"],
                "skillsAcquired": skills[:2] if skills else ["skill1", "skill2"],
                "certificationsCompleted": ["cert1", "cert2"]
            },
            "education": education if education else [
                {
                    "institution": "IIT Bombay",
                    "degree": "B.Tech in Civil Engineering",
                    "start_year": 2021,
                    "end_year": 2025
                }
            ]
        }

        return enriched_data

    async def update_person_from_transcript(
        self,
        person_id: str,
        transcript_data: Dict[str, Any]
    ) -> Optional[str]:
        """Update a person's information in the graph based on transcript data."""
        try:
            update_data = PersonUpdate(
                skills=transcript_data.get("skills") or [],
                expertise=transcript_data.get("expertise") or [],
                interests=transcript_data.get("interests") or [],
                company=transcript_data.get("company"),
                location=transcript_data.get("location")
            )
            job_roles = transcript_data.get("job_roles") or []

            logger.info(f"Updating person {person_id} with data:")
            logger.info(f"Skills: {update_data.skills}")
            logger.info(f"Expertise: {update_data.expertise}")
            logger.info(f"Interests: {update_data.interests}")
            logger.info(f"Company: {update_data.company}")
            logger.info(f"Location: {update_data.location}")
            logger.info(f"Job Roles: {job_roles}")

            query = """
            MATCH (p:Person {id: $person_id})
            SET p += $properties
            WITH p
            // Update Skills
            OPTIONAL MATCH (p)-[r:HAS_SKILL]->(s:Skill)
            WHERE NOT s.name IN $skills
            DELETE r
            WITH p
            UNWIND $skills AS skill
            MERGE (s:Skill {name: skill})
            MERGE (p)-[:HAS_SKILL]->(s)
            WITH p
            // Update Interests
            OPTIONAL MATCH (p)-[r:INTERESTED_IN]->(i:Interest)
            WHERE NOT i.name IN $interests
            DELETE r
            WITH p
            UNWIND $interests AS interest
            MERGE (i:Interest {name: interest})
            MERGE (p)-[:INTERESTED_IN]->(i)
            WITH p
            // Update Job Roles
            OPTIONAL MATCH (p)-[r:HAS_JOB_ROLE]->(jr:JobRole)
            WHERE NOT jr.name IN $job_roles
            DELETE r
            WITH p
            UNWIND $job_roles AS job_role
            MERGE (jr:JobRole {name: job_role})
            MERGE (p)-[:HAS_JOB_ROLE]->(jr)
            WITH p
            // Update Company
            OPTIONAL MATCH (p)-[r:WORKS_AT]->(c:Company)
            WHERE c.name <> $company OR $company IS NULL
            DELETE r
            WITH p
            CALL apoc.do.when(
                $company IS NOT NULL,
                'MERGE (c:Company {name: $company}) MERGE (p)-[:WORKS_AT]->(c) RETURN p',
                'RETURN p',
                {p: p, company: $company}
            ) YIELD value
            RETURN value.p.id AS person_id
            """

            with self.db.get_session() as session:
                result = session.run(
                    query,
                    {
                        "person_id": person_id,
                        "properties": {
                            "company": update_data.company,
                            "location": update_data.location
                        },
                        "skills": update_data.skills,
                        "interests": update_data.interests,
                        "job_roles": job_roles,
                        "company": update_data.company
                    }
                )

                record = result.single()
                if record and "person_id" in record:
                    return record["person_id"]
                else:
                    logger.warning(f"No record returned while updating person {person_id}")
                    return None

        except Exception as e:
            logger.error(f"Error updating person from transcript: {str(e)}", exc_info=True)
            raise