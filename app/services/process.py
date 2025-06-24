import numpy as np
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer
from postgres.models import SkillInterest  # SQLAlchemy model

model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embedding(skill_text: str) -> list[float]:
    embedding = model.encode(skill_text, normalize_embeddings=True)
    return embedding.tolist()


async def find_closest_skill_id(db: AsyncSession, skill_text: str) -> Optional[str]:
    # Step 1: Embed input skill name
    embedding = generate_embedding(skill_text)

# Step 2: Vector search - top 5 by L2 similarity
    vector_query = (
        select(
            SkillInterest.skill_interest_id,
            SkillInterest.name
        )
        .order_by(SkillInterest.embedding.l2_distance(embedding))
        .limit(5)
    )
    result = await db.execute(vector_query)
    top_skills = result.fetchall()

    print("Hello")
    print(top_skills)
    # Step 3: Full-text search over top 5 skill names
    top_skill_ids = [str(row.skill_interest_id) for row in top_skills]
    id_placeholders = ','.join(f"'{id}'" for id in top_skill_ids)

    fulltext_query = text(f"""
        SELECT skill_interest_id, name FROM skills_interests
        WHERE skill_interest_id IN ({id_placeholders})
        AND to_tsvector('english', name) @@ plainto_tsquery(:skill_text)
        ORDER BY ts_rank(to_tsvector('english', name), plainto_tsquery(:skill_text)) DESC
        LIMIT 1
    """)
    result = await db.execute(fulltext_query, {"skill_text": skill_text})
    match = result.fetchone()
    # print("npppp")
    # print(len(str(match[0])))
    if match:
        print("hello")

        return {
            "skill_interest_id": str(match[0]),
            "name": match[1]
        }

    # Fallback: return top from vector search
    top_match = top_skills[0]
    # print("hello")
    # print(len(top_match.skill_interest_id))
    return {
        "skill_interest_id": str(top_match.skill_interest_id),
        "name": top_match.name
    }

