# scripts/generate_encryption_key.py
from cryptography.fernet import Fernet
import base64
import os

def generate_encryption_key():
    """Generate a new Fernet encryption key"""
    key = Fernet.generate_key()
    return key.decode()

def validate_encryption_key(key_string: str) -> bool:
    """Validate if a string is a valid Fernet key"""
    try:
        # Try to decode the key
        key_bytes = key_string.encode()
        Fernet(key_bytes)
        return True
    except Exception:
        return False

if __name__ == "__main__":
    print("Generating new Fernet encryption key...")
    new_key = generate_encryption_key()
    
    print(f"Generated key: {new_key}")
    print("\nAdd this to your .env file:")
    print(f"ENCRYPTION_KEY={new_key}")
    
    # Validate the generated key
    if validate_encryption_key(new_key):
        print("\n✅ Key validation successful!")
    else:
        print("\n❌ Key validation failed!")
