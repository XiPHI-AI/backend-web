from fastapi import APIRouter
from app.api.v1.endpoints import people

api_router = APIRouter()

api_router.include_router(
    people.router,
    prefix="/people",
    tags=["people"]
)

# api_router.include_router(
#     transcripts.router,
#     prefix="/transcripts",
#     tags=["transcripts"]
# ) 