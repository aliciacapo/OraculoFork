#!/usr/bin/env python3
"""
Script to generate secure keys for Django authentication service.
Run this script to generate the required environment variables.
"""

import secrets
from cryptography.fernet import Fernet

def generate_django_secret_key():
    """Generate a secure Django secret key"""
    return ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for _ in range(50))

def generate_fernet_key():
    """Generate a Fernet encryption key"""
    return Fernet.generate_key().decode()

if __name__ == '__main__':
    print("=== Django Authentication Service - Key Generator ===\n")
    
    django_key = generate_django_secret_key()
    fernet_key = generate_fernet_key()
    
    print("Add these to your .env file:\n")
    print(f"DJANGO_SECRET_KEY={django_key}")
    print(f"FERNET_KEY={fernet_key}")
    print(f"DEBUG=True")
    print("\nIMPORTANT: Keep these keys secure and never commit them to version control!")