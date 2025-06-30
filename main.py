# app/main.py

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router # Your main API router for v1

# Import Neo4j/GDS functions for startup/shutdown
from app.db.neo4j import (
    get_neo4j_async_driver,
    close_neo4j_driver,
    initialize_gds,
    refresh_gds_graphs_and_similarities, # This will be called on startup
)

# Removed datetime, timedelta, timezone as they are no longer needed for background task timing
# Removed _total_profile_updates_since_last_comp and _last_similarity_computed_at global variables

app = FastAPI(
    title="X.COM",
    description="A sophisticated recommendation system for professional networking and event platforms",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Configure CORS Middleware ---
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "null",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Main API Router ---
app.include_router(
    api_router,
    prefix="/api/v1"
)

# --- REMOVED: GLOBAL IN-MEMORY STATE FOR GRAPH COMPUTATION TRIGGERS ---
# Removed: _total_profile_updates_since_last_comp, _last_similarity_computed_at

# --- REMOVED: IN-MEMORY STATE MANAGEMENT FUNCTIONS ---
# Removed: async def increment_profile_update_count_in_memory()
# Removed: async def reset_similarity_state_in_memory()

# --- REMOVED: Background Task for Similarity Computation ---
# Removed: async def background_similarity_task()


# --- FastAPI Application Lifecycle Events ---

@app.on_event("startup")
async def startup_event():
    print("Application startup initiated...")
    try:
        # 1. Initialize PostgreSQL tables (if not already done by migrations)
        # Ensure 'engine' and 'Base' are imported from app.db.database
        # from app.db.database import engine, Base # Local import to avoid circular dependency at top
        # async with engine.begin() as conn:
        #     await conn.run_sync(Base.metadata.create_all)
        # print("PostgreSQL tables initialized (or verified).")

        # # 2. Initialize Neo4j Driver and GDS client
        # await get_neo4j_async_driver() # Initialize the async Neo4j driver
        # await initialize_gds() # Initialize GDS client and project graphs

        # 3. Perform initial GDS graph and similarity refresh
        print("Performing initial GDS graph and similarity refresh on startup...")
        #zawait refresh_gds_graphs_and_similarities()
        # Removed: await reset_similarity_state_in_memory() # No longer managed in-memory
        print("Initial GDS refresh completed.")

        # Removed: asyncio.create_task(background_similarity_task()) # Background task removed
        print("Application startup tasks completed successfully.")

    except Exception as e:
        print(f"FAILED DURING STARTUP: {e}")
        raise 

@app.on_event("shutdown")
async def shutdown_event():
    print("Application shutdown initiated...")
    await close_neo4j_driver()
    print("Application shutdown complete.")

# --- Root Endpoint (Example) ---
@app.get("/")
async def root():
    return {
        "message": "Welcome to the X.COM API for Recommendations!",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

# --- Programmatic Uvicorn Execution ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )