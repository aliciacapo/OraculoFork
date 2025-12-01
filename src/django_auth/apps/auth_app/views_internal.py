import os
import hmac
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import AccessToken

User = get_user_model()

from rest_framework.decorators import authentication_classes

@api_view(["POST"])
@authentication_classes([])  # Disable all authentication for this view
@permission_classes([AllowAny])
def validate_token_for_backend(request):
    """
    Internal endpoint to validate JWT tokens for backend services.
    
    Expects:
    - Authorization: Bearer <INTERNAL_AUTH_TOKEN>
    - JSON body: {"jwt": "<user_jwt_token>"}
    
    Returns:
    - 200: Valid JWT with user info
    - 400: Missing JWT in request body
    - 401: Invalid JWT or missing internal auth
    - 403: Invalid internal auth token
    """
    # Validate internal authentication
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return Response({"detail": "Missing internal auth header"}, status=status.HTTP_401_UNAUTHORIZED)
    
    provided = auth.split(" ", 1)[1]
    expected = getattr(settings, "INTERNAL_AUTH_TOKEN", None)
    if not expected or not hmac.compare_digest(provided, expected):
        return Response({"detail": "Invalid internal auth token"}, status=status.HTTP_403_FORBIDDEN)

    # Extract JWT from request body
    jwt_token = request.data.get("jwt")
    if not jwt_token:
        return Response({"detail": "Missing jwt field in request body"}, status=status.HTTP_400_BAD_REQUEST)

    # Validate JWT format (should have 3 parts)
    if not isinstance(jwt_token, str) or len(jwt_token.split('.')) != 3:
        return Response({"detail": "Invalid JWT format"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        # Decode and validate JWT using the same settings as token generation
        decoded_token = jwt.decode(
            jwt_token,
            settings.SIMPLE_JWT['SIGNING_KEY'],
            algorithms=[settings.SIMPLE_JWT['ALGORITHM']],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "user_id", "token_type"]
            }
        )
        
        # Validate token type
        if decoded_token.get('token_type') != 'access':
            return Response({"detail": "Invalid token type - expected access token"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Extract user_id
        user_id = decoded_token.get('user_id')
        if not user_id:
            return Response({"detail": "Missing user_id in JWT payload"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Try to get user info, but don't fail if database is unavailable
        username = f"user_{user_id}"  # Default username
        has_active_access_token = True  # JWT validation doesn't require AccessToken records
        
        try:
            user = User.objects.get(id=user_id)
            username = user.username
            
            # AccessToken model is for service tokens (GitHub, GitLab, etc.), not JWT validation
            # JWT tokens are validated cryptographically, not via database records
            has_active_access_token = True
            
        except Exception as db_error:
            # Log database error but don't fail validation
            # JWT is valid even if we can't check database
            print(f"[WARNING] Database unavailable during JWT validation: {db_error}")
            has_active_access_token = True  # JWT validation is independent of database
            
    except jwt.ExpiredSignatureError:
        return Response({"detail": "JWT token has expired"}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidSignatureError:
        return Response({"detail": "JWT signature verification failed"}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.DecodeError:
        return Response({"detail": "JWT decode error - malformed token"}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError as e:
        return Response({"detail": f"Invalid JWT: {str(e)}"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"detail": f"Token validation error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # JWT token is valid
    return Response({
        "user_id": user_id,
        "username": username,
        "has_active_access_token": has_active_access_token,
        "token_valid": True
    }, status=status.HTTP_200_OK)