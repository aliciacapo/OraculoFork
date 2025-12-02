import os
import sys
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY or JWT_SECRET_KEY.strip() == '':
    print("CRITICAL ERROR: JWT_SECRET_KEY environment variable is not set or empty!")
    print("This is required for JWT token validation in FastAPI.")
    print("Available environment variables:")
    for key in sorted(os.environ.keys()):
        if 'JWT' in key or 'SECRET' in key or 'TOKEN' in key:
            print(f"  {key}={os.environ[key][:20]}..." if len(os.environ[key]) > 20 else f"  {key}={os.environ[key]}")
    print("Please ensure JWT_SECRET_KEY is set in Docker Compose environment.")
    sys.exit(1)

security = HTTPBearer()
DJANGO_VALIDATE_URL = os.getenv("DJANGO_VALIDATE_URL", "http://django-auth:8001/internal/validate-token/")
INTERNAL_AUTH_TOKEN = os.getenv("INTERNAL_AUTH_TOKEN")

if not INTERNAL_AUTH_TOKEN or INTERNAL_AUTH_TOKEN.strip() == '':
    print("CRITICAL ERROR: INTERNAL_AUTH_TOKEN environment variable is not set or empty!")
    print("This is required for backend-to-backend authentication.")
    print("Available environment variables:")
    for key in sorted(os.environ.keys()):
        if 'JWT' in key or 'SECRET' in key or 'TOKEN' in key:
            print(f"  {key}={os.environ[key][:20]}..." if len(os.environ[key]) > 20 else f"  {key}={os.environ[key]}")
    print("Please ensure INTERNAL_AUTH_TOKEN is set in Docker Compose environment.")
    sys.exit(1)

def validate_user_jwt(credentials=Depends(security)):
    """Validate JWT token with Django auth service and check AccessToken existence"""
    if not INTERNAL_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal auth not configured"
        )
    
    jwt_token = credentials.credentials
    headers = {
        "Authorization": f"Bearer {INTERNAL_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"[AUTH] Validating JWT with Django at {DJANGO_VALIDATE_URL}")
        resp = requests.post(
            DJANGO_VALIDATE_URL, 
            json={"jwt": jwt_token},
            headers=headers, 
            timeout=10
        )
        print(f"[AUTH] Django response: {resp.status_code} - {resp.text}")
    except requests.RequestException as e:
        print(f"[AUTH] Request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Auth validation failed - service unavailable"
        )
    
    if resp.status_code != 200:
        try:
            error_detail = resp.json().get("detail", "Unauthorized")
        except:
            error_detail = f"Unauthorized (HTTP {resp.status_code})"
        print(f"[AUTH] Validation failed: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=error_detail
        )
    
    try:
        body = resp.json()
        if not body.get("has_active_access_token"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="No active access token"
            )
        
        print(f"[AUTH] Validation successful for user {body.get('user_id')}")
        return {
            "user_id": body.get("user_id"),
            "username": body.get("username")
        }
    except Exception as e:
        print(f"[AUTH] Response parsing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid response from auth service"
        )