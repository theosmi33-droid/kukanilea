from datetime import datetime
from sqlalchemy import Column, Integer, Text, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
import json

Base = declarative_base()

class RuleProposal(Base):
    __tablename__ = 'agent_drafts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_text = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String, default='pending') # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "rule_text": self.rule_text,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

# SQLAlchemy setup helper for the app
def get_sa_engine():
    from app.database import get_db_path
    db_path = get_db_path()
    return create_engine(f"sqlite:///{db_path}")

def init_sa_db():
    engine = get_sa_engine()
    Base.metadata.create_all(engine)

def get_sa_session():
    engine = get_sa_engine()
    Session = sessionmaker(bind=engine)
    return Session()
