# app/db/neo4j.py

# ... (existing imports and driver setup) ...

# ... (existing GDS Graph Names, initialize_gds, _try_project_gds_graph functions) ...

async def refresh_gds_graphs_and_similarities():
    # ... (existing code for initialization and GDS graph projection calls) ...

    # UPDATED: DEMO_GRAPH_NAME relationships to include SPEAKS_AT if relevant
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
            'EXHIBITS_AT': {'orientation': 'UNDIRECTED'},
            'SPEAKS_AT': {'orientation': 'UNDIRECTED'} # <--- ADDED for GDS
        }
    )

    # ... (existing INTEREST_GRAPH_NAME and SKILL_GRAPH_NAME, EVENT_CONTENT_GRAPH_NAME - ensure SPEAKS_AT is added here too if it contributes to content/skill similarity) ...
    await _try_project_gds_graph(
        EVENT_CONTENT_GRAPH_NAME,
        ['Event', 'Topic', 'User'],
        {
            'COVERS_TOPIC': {'orientation': 'UNDIRECTED'},
            'PRESENTS_AT': {'orientation': 'UNDIRECTED'},
            'SPEAKS_AT': {'orientation': 'UNDIRECTED'}, # <--- ADDED for GDS
            'EXPRESSES_INTEREST_IN': {'orientation': 'UNDIRECTED'},
            'ATTENDS': {'orientation': 'UNDIRECTED'}
        }
    )


    # ... (rest of the existing similarity computation calls) ...

# --- Asynchronous Neo4j CRUD functions ---

# ... (create_user_node, update_user_node_neo4j, create_or_update_user_skill_neo4j,
#      create_or_update_user_interest_neo4j, create_or_update_user_job_role_neo4j,
#      create_or_update_user_company_neo4j, update_user_location_neo4j,
#      create_conference_node_neo4j, create_event_node_neo4j, create_topic_node_neo4j,
#      link_event_to_topic_neo4j, create_exhibitor_event_link_neo4j,
#      create_user_event_interest_neo4j, create_user_event_attendance_neo4j,
#      create_user_conference_registration_neo4j - existing code) ...


# NEW FUNCTION: Create Speaker-Event link (similar to presenter, but distinct relationship)
async def create_speaker_event_link_neo4j(speaker_user_id: str, event_id: str,
                                         expertise_interests: Optional[List[str]] = None,
                                         expertise_interest_id_map: Optional[Dict[str, str]] = None):
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
        if expertise_interests and expertise_interest_id_map:
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