# models/encryption.py
from cryptography.fernet import Fernet, InvalidToken
import os
import base64
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Handles encryption and decryption using Fernet symmetric encryption."""

    def __init__(self, key: str = None):
        """
        Initializes the EncryptionManager.

        Args:
            key (str, optional): The Fernet key. If not provided, uses settings.ENCRYPTION_KEY.
                                 Primarily for testing or key rotation scenarios.
        """
        if key:
            self.key = key.encode() if isinstance(key, str) else key
        else:
            # settings.encryption_key is already a string from .env
            self.key = settings.encryption_key.encode()

        try:
            # Validate the key format
            base64.urlsafe_b64decode(self.key)
            self.cipher_suite = Fernet(self.key)
        except (ValueError, InvalidToken) as e:
            logger.error(f"Invalid Fernet key provided: {e}")
            raise ValueError("The provided ENCRYPTION_KEY is not a valid Fernet key.") from e

    def encrypt(self, data: str) -> str:
        """Encrypts a string."""
        if not isinstance(data, str):
            raise TypeError("Data to encrypt must be a string.")
        try:
            encrypted_data = self.cipher_suite.encrypt(data.encode())
            return encrypted_data.decode() # Return as string for storage
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypts a string."""
        if not isinstance(encrypted_data, str):
            raise TypeError("Encrypted data must be a string.")
        try:
            decrypted_data = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except InvalidToken:
            logger.error("Decryption failed: Invalid token. Key might be incorrect.")
            raise ValueError("Decryption failed: Invalid token.")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

# Global instance for application use
# Initialized based on settings
encryption_manager = EncryptionManager()
