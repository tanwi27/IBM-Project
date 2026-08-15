import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)
    text = Column(Text, nullable=False)
    structural_metadata = Column(JSON, nullable=False) # e.g. {"has_tables": bool, "tables_count": int, "has_images": bool, "images_count": int, "has_columns": bool}
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scores = relationship("Score", back_populates="resume", cascade="all, delete-orphan")

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    level = Column(String(50), nullable=False) # "Entry-level" | "Mid-level" | "Senior-level"
    target_role = Column(String(255), nullable=True)
    jd_text = Column(Text, nullable=True)
    
    # Cache key: sha256(file_hash + level + sha256(jd_text or ""))
    cache_key = Column(String(64), unique=True, index=True, nullable=False)
    
    score_data = Column(JSON, nullable=False) # Comprehensive scores object
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    resume = relationship("Resume", back_populates="scores")

class BulletLibrary(Base):
    __tablename__ = "bullet_library"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(100), index=True, nullable=False) # e.g. "Software Engineering", "Product Management"
    level = Column(String(50), index=True, nullable=False) # "Entry-level" | "Mid-level" | "Senior-level"
    bullet_text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False) # Array of floats

class BulletRewrite(Base):
    __tablename__ = "bullet_rewrites"

    id = Column(Integer, primary_key=True, index=True)
    original_bullet = Column(Text, nullable=False)
    rewritten_bullet = Column(Text, nullable=False)
    changed_because = Column(Text, nullable=False)
    note = Column(Text, nullable=True)
    feedback = Column(String(50), nullable=True) # "approved" | "rejected" | "pending"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
