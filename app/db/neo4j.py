# app/db/neo4j.py

import os
import asyncio
from neo4j import AsyncGraphDatabase, GraphDatabase
from graphdatascience import GraphDataScience

from app.core.config import settings
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID # Ensure UUID is imported for type hints

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
    if _neo4j_sync_driver_for_gds_instance:
        _neo4j_sync_driver_for_gds_instance.close()
        _neo4j_sync_driver_for_gds_instance = None
        print("Neo4j GDS sync driver closed.")


# --- GDS Graph Names (Constants) ---
DEMO_GRAPH_NAME = "user_demographics_graph"
INTEREST_GRAPH_NAME = "user_interest_graph" # For User-Interest connections
SKILL_GRAPH_NAME = "user_skill_graph"
EVENT_CONTENT_GRAPH_NAME = "event_content_graph" # For Event-to-Event and User-to-Event recommendations


async def initialize_gds():
    """
    Initializes the GDS client.
    """
    global gds, _neo4j_sync_driver_for_gds_instance

    if _neo4j_sync_driver_for_gds_instance is None:
        _neo4j_sync_driver_for_gds_instance = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
        _neo4j_sync_driver_for_gds_instance.verify_connectivity()
        print("Neo4j GDS sync driver initialized successfully!")

    gds = GraphDataScience(_neo4j_sync_driver_for_gds_instance)
    print("GDS client initialized.")


async def _try_project_gds_graph(graph_name: str, node_labels: List[str], relationship_types: Dict[str, Dict[str, str]]):
    """Helper to drop and project a GDS graph, wrapping sync GDS calls in to_thread."""
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
    This is designed as a batch refresh for pre-computing similarities, to be run periodically.
    """
    global gds

    if gds is None:
        print("GDS client not initialized within refresh_gds_graphs_and_similarities. Attempting initialization.")
        await initialize_gds()
        if gds is None:
            print("GDS client could not be initialized. Aborting GDS refresh.")
            return

    print("Starting full GDS graph and similarity refresh process...")

    # Project all necessary graphs
    print("Projecting GDS graphs...")

    # DEMO_GRAPH_NAME: User demographics similarity (company, location, etc.)
    await _try_project_gds_graph(
        DEMO_GRAPH_NAME,
        ['User', 'Company', 'Location', 'JobRole', 'Conference', 'Event'],
        {
            'WORKS_AT': {'orientation': 'UNDIRECTED'},
            'LIVES_IN': {'orientation': 'UNDIRECTED'},
            'HAS_CURRENT_ROLE': {'orientation': 'UNDIRECTED'},
            'REGISTERED_FOR': {'orientation': 'UNDIRECTED'},
            'ATTENDS': {'orientation': 'UNDIRECTED'},
            'ORGANIZES': {'orientation': 'UNDIRECTED'},
            'PRESENTS_AT': {'orientation': 'UNDIRECTED'},
            'EXHIBITS_AT': {'orientation': 'UNDIRECTED'}
        }
    )

    # INTEREST_GRAPH_NAME: User similarity based on expressed interests (User-Interest connections)
    await _try_project_gds_graph(
        INTEREST_GRAPH_NAME,
        ['User', 'Interest'], # Node is :Interest for user connections
        {
            'HAS_INTEREST': {'orientation': 'UNDIRECTED'}
        }
    )

    # SKILL_GRAPH_NAME: User similarity based on skills and expertise (User-Skill & User-Topic)
    await _try_project_gds_graph(
        SKILL_GRAPH_NAME,
        ['User', 'Skill', 'Topic'], # Node is :Topic for speaker expertise
        {
            'HAS_SKILL': {'orientation': 'UNDIRECTED'},
            'HAS_EXPERTISE_IN': {'orientation': 'UNDIRECTED'} # Links speakers (Users) to :Topic nodes
        }
    )

    # EVENT_CONTENT_GRAPH_NAME: For Event-to-Event and User-to-Event content-based similarity
    await _try_project_gds_graph(
        EVENT_CONTENT_GRAPH_NAME,
        ['Event', 'Topic', 'User'], # Node is :Topic for event content
        {
            'COVERS_TOPIC': {'orientation': 'UNDIRECTED'}, # Event to :Topic
            'PRESENTS_AT': {'orientation': 'UNDIRECTED'},
            'EXPRESSES_INTEREST_IN': {'orientation': 'UNDIRECTED'}, # User explicit interest in Event
            'ATTENDS': {'orientation': 'UNDIRECTED'}
        }
    )

    print("All GDS graphs projected successfully.")

    # Compute all similarities
    print("Computing all GDS similarities...")

    try:
        demo_graph = await asyncio.to_thread(gds.graph.get, DEMO_GRAPH_NAME)
        interest_graph = await asyncio.to_thread(gds.graph.get, INTEREST_GRAPH_NAME)
        skill_graph = await asyncio.to_thread(gds.graph.get, SKILL_GRAPH_NAME)
        event_content_graph = await asyncio.to_thread(gds.graph.get, EVENT_CONTENT_GRAPH_NAME)
    except Exception as e:
        print(f"Failed to retrieve projected graphs before similarity computation: {e}")
        raise

    async def _compute_similarity(graph: Any, relationship_type: str, property_name: str, top_k: int = 50, similarity_cutoff: float = 0.0):
        try:
            await asyncio.to_thread(gds.nodeSimilarity.write,
                graph,
                writeRelationshipType=relationship_type,
                writeProperty=property_name,
                topK=top_k,
                similarityCutoff=similarity_cutoff
            )
            print(f"{relationship_type} calculation complete.")
        except Exception as e:
            print(f"Error computing {relationship_type}: {e}")
            raise

    try:
        await _compute_similarity(demo_graph, 'SIMILAR_DEMO', 'score')
        await _compute_similarity(interest_graph, 'SIMILAR_INTEREST', 'score')
        await _compute_similarity(skill_graph, 'SIMILAR_SKILL', 'score')
        await _compute_similarity(event_content_graph, 'SIMILAR_EVENT_CONTENT', 'score')
        print("All GDS similarities computed.")
    except Exception as e:
        print(f"An error occurred during similarity computation: {e}")
        raise

    print("Full GDS refresh process completed. Schedule this periodically for freshness.")


# --- Asynchronous Neo4j CRUD functions (UPDATED to use :Interest/:Topic labels based on context) ---

async def create_user_node(user_id: str, full_name: str, email: str,
                     avatar_url: Optional[str] = None,
                     biography: Optional[str] = None,
                     phone: Optional[str] = None,
                     registration_category: Optional[str] = None,
                     reg_id: Optional[str] = None
                    ):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        CREATE (u:User {
            userID: $user_id,
            full_name: $full_name,
            email: $email,
            avatar_url: $avatar_url,
            biography: $biography,
            phone: $phone,
            registration_category: $registration_category,
            regID: $reg_id
        })
        RETURN u
        """
        await session.run(query, user_id=user_id, full_name=full_name, email=email,
                           avatar_url=avatar_url, biography=biography, phone=phone,
                           registration_category=registration_category, reg_id=reg_id)
        print(f"Neo4j: Created User node for {full_name} (ID: {user_id})")

async def update_user_node_neo4j(user_id: str, **properties: Any):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        set_clauses = ", ".join([f"u.{k} = ${k}" for k in properties.keys()])
        if not set_clauses:
            print(f"Neo4j: No properties to update for User {user_id}.")
            return
        query = f"""
        MATCH (u:User {{userID: $user_id}})
        SET {set_clauses}
        RETURN u
        """
        params = {"user_id": user_id, **properties}
        await session.run(query, params)
        print(f"Neo4j: Updated User node {user_id} with properties: {properties.keys()}")


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

# UPDATED: create_or_update_user_interest_neo4j to use :Interest node for user's interest
async def create_or_update_user_interest_neo4j(user_id: str, interest_name: str, interest_id: Optional[str] = None):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        MERGE (i:Interest {name: $interest_name}) // Node label is :Interest
        ON CREATE SET i.interestID = $interest_id // Store original Postgres ID
        ON MATCH SET i.interestID = coalesce(i.interestID, $interest_id) // Only set if not already present
        MERGE (u)-[r:HAS_INTEREST]->(i)
        ON CREATE SET r.assigned_at = datetime()
        ON MATCH SET r.updated_at = datetime()
        RETURN u, i, r
        """
        await session.run(query, user_id=user_id, interest_name=interest_name, interest_id=interest_id)
        print(f"Neo4j: User {user_id} HAS_INTEREST {interest_name} (:Interest node)")


async def create_or_update_user_job_role_neo4j(user_id: str, job_role_title: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (u:User {userID: $user_id})
        OPTIONAL MATCH (u)-[old_r:HAS_CURRENT_ROLE]->(old_j:JobRole)
        SET old_r.isCurrent = FALSE
        MERGE (j:JobRole {title: $job_role_title})
        MERGE (u)-[r:HAS_CURRENT_ROLE]->(j)
        ON CREATE SET r.assigned_at = datetime(), r.isCurrent = TRUE
        ON MATCH SET r.updated_at = datetime(), r.isCurrent = TRUE
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


async def create_conference_node_if_not_exists(conference_id: str):
    driver = await get_neo4j_async_driver()
    query = """
    MERGE (c:Conference {conference_id: $conference_id})
    """
    async with driver.session() as session:
        result = await session.run(query, conference_id=conference_id)
        return result


async def link_user_to_conference(user_id: str, conference_id: str, relationship_type: str):
    category = relationship_type
    if category == "ATTENDS":
        query = """
        MATCH (u:User {userID: $user_id}), (c:Conference {conference_id: $conference_id})
        MERGE (u)-[r:ATTENDS]->(c)
        RETURN type(r) AS rel_type
        """
    elif category == "EXHIBITS":
        query = """
        MATCH (u:User {userID: $user_id}), (c:Conference {conference_id: $conference_id})
        MERGE (u)-[r:EXHIBITS]->(c)
        RETURN type(r) AS rel_type
        """
    elif category == "SPEAKS_AT":
        query = """
        MATCH (u:User {userID: $user_id}), (c:Conference {conference_id: $conference_id})
        MERGE (u)-[r:SPEAKS_AT]->(c)
        RETURN type(r) AS rel_type
        """
    else:
        raise ValueError(f"Unknown registration category: {category}")

    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        result = await session.run(query, {
            "user_id": user_id,
            "conference_id": conference_id
        })
        return result




# UPDATED: create_event_node_neo4j to store organizer identifiers as properties and link to :Topic
async def create_event_node_neo4j(
    event_id: str, conference_id: str, title: str, event_type: str,
    start_time: datetime, end_time: datetime, description: Optional[str] = None,
    venue_details: Optional[str] = None,
    topics: Optional[List[str]] = None, # List of topic names
    topic_id_map: Optional[Dict[str, str]] = None, # Maps topic_name to Postgres interest_id
    organizer_presenter_identifiers: Optional[List[str]] = None, # ADDED
    organizer_exhibitor_identifiers: Optional[List[str]] = None, # ADDED
    organizer_speaker_identifiers: Optional[List[str]] = None # ADDED
):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (conf:Conference {conferenceID: $conference_id})
        MERGE (e:Event {eventID: $event_id})
        ON CREATE SET
            e.title = $title, e.type = $event_type,
            e.start_time = $start_time, e.end_time = $end_time,
            e.venue_details = $venue_details,
            e.description = $description,
            e.organizer_presenter_identifiers = $organizer_presenter_identifiers,
            e.organizer_exhibitor_identifiers = $organizer_exhibitor_identifiers,
            e.organizer_speaker_identifiers = $organizer_speaker_identifiers
        ON MATCH SET
            e.title = $title, e.type = $event_type,
            e.start_time = $start_time, e.end_time = $end_time,
            e.venue_details = $venue_details,
            e.description = $description,
            e.organizer_presenter_identifiers = $organizer_presenter_identifiers,
            e.organizer_exhibitor_identifiers = $organizer_exhibitor_identifiers,
            e.organizer_speaker_identifiers = $organizer_speaker_identifiers
        MERGE (conf)-[:HAS_EVENT]->(e)
        RETURN e
        """
        params = {
            "event_id": event_id, "conference_id": conference_id, "title": title,
            "event_type": event_type, "start_time": start_time, "end_time": end_time,
            "venue_details": venue_details, "description": description,
            "organizer_presenter_identifiers": organizer_presenter_identifiers,
            "organizer_exhibitor_identifiers": organizer_exhibitor_identifiers,
            "organizer_speaker_identifiers": organizer_speaker_identifiers
        }
        await session.run(query, params)

        # Link Event to :Topic nodes
        if topics and topic_id_map:
            for topic_name in topics:
                pg_interest_id = topic_id_map.get(topic_name)
                if pg_interest_id:
                    await session.run(
                        """
                        MATCH (e:Event {eventID: $event_id})
                        MERGE (t:Topic {name: $topic_name})
                        ON CREATE SET t.topicID = $topic_id
                        ON MATCH SET t.topicID = coalesce(t.topicID, $topic_id)
                        MERGE (e)-[:COVERS_TOPIC]->(t)
                        """,
                        event_id=event_id, topic_name=topic_name, topic_id=pg_interest_id
                    )
        print(f"Neo4j: Created/Updated Event node {title} (ID: {event_id}) for Conference {conference_id} and linked topics.")


# NEW FUNCTION: create_topic_node_neo4j (for events/speaker expertise)
async def create_topic_node_neo4j(topic_id: str, name: str, description: Optional[str] = None):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MERGE (t:Topic {name: $name}) // Node label is :Topic
        ON CREATE SET t.topicID = $topic_id, t.description = $description
        ON MATCH SET t.topicID = coalesce(t.topicID, $topic_id), t.description = coalesce(t.description, $description)
        RETURN t
        """
        await session.run(query, topic_id=topic_id, name=name, description=description)
        print(f"Neo4j: Created/Updated :Topic node {name} (ID: {topic_id})")

# NEW FUNCTION: link_event_to_topic_neo4j (just a helper, logic already in create_event_node_neo4j)
async def link_event_to_topic_neo4j(event_id: str, topic_id: str):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        query = """
        MATCH (e:Event {eventID: $event_id})
        MATCH (t:Topic {topicID: $topic_id}) // Match :Topic node
        MERGE (e)-[:COVERS_TOPIC]->(t) // Relationship is COVERS_TOPIC
        RETURN e, t
        """
        await session.run(query, event_id=event_id, topic_id=topic_id)
        print(f"Neo4j: Event {event_id} COVERS_TOPIC {topic_id}")


# UPDATED: create_presenter_event_link_neo4j to link expertise to :Topic
async def create_presenter_event_link_neo4j(presenter_user_id: str, event_id: str,
                                          #expertise_interests: Optional[List[str]] = None, # List of interest names
                                          #expertise_interest_id_map: Optional[Dict[str, str]] = None
                                          ): # Map name to Postgres ID
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        await session.run(
            """
            MERGE (u:User {userID: $presenter_user_id})
            ON CREATE SET u.registration_category = 'presenter'
            ON MATCH SET u.registration_category = 'presenter'
            """,
            presenter_user_id=presenter_user_id
        )
        query = """
        MATCH (u:User {userID: $presenter_user_id})
        MATCH (e:Event {eventID: $event_id})
        MERGE (u)-[:PRESENTS_AT]->(e)
        RETURN u, e
        """
        await session.run(query, presenter_user_id=presenter_user_id, event_id=event_id)
        print(f"Neo4j: User {presenter_user_id} assigned as presenter for Event {event_id}")

        # Link presenter to their expertise :Topic nodes
        '''if expertise_interests and expertise_interest_id_map:
            for interest_name in expertise_interests:
                pg_interest_id = expertise_interest_id_map.get(interest_name)
                if pg_interest_id:
                    await session.run(
                        """
                        MATCH (u:User {userID: $presenter_user_id})
                        MERGE (t:Topic {name: $interest_name}) // Merge as :Topic
                        ON CREATE SET t.topicID = $topic_id
                        ON MATCH SET t.topicID = coalesce(t.topicID, $topic_id)
                        MERGE (u)-[:HAS_EXPERTISE_IN]->(t) // Link HAS_EXPERTISE_IN to :Topic
                        """,
                        presenter_user_id=presenter_user_id, interest_name=interest_name, topic_id=pg_interest_id
                    )
            print(f"Neo4j: Presenter {presenter_user_id} HAS_EXPERTISE_IN topics: {expertise_interests}")
'''
# app/db/neo4j.py

# ... (other existing imports and functions) ...

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

# app/db/neo4j.py

# ... (other existing imports and functions) ...

# NEW: Create Exhibitor-Event link (from previous updates)
async def create_exhibitor_event_link_neo4j(exhibitor_user_id: str, event_id: str,
                                         # company_name: Optional[str] = None
                                          ): # NEW: company name for exhibitor
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        # Ensure User node exists and its role is correct
        await session.run(
            """
            MERGE (u:User {userID: $exhibitor_user_id})
            ON CREATE SET u.registration_category = 'exhibitor'
            ON MATCH SET u.registration_category = 'exhibitor' // Ensure role is 'exhibitor'
            """,
            exhibitor_user_id=exhibitor_user_id
        )

        query = """
        MATCH (u:User {userID: $exhibitor_user_id})
        MATCH (e:Event {eventID: $event_id})
       // WHERE e.type IN ['panel', 'keynote']  Ensure it's an exhibition type event
        MERGE (u)-[:EXHIBITS_AT]->(e)
        RETURN u, e
        """
        await session.run(query, exhibitor_user_id=exhibitor_user_id, event_id=event_id)
        print(f"Neo4j: User {exhibitor_user_id} assigned as exhibitor for Event {event_id}")

        # NEW: Link exhibitor to Company node if provided
        '''if company_name:
            await session.run(
                """
                MATCH (u:User {userID: $exhibitor_user_id})
                MERGE (c:Company {name: $company_name})
                MERGE (u)-[:WORKS_AT {isCurrent: TRUE}]->(c) // Exhibitors 'work at' a company
                """,
                exhibitor_user_id=exhibitor_user_id, company_name=company_name
            )
            print(f"Neo4j: Exhibitor {exhibitor_user_id} WORKS_AT Company {company_name}")'''


async def create_speaker_event_link_neo4j(speaker_user_id: str, event_id: str,
                                         #expertise_interests: Optional[List[str]] = None,
                                         #expertise_interest_id_map: Optional[Dict[str, str]] = None
                                          ):
    driver = await get_neo4j_async_driver()
    async with driver.session() as session:
        # Ensure User node exists and its role is correct (can be 'speaker' category)
        await session.run(
            """
            MERGE (u:User {userID: $speaker_user_id})
            ON CREATE SET u.registration_category = 'speaker'
            ON MATCH SET u.registration_category = 'speaker' // Ensure role is 'speaker'
            """,
            speaker_user_id=speaker_user_id
        )
        query = """
        MATCH (u:User {userID: $speaker_user_id})
        MATCH (e:Event {eventID: $event_id})
        MERGE (u)-[:SPEAKS_AT]->(e) # <--- NEW RELATIONSHIP TYPE
        RETURN u, e
        """
        await session.run(query, speaker_user_id=speaker_user_id, event_id=event_id)
        print(f"Neo4j: User {speaker_user_id} assigned as speaker for Event {event_id}")

        # Link speaker to their expertise :Topic nodes (if provided)
        '''if expertise_interests and expertise_interest_id_map:
            for interest_name in expertise_interests:
                pg_interest_id = expertise_interest_id_map.get(interest_name)
                if pg_interest_id:
                    await session.run(
                        """
                        MATCH (u:User {userID: $speaker_user_id})
                        MERGE (t:Topic {name: $interest_name})
                        ON CREATE SET t.topicID = $topic_id
                        ON MATCH SET t.topicID = coalesce(t.topicID, $topic_id)
                        MERGE (u)-[:HAS_EXPERTISE_IN]->(t)
                        """,
                        speaker_user_id=speaker_user_id, interest_name=interest_name, topic_id=pg_interest_id
                    )
            print(f"Neo4j: Speaker {speaker_user_id} HAS_EXPERTISE_IN topics: {expertise_interests}")
'''
