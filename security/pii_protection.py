# security/pii_protection.py
from cryptography.fernet import Fernet
import hashlib
import os
import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class PIIProtectionManager:
    """Enhanced PII protection and compliance manager"""
    
    PII_PATTERNS = {
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        'phone': re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
        'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        'credit_card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
        'address': re.compile(r'\d+\s+\w+\s+(st|street|ave|avenue|rd|road|ln|lane|dr|drive|ct|court)', re.IGNORECASE)
    }
    
    def __init__(self):
        from models.encryption import encryption_manager
        self.encryption_manager = encryption_manager
    
    def scan_for_pii(self, text: str) -> Dict[str, List[str]]:
        """Scan text for PII patterns"""
        found_pii = {}
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                found_pii[pii_type] = matches
        
        return found_pii
    
    def redact_pii(self, text: str, redaction_char: str = '*') -> str:
        """Redact PII from text"""
        redacted_text = text
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            def redact_match(match):
                original = match.group(0)
                if pii_type == 'email':
                    # Keep first character and domain
                    parts = original.split('@')
                    username = parts[0][0] + '*' * (len(parts[0]) - 1)
                    return f"{username}@{parts[1]}"
                else:
                    # General redaction
                    return redaction_char * len(original)
            
            redacted_text = pattern.sub(redact_match, redacted_text)
        
        return redacted_text
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in data dictionary"""
        sensitive_fields = ['email', 'phone', 'address', 'full_name', 'resume_content']
        
        encrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_value = self.encryption_manager.encrypt(
                    str(encrypted_data[field])
                )
                encrypted_data[field] = encrypted_value
        
        return encrypted_data
    
    def create_data_hash(self, data: str) -> str:
        """Create SHA-256 hash of data for deduplication"""
        return hashlib.sha256(data.encode()).hexdigest()

# Global PII protection manager
pii_manager = PIIProtectionManager()
