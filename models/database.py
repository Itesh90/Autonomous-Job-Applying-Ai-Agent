"""
Database models and encryption utilities
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import hashlib
from enum import Enum

from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, Integer, Float, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.ext.hybrid import hybrid_property
from cryptography.fernet import Fernet

from config.settings import settings

# Create base class for models
Base = declarative_base()

# Encryption manager
class EncryptionManager:
    """Manages encryption/decryption of sensitive data"""
    
    def __init__(self):
        self.cipher_suite = Fernet(settings.encryption_key.encode())
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if not data:
            return data
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        if not encrypted_data:
            return encrypted_data
        try:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return encrypted_data  # Return as-is if decryption fails
    
    def hash_data(self, data: str) -> str:
        """Create SHA-256 hash of data"""
        return hashlib.sha256(data.encode()).hexdigest()

# Global encryption manager
encryption = EncryptionManager()

# Enums
class JobStatus(str, Enum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    SKIPPED = "skipped"

class ApplicationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"

# Models
class Candidate(Base):
    """Candidate profile with encrypted PII"""
    __tablename__ = 'candidates'
    
    id = Column(String, primary_key=True, default=lambda: hashlib.md5(str(datetime.utcnow()).encode()).hexdigest())
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Encrypted PII fields
    _first_name = Column('first_name', Text, nullable=True)
    _last_name = Column('last_name', Text, nullable=True)
    _email = Column('email', Text, nullable=True)
    _phone = Column('phone', Text, nullable=True)
    _address = Column('address', Text, nullable=True)
    
    # Non-encrypted fields
    profile_summary = Column(Text)
    years_experience = Column(Integer, default=0)
    skills = Column(JSON, default=list)
    education = Column(JSON, default=list)
    experiences = Column(JSON, default=list)
    
    # Resume data
    resume_file_path = Column(String)
    resume_text = Column(Text)
    resume_parsed_data = Column(JSON)
    
    # Preferences
    desired_roles = Column(JSON, default=list)
    desired_locations = Column(JSON, default=list)
    min_salary = Column(Integer)
    max_salary = Column(Integer)
    remote_preference = Column(String, default="flexible")
    
    # Relationships
    applications = relationship("Application", back_populates="candidate")
    
    # Encrypted property accessors
    @hybrid_property
    def first_name(self):
        return encryption.decrypt(self._first_name) if self._first_name else None
    
    @first_name.setter
    def first_name(self, value):
        self._first_name = encryption.encrypt(value) if value else None
    
    @hybrid_property
    def last_name(self):
        return encryption.decrypt(self._last_name) if self._last_name else None
    
    @last_name.setter
    def last_name(self, value):
        self._last_name = encryption.encrypt(value) if value else None
    
    @hybrid_property
    def email(self):
        return encryption.decrypt(self._email) if self._email else None
    
    @email.setter
    def email(self, value):
        self._email = encryption.encrypt(value) if value else None
    
    @hybrid_property
    def phone(self):
        return encryption.decrypt(self._phone) if self._phone else None
    
    @phone.setter
    def phone(self, value):
        self._phone = encryption.encrypt(value) if value else None
    
    @hybrid_property
    def address(self):
        return encryption.decrypt(self._address) if self._address else None
    
    @address.setter
    def address(self, value):
        self._address = encryption.encrypt(value) if value else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (with decrypted data)"""
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'profile_summary': self.profile_summary,
            'years_experience': self.years_experience,
            'skills': self.skills,
            'education': self.education,
            'experiences': self.experiences,
            'desired_roles': self.desired_roles,
            'desired_locations': self.desired_locations,
            'salary_range': {'min': self.min_salary, 'max': self.max_salary},
            'remote_preference': self.remote_preference
        }

class Job(Base):
    """Job posting information"""
    __tablename__ = 'jobs'
    
    id = Column(String, primary_key=True, default=lambda: hashlib.md5(str(datetime.utcnow()).encode()).hexdigest())
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Job details
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    remote_type = Column(String)  # remote, hybrid, onsite
    
    # Job description
    description = Column(Text)
    requirements = Column(Text)
    benefits = Column(Text)
    
    # Metadata
    source = Column(String)  # linkedin, indeed, greenhouse, etc.
    platform = Column(String)  # ATS platform detected
    posted_date = Column(DateTime)
    deadline = Column(DateTime)
    
    # Salary information
    min_salary = Column(Integer)
    max_salary = Column(Integer)
    salary_currency = Column(String, default="USD")
    
    # Processing status
    status = Column(String, default=JobStatus.DISCOVERED)
    relevance_score = Column(Float, default=0.0)
    priority = Column(Integer, default=5)
    
    # Analysis results
    required_skills = Column(JSON, default=list)
    nice_to_have_skills = Column(JSON, default=list)
    experience_required = Column(Integer)
    
    # RAG embeddings reference
    embedding_id = Column(String)
    
    # Relationships
    applications = relationship("Application", back_populates="job")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_job_status', 'status'),
        Index('idx_job_company', 'company'),
        Index('idx_job_created', 'created_at'),
    )

class Application(Base):
    """Job application tracking"""
    __tablename__ = 'applications'
    
    id = Column(String, primary_key=True, default=lambda: hashlib.md5(str(datetime.utcnow()).encode()).hexdigest())
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    candidate_id = Column(String, ForeignKey('candidates.id'))
    job_id = Column(String, ForeignKey('jobs.id'))
    
    candidate = relationship("Candidate", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    
    # Application status
    status = Column(String, default=ApplicationStatus.PENDING)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    processing_time = Column(Float)  # seconds
    
    # Application data
    form_data = Column(JSON)  # Filled form fields
    cover_letter = Column(Text)
    additional_questions = Column(JSON)
    
    # Files
    resume_version = Column(String)  # Track which resume version was used
    portfolio_links = Column(JSON, default=list)
    
    # Tracking
    application_url = Column(String)
    confirmation_number = Column(String)
    
    # Screenshots and logs
    screenshots = Column(JSON, default=list)
    activity_log = Column(JSON, default=list)
    
    # Issues and review
    needs_review_reason = Column(Text)
    review_notes = Column(Text)
    captcha_encountered = Column(Boolean, default=False)
    errors = Column(JSON, default=list)
    
    # Metrics
    confidence_score = Column(Float, default=0.0)
    fields_filled = Column(Integer, default=0)
    fields_total = Column(Integer, default=0)
    
    def add_log_entry(self, action: str, details: Dict[str, Any]):
        """Add entry to activity log"""
        if not self.activity_log:
            self.activity_log = []
        
        self.activity_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'details': details
        })

class APIKey(Base):
    """API key management with encryption"""
    __tablename__ = 'api_keys'
    
    id = Column(String, primary_key=True, default=lambda: hashlib.md5(str(datetime.utcnow()).encode()).hexdigest())
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Provider information
    provider_name = Column(String, nullable=False)  # openai, anthropic, etc.
    key_alias = Column(String, nullable=False)  # User-friendly name
    
    # Encrypted key
    _encrypted_key = Column('encrypted_key', Text, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    usage_count = Column(Integer, default=0)
    
    # Quotas
    daily_quota = Column(Integer)
    monthly_quota = Column(Integer)
    tokens_used_today = Column(Integer, default=0)
    tokens_used_month = Column(Integer, default=0)
    
    # Cost tracking
    total_cost_usd = Column(Float, default=0.0)
    
    @hybrid_property
    def api_key(self):
        return encryption.decrypt(self._encrypted_key)
    
    @api_key.setter
    def api_key(self, value):
        self._encrypted_key = encryption.encrypt(value)

class AuditLog(Base):
    """Audit trail for compliance"""
    __tablename__ = 'audit_logs'
    
    id = Column(String, primary_key=True, default=lambda: hashlib.md5(str(datetime.utcnow()).encode()).hexdigest())
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Action details
    action = Column(String, nullable=False)
    entity_type = Column(String)  # job, application, candidate, etc.
    entity_id = Column(String)
    
    # Context
    user_id = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    
    # Details
    details = Column(JSON)
    
    # Compliance
    pii_accessed = Column(Boolean, default=False)
    data_exported = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
    )

# Database initialization
def init_database():
    """Initialize database and create tables"""
    engine = create_engine(settings.database_url, echo=False)
    Base.metadata.create_all(engine)
    return engine

def get_session() -> Session:
    """Get database session"""
    engine = init_database()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

# Export commonly used items
__all__ = [
    'Base', 'Candidate', 'Job', 'Application', 'APIKey', 'AuditLog',
    'JobStatus', 'ApplicationStatus', 'EncryptionManager', 'encryption',
    'init_database', 'get_session'
]
