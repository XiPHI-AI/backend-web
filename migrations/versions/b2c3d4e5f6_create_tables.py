from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text
from pgvector.sqlalchemy import Vector

revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Enable the vector extension for embeddings
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


    

    # 1. job_roles (with embeddings for graph-like similarity)
    op.create_table(
        'job_roles',
        sa.Column('job_role_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('embedding', Vector(384)),  # Embedding for graph-like queries
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 3. companies (with embeddings for graph-like similarity)
    op.create_table(
        'companies',
        sa.Column('company_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('embedding', Vector(384)),  # Embedding for graph-like queries
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 4. skills_interests (unified table for skills and interests with embeddings)
    op.create_table(
        'skills_interests',
        sa.Column('skill_interest_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),  # Embedding for graph-like queries
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 5. users (removed role_id and skill_interest_id, fixed primary key)
    op.create_table(
        'users',
        sa.Column('user_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('first_name', sa.Text, nullable=False),  # Aligned with model
        sa.Column('last_name', sa.Text, nullable=False),   # Aligned with model
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.company_id', ondelete='SET NULL'), nullable=True),
        sa.Column('job_title', sa.Text),
        sa.Column('job_role_id', UUID(as_uuid=True), sa.ForeignKey('job_roles.job_role_id', ondelete='SET NULL'), nullable=True),
        sa.Column('avatar_url', sa.Text),
        sa.Column('biography', sa.Text),
        sa.Column('phone', sa.Text),
        sa.Column('registration_category', sa.Enum('attendee', 'organizer', 'exhibitor', 'presenter', name='registration_category'), nullable=False, server_default='attendee'),
    )

    # 6. user_skills (fixed composite primary key)
    

    # 7. user_interests (fixed composite primary key, points to skills_interests)
    

    # 8. recommendations (added foreign key constraints)
    op.create_table(
        'recommendations',
        sa.Column('recommendation_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column('recommended_user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('context', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 9. event_attendance
    

    # 10. connections
    op.create_table(
        'connections',
        sa.Column('connection_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('requester_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('requestee_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('status', sa.Enum('pending', 'accepted', 'ignored', name='connection_status'), nullable=False, server_default='pending'),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True)
    )

    # 11. tags
    op.create_table(
        'tags',
        sa.Column('tag_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 12. user_tags (fixed composite primary key)
    op.create_table(
        'user_tags',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column('tag_id', UUID(as_uuid=True), sa.ForeignKey("tags.tag_id", ondelete="CASCADE"), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id', 'tag_id', 'valid_from')  # Matches model
    )

    # 13. conferences
    op.create_table(
        'conferences',
        sa.Column('conference_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('location', sa.Text),
        sa.Column('venue_details', sa.Text),
        sa.Column('logo_url', sa.Text),
        sa.Column('website_url', sa.Text),
        sa.Column('organizer_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 14. locations
    op.create_table(
        'locations',
        sa.Column('location_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('address', sa.Text),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'"))
    )

    # 15. events
    op.create_table(
        'events',
        sa.Column('organizer_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
        sa.Column('event_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.Column('conference_id', UUID(as_uuid=True), sa.ForeignKey("conferences.conference_id")),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('event_type', sa.Enum('presentation', 'exhibition', 'workshop', 'panel', 'keynote', name='event_type'), nullable=False),
        sa.Column('location_id', UUID(as_uuid=True), sa.ForeignKey("locations.location_id")),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'event_attendance',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('event_id', UUID(as_uuid=True), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column('attendance_status', sa.Enum('interested', 'going', name='attendance_status'), nullable=False),
        sa.Column('attended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.PrimaryKeyConstraint('user_id', 'event_id')
    )

    # 16. messages
    op.create_table(
        'messages',
        sa.Column('message_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('sender_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('receiver_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('direction', sa.Enum('sent', 'received', name='message_direction'), nullable=False)
    )

    # 17. notifications
    op.create_table(
        'notifications',
        sa.Column('notification_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('notification_type', sa.Enum('event_reminder', 'connection_request', 'interest_match', 'content_suggestion', 'announcement', name='notification_type'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_read', sa.Boolean, nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )

    # 18. content
    op.create_table(
        'content',
        sa.Column('content_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('content_type', sa.Enum('popular', 'library', name='content_type'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        'user_skills',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column('skill_interest_id', UUID(as_uuid=True), sa.ForeignKey('skills_interests.skill_interest_id', ondelete="CASCADE"), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.PrimaryKeyConstraint('user_id', 'skill_interest_id', 'valid_from')  # Matches model
    )
    op.create_table(
        'user_interests',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column('skill_interest_id', UUID(as_uuid=True), sa.ForeignKey('skills_interests.skill_interest_id', ondelete="CASCADE"), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.PrimaryKeyConstraint('user_id', 'skill_interest_id', 'valid_from')  # Matches model
    )
    # 19. user_content_interactions
    op.create_table(
        'user_content_interactions',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column('content_id', UUID(as_uuid=True), sa.ForeignKey("content.content_id"), nullable=False),
        sa.Column('liked', sa.Boolean, nullable=False, default=False),
        sa.Column('viewed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id', 'content_id')
    )
    op.create_table(
        'user_job_role',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column('job_role_id', UUID(as_uuid=True), sa.ForeignKey('job_roles.job_role_id', ondelete="CASCADE"), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=text("'infinity'")),
        sa.PrimaryKeyConstraint('user_id', 'job_role_id', 'valid_from')  # Matches model
    )
    op.create_table(
        'user_company',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_company', UUID(as_uuid=True), sa.ForeignKey('companies.company_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), primary_key=True),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("'infinity'::timestamp with time zone")),
    )

def downgrade():
    # Drop tables in reverse order to respect dependencies
    op.drop_table('user_content_interactions')
    op.drop_table('content')
    op.drop_table('notifications')
    op.drop_table('messages')
    op.drop_table('events')
    op.drop_table('locations')
    op.drop_table('conferences')
    op.drop_table('user_tags')
    op.drop_table('tags')
    op.drop_table('connections')
    op.drop_table('event_attendance')
    op.drop_table('recommendations')
    op.drop_table('user_interests')
    op.drop_table('user_skills')
    op.drop_table('users')
    op.drop_table('skills_interests')
    op.drop_table('companies')
    op.drop_table('job_roles')
    op.drop_table('user_roles')
    op.execute("DROP EXTENSION IF EXISTS vector")