

import os
import asyncio
from neo4j import AsyncGraphDatabase, GraphDatabase
from graphdatascience import GraphDataScience

from app.core.config import settings
from typing import List, Dict, Any, Optional # Ensure Optional is imported
from datetime import datetime
from uuid import UUID # Ensure UUID is imported

# --- GLOBAL DRIVER INSTANCES ---
_neo4j_async_driver_instance = None
_neo4j_sync_driver_for_gds_instance = None
gds = None

async def get_neo4j_async_driver():
    """Returns the Neo4j ASYNC driver instance, initializing if not already."""
    global _neo4j_async_driver_instance
    if _neo4j_async_driver_instance is None:
        uri = settings.NEO4J_URI
        username = settings.NEO4J_USER
        password = settings.NEO4J_PASSWORD
        if not uri or not username or not password:
            raise ValueError("Neo4j connection details are not set in app.core.config.")
        _neo4j_async_driver_instance = AsyncGraphDatabase.driver(uri, auth=(username, password))
        await _neo4j_async_driver_instance.verify_connectivity()
        print("Neo4j async driver initialized successfully!")
    return _neo4j_async_driver_instance

async def close_neo4j_driver():
    """Closes the Neo4j async driver connection AND the GDS sync driver."""
    global _neo4j_async_driver_instance, _neo4j_sync_driver_for_gds_instance
    if _neo4j_async_driver_instance:
        await _neo4j_async_driver_instance.close()
        _neo4j_async_driver_instance = None
        print("Neo4j async driver closed.")
    if _neo4j_sync_driver_for_gds_instance: # Close the sync driver for GDS as well
        _neo4j_sync_driver_for_gds_instance.close()
        _neo4j_sync_driver_for_gds_instance = None
        print("Neo4j GDS sync driver closed.")

# --- GDS Graph Names (Constants) ---
DEMO_GRAPH_NAME = "user_demographics_graph"
INTEREST_GRAPH_NAME = "user_interest_graph"
SKILL_GRAPH_NAME = "user_skill_graph"

async def initialize_gds():
    """
    Initializes the GDS client.
    This function no longer projects graphs; projection is handled by refresh_gds_graphs_and_similarities.
    """
    global gds, _neo4j_sync_driver_for_gds_instance
    if _neo4j_sync_driver_for_gds_instance is None:
        _neo4j_sync_driver_for_gds_instance = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
        _neo4j_sync_driver_for_gds_instance.verify_connectivity()
        print("Neo4j GDS sync driver initialized successfully!")
    gds = GraphDataScience(_neo4j_sync_driver_for_gds_instance)

    print("Initializing GDS graph projections...")

    # GDS projections: No longer include these properties on User node
    await _try_project_gds_graph(
        DEMO_GRAPH_NAME,
        ['User', 'Company', 'Location', 'University', 'Conference', 'Event'], 
        {
            'WORKS_AT': {'orientation': 'UNDIRECTED'},
            'WORKED_AT': {'orientation': 'UNDIRECTED'},
            'LIVES_IN': {'orientation': 'UNDIRECTED'},
            'STUDIED_AT': {'orientation': 'UNDIRECTED'},
            'REGISTERED_FOR': {'orientation': 'UNDIRECTED'},
            'ATTENDS': {'orientation': 'UNDIRECTED'}, 
            'HAS_EVENT': {'orientation': 'UNDIRECTED'},
            'ORGANIZES': {'orientation': 'UNDIRECTED'},
            'EXHIBITS_AT': {'orientation': 'UNDIRECTED'}, 
            'PRESENTS_AT': {'orientation': 'UNDIRECTED'} 
        }
    )
    await _try_project_gds_graph(
        INTEREST_GRAPH_NAME,
        ['User', 'Interest'],
        {
            'HAS_INTEREST': {'orientation': 'UNDIRECTED'},
            'DESIRES_INDUSTRY': {'orientation': 'UNDIRECTED'}
        }
    )
    await _try_project_gds_graph(
        SKILL_GRAPH_NAME,
        ['User', 'Skill'],
        {
            'HAS_SKILL': {'orientation': 'UNDIRECTED'}
        }
    )
    print("All GDS graphs projected successfully.")

async def _try_project_gds_graph(graph_name, node_labels, relationship_types):
    try:
        print(f"Dropping existing GDS graph '{graph_name}'...")
        try:
            await asyncio.to_thread(gds.graph.drop, graph_name)
        except Exception as e:
            if "does not exist" in str(e).lower() or "no graph exists" in str(e).lower():
                print(f"Graph '{graph_name}' did not exist, so no need to drop. Proceeding.")
            else:
                print(f"Error during GDS graph drop for '{graph_name}': {e}")
                raise
        print(f"Projecting GDS graph '{graph_name}'...")
        await asyncio.to_thread(gds.graph.project, graph_name, node_labels, relationship_types)
        print(f"GDS graph '{graph_name}' projected successfully.")
    except Exception as e:
        print(f"Error during GDS graph projection for '{graph_name}': {e}")
        raise

async def refresh_gds_graphs_and_similarities():
    """
    Orchestrates the dropping, re-projecting, and re-computing of all GDS graphs and similarities.
    This function is intended to be called by the background task based on defined criteria.
    """
    global gds

    if gds is None:
        print("GDS client not initialized within refresh_gds_graphs_and_similarities. Attempting initialization.")
        await initialize_gds()
        if gds is None: # Defensive check if initialization still failed
            print("GDS client could not be initialized. Aborting GDS refresh.")
            return

    print("Starting full GDS graph and similarity refresh process...")

    # Project all necessary graphs
    print("Projecting GDS graphs...")
    await _try_project_gds_graph(
        DEMO_GRAPH_NAME,
        ['User', 'Company', 'Location', 'University', 'Conference', 'Event'], # Added Conference, Event (component)
        {
            'WORKS_AT': {'orientation': 'UNDIRECTED'},
            'WORKED_AT': {'orientation': 'UNDIRECTED'},
            'LIVES_IN': {'orientation': 'UNDIRECTED'},
            'STUDIED_AT': {'orientation': 'UNDIRECTED'},
            'REGISTERED_FOR': {'orientation': 'UNDIRECTED'}, # User registered for Conference
            'ATTENDS': {'orientation': 'UNDIRECTED'}, # User attends Event (component)
            'HAS_EVENT': {'orientation': 'UNDIRECTED'}, # Conference has Event (component)
            'ORGANIZES': {'orientation': 'UNDIRECTED'}, # Organizer User to Conference
            'EXHIBITS_AT': {'orientation': 'UNDIRECTED'}, # Exhibitor User to Event (component, like exhibition)
            'PRESENTS_AT': {'orientation': 'UNDIRECTED'} # Presenter User to Event (component)
        }
    )

    await _try_project_gds_graph(
        INTEREST_GRAPH_NAME,
        ['User', 'Interest'],
        {
            'HAS_INTEREST': {'orientation': 'UNDIRECTED'},
            'DESIRES_INDUSTRY': {'orientation': 'UNDIRECTED'}
        }
    )

    await _try_project_gds_graph(
        SKILL_GRAPH_NAME,
        ['User', 'Skill'],
        {
            'HAS_SKILL': {'orientation': 'UNDIRECTED'}
        }
    )
    print("All GDS graphs projected successfully.")

    # Compute all similarities
    print("Computing all GDS similarities...")

    try:
        demo_graph = await asyncio.to_thread(gds.graph.get, DEMO_GRAPH_NAME)
        interest_graph = await asyncio.to_thread(gds.graph.get, INTEREST_GRAPH_NAME)
        skill_graph = await asyncio.to_thread(gds.graph.get, SKILL_GRAPH_NAME)
    except Exception as e:
        print(f"Failed to retrieve projected graphs: {e}")
        raise

    # 1. Compute Demographics Similarity
    try:
        await asyncio.to_thread(gds.nodeSimilarity.write,
            demo_graph,
            writeRelationshipType='SIMILAR_DEMO',
            writeProperty='score',
            topK=50,
            similarityCutoff=0.0
        )
        print("SIMILAR_DEMO calculation complete.")
    except Exception as e:
        print(f"Error computing SIMILAR_DEMO: {e}")

    # 2. Compute Interests Similarity
    try:
        await asyncio.to_thread(gds.nodeSimilarity.write,
            interest_graph,
            writeRelationshipType='SIMILAR_INTEREST',
            writeProperty='score',
            topK=50,
            similarityCutoff=0.0
        )
        print("SIMILAR_INTEREST calculation complete.")
    except Exception as e:
        print(f"Error computing SIMILAR_INTEREST: {e}")

    # 3. Compute Skills Similarity
    try:
        await asyncio.to_thread(gds.nodeSimilarity.write,
            skill_graph,
            writeRelationshipType='SIMILAR_SKILL',
            writeProperty='score',
            topK=50,
            similarityCutoff=0.0
        )
        print("SIMILAR_SKILL calculation complete.")
    except Exception as e:
        print(f"Error computing SIMILAR_SKILL: {e}")

    print("All GDS similarities computed.")

# --- Asynchronous Neo4j CRUD functions ---
# Note: These are now called by API endpoints and use the async driver.

async def create_user_node(user_id: str, email: str, 
                           full_name: str,
                     avatar_url: Optional[str] = None, # Corrected type hint to HttpUrl
                     biography: Optional[str] = None, # Corrected type hint
                     phone: Optional[str] = None, # Corrected type hint
                     registration_category: Optional[str] = None # Corrected type hint
                    ):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        CREATE (u:User {
            userID: $user_id,
            email: $email,
            full_name: $full_name,
            avatar_url: $avatar_url,
            biography: $biography,
            phone: $phone,
            registration_category: $registration_category
        })
        RETURN u
        """
        await session.run(query, user_id=user_id, email=email,
                           full_name = full_name,
                           avatar_url=avatar_url, biography=biography, phone=phone,
                           registration_category=registration_category)
        print(f"Neo4j: Created User node for {full_name} (ID: {user_id})")

async def create_or_update_user_skill_neo4j(user_id: str, skill_name: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        MERGE (s:Skill {name: $skill_name})
        MERGE (u)-[r:HAS_SKILL]->(s)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, s, r
        """
        await session.run(query, user_id=user_id, skill_name=skill_name)
        print(f"Neo4j: User {user_id} HAS_SKILL {skill_name}")

async def create_or_update_user_interest_neo4j(user_id: str, interest_name: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        MERGE (i:Interest {name: $interest_name})
        MERGE (u)-[r:HAS_INTEREST]->(i)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, i, r
        """
        await session.run(query, user_id=user_id, interest_name=interest_name)
        print(f"Neo4j: User {user_id} HAS_INTEREST {interest_name}")

async def create_or_update_user_job_role_neo4j(user_id: str, job_role_title: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        MERGE (j:JobRole {title: $job_role_title})
        MERGE (u)-[r:HAS_CURRENT_ROLE]->(j)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, j, r
        """
        await session.run(query, user_id=user_id, job_role_title=job_role_title)
        print(f"Neo4j: User {user_id} HAS_CURRENT_ROLE {job_role_title}")

async def create_or_update_user_company_neo4j(user_id: str, company_name: str, is_current: bool = True):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        await session.run(
            """
            MATCH (u:User {userID: $user_id})-[r:WORKS_AT {isCurrent: TRUE}]->(c:Company)
            SET r.isCurrent = FALSE
            """,
            user_id=user_id
        )

        query = """
        MATCH (u:User {userID: $user_id})
        MERGE (c:Company {name: $company_name})
        MERGE (u)-[r:WORKS_AT]->(c)
        ON CREATE SET r.assigned_at = datetime(), r.isCurrent = $is_current
        ON MATCH SET r.updated_at = datetime(), r.isCurrent = $is_current
        RETURN u, c, r
        """
        await session.run(query, user_id=user_id, company_name=company_name, is_current=is_current)
        print(f"Neo4j: User {user_id} WORKS_AT {company_name} (isCurrent: {is_current})")

async def update_user_location_neo4j(user_id: str, location_name: str, location_type: str = 'City'):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        await session.run(
            """
            MATCH (u:User {userID: $user_id})-[old_r:LIVES_IN]->(:Location)
            DELETE old_r
            """,
            user_id=user_id
        )

        query = """
        MATCH (u:User {userID: $user_id})
        MERGE (l:Location {name: $location_name, type: $location_type})
        MERGE (u)-[r:LIVES_IN]->(l)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, l, r
        """
        await session.run(query, user_id=user_id, location_name=location_name, location_type=location_type)
        print(f"Neo4j: User {user_id} LIVES_IN {location_name}")

# NEW: Create/update Conference node in Neo4j (maps from conferences table)
async def create_conference_node_neo4j(
    conference_id: str, name: str, description: Optional[str],
    start_date: datetime, end_date: datetime, location_name: Optional[str],
    organizer_id: Optional[str] = None,
    logo_url: Optional[str] = None, # Corrected type hint to HttpUrl
    website_url: Optional[str] = None # Corrected type hint to HttpUrl
):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MERGE (c:Conference {conferenceID: $conference_id})
        ON CREATE SET
            c.name = $name,
            c.description = $description,
            c.start_date = $start_date,
            c.end_date = $end_date,
            c.location = $location_name,
            c.logo_url = $logo_url,
            c.website_url = $website_url
        ON MATCH SET
            c.name = $name,
            c.description = $description,
            c.start_date = $start_date,
            c.end_date = $end_date,
            c.location = $location_name,
            c.logo_url = $logo_url,
            c.website_url = $website_url
        """
        params = {
            "conference_id": conference_id, "name": name, "description": description,
            "start_date": start_date, "end_date": end_date, "location_name": location_name,
            "organizer_id": organizer_id, "logo_url": logo_url, "website_url": website_url
        }
        if organizer_id:
            query += " MERGE (o:User {userID: $organizer_id}) MERGE (o)-[:ORGANIZES]->(c)"
        
        await session.run(query, params)
        print(f"Neo4j: Created/Updated Conference node for {name} (ID: {conference_id})")

# NEW: Create/update Event (component) node in Neo4j and link to Conference
async def create_event_node_neo4j( # Renamed from create_session_node_neo4j
    event_id: str, conference_id: str, title: str, event_type: str,
    start_time: datetime, end_time: datetime, location_name: Optional[str] = None
):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (conf:Conference {conferenceID: $conference_id})
        MERGE (e:Event {eventID: $event_id}) # Changed s:Session to e:Event
        ON CREATE SET
            e.title = $title,
            e.type = $event_type, # Use event_type
            e.start_time = $start_time,
            e.end_time = $end_time,
            e.location = $location_name
        ON MATCH SET
            e.title = $title,
            e.type = $event_type,
            e.start_time = $start_time,
            e.end_time = $end_time,
            e.location = $location_name
        MERGE (conf)-[:HAS_EVENT]->(e) # Changed HAS_SESSION to HAS_EVENT
        RETURN e
        """
        await session.run(query, {
            "event_id": event_id, "conference_id": conference_id, "title": title,
            "event_type": event_type, "start_time": start_time, "end_time": end_time,
            "location_name": location_name
        })
        print(f"Neo4j: Created/Updated Event node {title} (ID: {event_id}) for Conference {conference_id}")

# NEW: Create User-Event (component) attendance relationship
async def create_user_event_attendance_neo4j(user_id: str, event_id: str, attendance_status: str, attended_at: datetime):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        MATCH (e:Event {eventID: $event_id})
        MERGE (u)-[r:ATTENDS {status: $status, attended_at: $attended_at}]->(e)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, r, e
        """
        await session.run(query, user_id=user_id, event_id=event_id, status=attendance_status, attended_at=attended_at)
        print(f"Neo4j: User {user_id} ATTENDS Event {event_id} (Status: {attendance_status})")

# NEW: Create Presenter-Event link
async def create_presenter_event_link_neo4j(presenter_user_id: str, event_id: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $presenter_user_id})
        MATCH (e:Event {eventID: $event_id})
        MERGE (u)-[:PRESENTS_AT]->(e)
        RETURN u,e
        """
        await session.run(query, presenter_user_id=presenter_user_id, event_id=event_id)
        print(f"Neo4j: User {presenter_user_id} assigned as presenter for Event {event_id}")

# NEW: Create Exhibitor-Event link
async def create_exhibitor_event_link_neo4j(exhibitor_user_id: str, event_id: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $exhibitor_user_id})
        MATCH (e:Event {eventID: $event_id})
        WHERE e.type = 'exhibition'
        MERGE (u)-[:EXHIBITS_AT]->(e)
        RETURN u,s
        """
        await session.run(query, exhibitor_user_id=exhibitor_user_id, event_id=event_id)
        print(f"Neo4j: User {exhibitor_user_id} assigned as exhibitor for Event {event_id}")

# NEW: Create User-Conference registration relationship
async def create_user_conference_registration_neo4j(user_id: str, conference_id: str, reg_id: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        MATCH (c:Conference {conferenceID: $conference_id})
        MERGE (u)-[r:REGISTERED_FOR {regId: $reg_id}]->(c)
        ON CREATE SET r.registered_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, r, c
        """
        await session.run(query, user_id=user_id, conference_id=conference_id, reg_id=reg_id)
        print(f"Neo4j: User {user_id} REGISTERED_FOR Conference {conference_id} (Reg ID: {reg_id})")