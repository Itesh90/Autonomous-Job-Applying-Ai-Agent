"""
Application configuration and settings management
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Database
    database_url: str = Field(default="sqlite:///./data/jobagent.db")
    redis_url: str = Field(default="redis://localhost:6379/0")
    mongodb_url: str = Field(default="mongodb://localhost:27017/jobagent_vectors")
    
    # Encryption
    encryption_key: str = Field(default="")
    
    # LLM Providers
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    huggingface_api_key: Optional[str] = Field(default=None)
    default_llm_provider: str = Field(default="openai")
    llm_temperature: float = Field(default=0.0)
    llm_max_tokens: int = Field(default=2000)
    
    # Application
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    max_concurrent_jobs: int = Field(default=3)
    rate_limit_delay: int = Field(default=5)
    dry_run_mode: bool = Field(default=False)
    
    # Security
    allowed_hosts: str = Field(default="localhost,127.0.0.1")
    session_secret: str = Field(default="")
    jwt_secret_key: str = Field(default="")
    
    # Browser
    headless_browser: bool = Field(default=True)
    browser_timeout: int = Field(default=30000)
    use_selenium: bool = Field(default=True)
    use_undetected_chrome: bool = Field(default=True)
    
    # File Storage
    upload_max_size_mb: int = Field(default=10)
    screenshot_retention_days: int = Field(default=30)
    log_retention_days: int = Field(default=90)
    data_dir: Path = Field(default=Path("./data"))
    logs_dir: Path = Field(default=Path("./logs"))
    screenshots_dir: Path = Field(default=Path("./screenshots"))
    
    # RAG Settings
    chroma_persist_directory: Path = Field(default=Path("./data/chroma"))
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    
    # Job Sites
    linkedin_email: Optional[str] = Field(default=None)
    linkedin_password: Optional[str] = Field(default=None)
    indeed_api_key: Optional[str] = Field(default=None)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator("encryption_key", pre=True)
    def validate_encryption_key(cls, v):
        if not v:
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()
        return v
    
    @validator("session_secret", "jwt_secret_key", pre=True)
    def generate_secrets(cls, v):
        if not v:
            import secrets
            return secrets.token_urlsafe(32)
        return v
    
    @validator("data_dir", "logs_dir", "screenshots_dir", "chroma_persist_directory")
    def create_directories(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_llm_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Get LLM provider configuration"""
        provider = provider or self.default_llm_provider
        
        configs = {
            "openai": {
                "api_key": self.openai_api_key,
                "model": "gpt-4-turbo-preview",
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens
            },
            "anthropic": {
                "api_key": self.anthropic_api_key,
                "model": "claude-3-opus-20240229",
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens
            },
            "huggingface": {
                "api_key": self.huggingface_api_key,
                "model": "meta-llama/Llama-2-70b-chat-hf",
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens
            }
        }
        
        return configs.get(provider, configs["openai"])
    
    def get_browser_config(self) -> Dict[str, Any]:
        """Get browser configuration for Selenium/Playwright"""
        return {
            "headless": self.headless_browser,
            "timeout": self.browser_timeout,
            "use_selenium": self.use_selenium,
            "use_undetected": self.use_undetected_chrome,
            "window_size": (1920, 1080),
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary (excluding sensitive data)"""
        data = self.dict()
        # Remove sensitive keys
        sensitive_keys = [
            "encryption_key", "openai_api_key", "anthropic_api_key",
            "huggingface_api_key", "linkedin_password", "session_secret",
            "jwt_secret_key"
        ]
        for key in sensitive_keys:
            if key in data:
                data[key] = "***REDACTED***"
        return data

# Global settings instance
settings = Settings()

# Feature flags
FEATURES = {
    "rag_enabled": True,
    "selenium_fallback": True,
    "multi_provider_llm": True,
    "captcha_detection": True,
    "dry_run_available": True,
    "monitoring_enabled": True,
    "audit_logging": True,
    "data_encryption": True
}
