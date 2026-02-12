"""Add LangGraph agent tables

Revision ID: a1b2c3d4e5f6
Revises: e24d2916597b
Create Date: 2026-02-11 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e24d2916597b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agent_checkpoints table
    op.create_table(
        'agent_checkpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('checkpoint_id', sa.String(), nullable=False),
        sa.Column('state_json', sa.JSON(), nullable=False),
        sa.Column('checkpoint_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_checkpoints_checkpoint_id'), 'agent_checkpoints', ['checkpoint_id'], unique=False)
    op.create_index(op.f('ix_agent_checkpoints_thread_id'), 'agent_checkpoints', ['thread_id'], unique=False)

    # Create workflow_executions table
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('workflow_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('current_node', sa.String(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('thread_id')
    )
    op.create_index(op.f('ix_workflow_executions_thread_id'), 'workflow_executions', ['thread_id'], unique=True)

    # Create healing_history table
    op.create_table(
        'healing_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=True),
        sa.Column('failed_locator', sa.String(), nullable=False),
        sa.Column('healed_locator', sa.String(), nullable=True),
        sa.Column('strategy_used', sa.String(), nullable=True),
        sa.Column('success', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Integer(), nullable=True),
        sa.Column('page_snapshot', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['ui_execution_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create crawl_cache table
    op.create_table(
        'crawl_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('schema_json', sa.JSON(), nullable=False),
        sa.Column('html_snapshot', sa.Text(), nullable=True),
        sa.Column('crawled_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index(op.f('ix_crawl_cache_url'), 'crawl_cache', ['url'], unique=True)

    # Create agent_memory table
    op.create_table(
        'agent_memory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_type', sa.String(), nullable=False),
        sa.Column('memory_key', sa.String(), nullable=False),
        sa.Column('memory_value', sa.JSON(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('relevance_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('accessed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_memory_agent_type'), 'agent_memory', ['agent_type'], unique=False)
    op.create_index(op.f('ix_agent_memory_memory_key'), 'agent_memory', ['memory_key'], unique=False)


def downgrade() -> None:
    # Drop indexes and tables in reverse order
    op.drop_index(op.f('ix_agent_memory_memory_key'), table_name='agent_memory')
    op.drop_index(op.f('ix_agent_memory_agent_type'), table_name='agent_memory')
    op.drop_table('agent_memory')
    
    op.drop_index(op.f('ix_crawl_cache_url'), table_name='crawl_cache')
    op.drop_table('crawl_cache')
    
    op.drop_table('healing_history')
    
    op.drop_index(op.f('ix_workflow_executions_thread_id'), table_name='workflow_executions')
    op.drop_table('workflow_executions')
    
    op.drop_index(op.f('ix_agent_checkpoints_thread_id'), table_name='agent_checkpoints')
    op.drop_index(op.f('ix_agent_checkpoints_checkpoint_id'), table_name='agent_checkpoints')
    op.drop_table('agent_checkpoints')
