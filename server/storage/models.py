import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Timeline(Base):
    __tablename__ = 'timelines'
    
    id = Column(String, primary_key=True)
    initialization_ref = Column(String, nullable=False)
    n_accepted = Column(BigInteger, default=0, nullable=False)
    t_trained = Column(BigInteger, default=0, nullable=False)
    e_indexed = Column(BigInteger, default=0, nullable=False)
    active_runtime = Column(String, nullable=False)
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Game(Base):
    __tablename__ = 'games'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timeline_id = Column(String, ForeignKey('timelines.id'), nullable=False)
    visitor_color = Column(String, nullable=False) # 'white' or 'black'
    pinned_age = Column(BigInteger, nullable=False)
    runtime_digest = Column(String, nullable=False)
    seed = Column(BigInteger, nullable=False)
    session_token = Column(String, nullable=False)
    state = Column(String, nullable=False, default="active") # active, completed, aborted
    result = Column(Float, nullable=True) # 1.0, 0.0, -1.0
    termination = Column(String, nullable=True) # mate, draw_claim, resign, abort
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    public_share_id = Column(String, unique=True, nullable=True)
    
    moves = relationship("Move", back_populates="game", order_by="Move.ply")
    experience_event = relationship("ExperienceEvent", back_populates="game", uselist=False)

class Move(Base):
    __tablename__ = 'moves'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey('games.id'), nullable=False)
    ply = Column(Integer, nullable=False)
    uci = Column(String, nullable=False)
    san = Column(String, nullable=False)
    state_hash = Column(String, nullable=False)
    prefix_key = Column(String, nullable=False)
    actor = Column(String, nullable=False) # 'visitor' or 'bot'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    game = relationship("Game", back_populates="moves")

class ExperienceEvent(Base):
    __tablename__ = 'experience_events'
    
    timeline_id = Column(String, ForeignKey('timelines.id'), nullable=False)
    sequence = Column(BigInteger, primary_key=True) # Explicit ID/PK
    game_id = Column(String, ForeignKey('games.id'), unique=True, nullable=False)
    trajectory_digest = Column(String, nullable=False)
    acceptance_time = Column(DateTime, default=datetime.utcnow)
    
    game = relationship("Game", back_populates="experience_event")

class TrainingStep(Base):
    __tablename__ = 'training_steps'
    
    timeline_id = Column(String, ForeignKey('timelines.id'), primary_key=True)
    sequence = Column(BigInteger, primary_key=True)
    parent_digest = Column(String, nullable=False)
    output_digest = Column(String, nullable=False)
    configuration = Column(JSON, nullable=False)
    replay_manifest = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)
    publication_status = Column(String, nullable=False) # pending, published
    created_at = Column(DateTime, default=datetime.utcnow)

class Checkpoint(Base):
    __tablename__ = 'checkpoints'
    
    timeline_id = Column(String, ForeignKey('timelines.id'), primary_key=True)
    age = Column(BigInteger, primary_key=True)
    file_manifest = Column(JSON, nullable=False)
    logical_digest = Column(String, nullable=False)
    artifact_checksums = Column(JSON, nullable=False)
    runtime_reference = Column(String, nullable=False)
    retention_role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kind = Column(String, nullable=False) # 'bot_move', 'snapshot_restoration', 'training'
    deduplication_key = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default="pending") # pending, leased, completed, failed
    lease_expires_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    payload = Column(JSON, nullable=False)
    failure_details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
