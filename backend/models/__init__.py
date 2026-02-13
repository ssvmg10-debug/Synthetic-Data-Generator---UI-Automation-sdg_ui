"""
Database Models for all modules
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base

# ========== SYNTHETIC DATA TABLES ==========

class Schema(Base):
    __tablename__ = "schemas"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)  # 'ui', 'api', 'unified'
    schema_json = Column(JSON, nullable=False)
    version = Column(String, default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    synthetic_runs = relationship("SyntheticRun", back_populates="schema")

class SyntheticRun(Base):
    __tablename__ = "synthetic_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    schema_id = Column(Integer, ForeignKey("schemas.id"))
    rows = Column(Integer, nullable=False)
    model = Column(String, default="GaussianCopula")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    schema = relationship("Schema", back_populates="synthetic_runs")
    data = relationship("SyntheticData", back_populates="run")

class SyntheticData(Base):
    __tablename__ = "synthetic_data"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("synthetic_runs.id"))
    row_json = Column(JSON, nullable=False)
    
    run = relationship("SyntheticRun", back_populates="data")

# ========== UI AUTOMATION TABLES ==========

class UITestCase(Base):
    __tablename__ = "ui_testcases"
    
    id = Column(Integer, primary_key=True, index=True)
    raw_input = Column(Text, nullable=False)
    structured_json = Column(JSON, nullable=False)
    # Store as JSON so we can keep metadata like language alongside the script text.
    # Shape: { "language": "javascript"|"typescript", "content": "<playwright code>" }
    script = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    execution_runs = relationship("UIExecutionRun", back_populates="test_case")

class LocatorRegistry(Base):
    __tablename__ = "locator_registry"
    
    id = Column(Integer, primary_key=True, index=True)
    element = Column(String, nullable=False)
    primary_locator = Column(String, nullable=False)
    healed_locators = Column(JSON)  # Array of healed locators
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UIElement(Base):
    """
    Semantic element registry (Katalon/KaneAI-style).
    One row per (app_key, page_pattern, intent); selectors stored with success/failure stats.
    Generator uses these first; Healer updates them when a new selector works.
    """
    __tablename__ = "ui_elements"
    
    id = Column(Integer, primary_key=True, index=True)
    app_key = Column(String(64), nullable=False, index=True)  # e.g. 'lg', 'hilti' from host
    page_pattern = Column(String(256), nullable=False, index=True)  # host + first path segment
    intent = Column(String(64), nullable=False, index=True)  # search_box, cookie_accept, add_to_cart, etc.
    element_name = Column(String(256), nullable=True)  # human label, optional
    # JSON array of {selector, source, success_count, failure_count, last_success_at (iso)}
    selectors = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UIExecutionRun(Base):
    __tablename__ = "ui_execution_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("ui_testcases.id"))
    status = Column(String, nullable=False)  # 'success', 'failed', 'healed'
    logs_path = Column(String)
    screenshot_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    test_case = relationship("UITestCase", back_populates="execution_runs")

# ========== API AUTOMATION TABLES ==========

class APITestCase(Base):
    __tablename__ = "api_testcases"
    
    id = Column(Integer, primary_key=True, index=True)
    raw_input = Column(Text, nullable=False)
    structured_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    execution_runs = relationship("APIExecutionRun", back_populates="test_case")

class APISchemaCache(Base):
    __tablename__ = "api_schema_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, nullable=False)
    schema_json = Column(JSON, nullable=False)
    version = Column(String, default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)

class APIExecutionRun(Base):
    __tablename__ = "api_execution_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("api_testcases.id"))
    endpoint = Column(String, nullable=False)
    payload_json = Column(JSON)
    response_json = Column(JSON)
    status = Column(String, nullable=False)  # 'success', 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    test_case = relationship("APITestCase", back_populates="execution_runs")


# ========== LANGGRAPH AGENT TABLES ==========

class AgentCheckpoint(Base):
    """Store LangGraph state checkpoints for resumability"""
    __tablename__ = "agent_checkpoints"
    
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, nullable=False, index=True)
    checkpoint_id = Column(String, nullable=False, index=True)
    state_json = Column(JSON, nullable=False)
    checkpoint_metadata = Column(JSON)  # Changed from 'metadata'
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowExecution(Base):
    """Track workflow execution status"""
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, nullable=False, unique=True, index=True)
    workflow_type = Column(String, nullable=False)  # 'synthetic_data', 'ui_automation'
    status = Column(String, nullable=False)  # 'running', 'completed', 'failed', 'paused'
    current_node = Column(String)  # Current graph node
    input_data = Column(JSON)
    output_data = Column(JSON)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class HealingHistory(Base):
    """Track self-healing attempts and success rates"""
    __tablename__ = "healing_history"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("ui_execution_runs.id"))
    failed_locator = Column(String, nullable=False)
    healed_locator = Column(String)
    strategy_used = Column(String)  # 'css', 'xpath', 'text', 'aria', 'hybrid'
    success = Column(Integer, nullable=False)  # 1 = success, 0 = failed
    confidence_score = Column(Integer)  # 0-100
    page_snapshot = Column(Text)  # HTML snapshot at failure
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class CrawlCache(Base):
    """Cache UI crawling results"""
    __tablename__ = "crawl_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, unique=True, index=True)
    schema_json = Column(JSON, nullable=False)
    html_snapshot = Column(Text)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Cache expiration


class CrawlSnapshot(Base):
    """Per-step snapshot from test-case-driven crawl (Phase 3). Keyed by flow_signature + step_index."""
    __tablename__ = "crawl_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_signature = Column(String, nullable=False, index=True)  # e.g. "lg_lg_01", "hilti_hilti_02"
    step_index = Column(Integer, nullable=False)
    url = Column(String, nullable=False)
    page_title = Column(String, nullable=True)
    elements_json = Column(JSON, nullable=True)  # list of { tag, text, selector? }
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentMemory(Base):
    """Store long-term agent memory"""
    __tablename__ = "agent_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String, nullable=False, index=True)  # 'synthetic_data', 'ui_automation'
    memory_key = Column(String, nullable=False, index=True)
    memory_value = Column(JSON, nullable=False)
    embedding = Column(Text)  # Vector embedding for similarity search
    relevance_score = Column(Integer)  # Usage/relevance tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== CHAT / SESSION TABLES (memory, state, UI history) ==========

class ChatSession(Base):
    """One conversation (like a ChatGPT thread). Keyed by agent_type."""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String, nullable=False, index=True)  # 'synthetic', 'ui-automation'
    title = Column(String(512), nullable=True)  # Optional; can be derived from first user message
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """A single message in a chat session (user or agent)."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    sender = Column(String(20), nullable=False)  # 'user', 'agent'
    text = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # SyntheticPayload or UiAutomationPayload
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chat_session = relationship("ChatSession", back_populates="messages")
