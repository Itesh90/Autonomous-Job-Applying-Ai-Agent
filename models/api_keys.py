# models/api_keys.py
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from cryptography.fernet import Fernet
import json
import os
import uuid
from datetime import datetime
from .encryption import encryption_manager
import hashlib

Base = declarative_base()

class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_name = Column(String, nullable=False)  # 'openai', 'anthropic', etc.
    key_alias = Column(String, nullable=False)  # User-friendly name
    encrypted_key = Column(Text, nullable=False)  # Fernet-encrypted API key
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0)
    daily_quota = Column(Integer, nullable=True)  # Optional daily limit
    monthly_quota = Column(Integer, nullable=True)  # Optional monthly limit
    
    def encrypt_key(self, raw_key: str):
        """Encrypt API key using Fernet"""
        self.encrypted_key = encryption_manager.encrypt(raw_key)
    
    def decrypt_key(self) -> str:
        """Decrypt API key"""
        return encryption_manager.decrypt(self.encrypted_key)
    
    def rotate_key(self, new_key: str):
        """Rotate to new API key"""
        old_key = self.decrypt_key()
        self.encrypt_key(new_key)
        # Log rotation for audit trail
        AuditLog.create(
            action='key_rotation',
            entity_id=str(self.id),
            details={'old_key_hash': hashlib.sha256(old_key.encode()).hexdigest()[:8]}
        )

class UsageRecord(Base):
    __tablename__ = 'usage_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey('api_keys.id'))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    tokens_used = Column(Integer)
    cost_usd = Column(Integer)  # Store as cents to avoid floating point issues
    request_type = Column(String)  # 'mapping', 'cover_letter', etc.
    success = Column(Boolean)
    error_message = Column(Text, nullable=True)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    action = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    
    @classmethod
    def create(cls, action: str, entity_id: str = None, details: dict = None):
        """Create an audit log entry"""
        log_entry = cls(
            action=action,
            entity_id=entity_id,
            details=json.dumps(details) if details else None
        )
        return log_entry
