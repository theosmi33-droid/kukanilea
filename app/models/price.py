from datetime import datetime
from sqlalchemy import Column, Integer, Text, String, Float, DateTime
from app.models.rule import Base

class Price(Base):
    __tablename__ = 'prices'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_number = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=False)
    unit_price = Column(Float, nullable=False)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "article_number": self.article_number,
            "description": self.description,
            "unit_price": self.unit_price,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
        }

class DocumentHash(Base):
    __tablename__ = 'document_hashes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String, nullable=False)
    sha256_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
