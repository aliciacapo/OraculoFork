from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Repository, AccessToken
from .serializers import (
    UserRegistrationSerializer, 
    UserProfileSerializer,
    RepositorySerializer,
    AccessTokenSerializer,
    AccessTokenMetadataSerializer
)


class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class RepositoryListCreateView(generics.ListCreateAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Repository.objects.filter(owner=self.request.user)


class RepositoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Repository.objects.filter(owner=self.request.user)


class AccessTokenListCreateView(generics.ListCreateAPIView):
    serializer_class = AccessTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AccessToken.objects.filter(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """Override to use metadata serializer for listing"""
        queryset = self.get_queryset()
        serializer = AccessTokenMetadataSerializer(queryset, many=True)
        return Response(serializer.data)


class AccessTokenDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AccessTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AccessToken.objects.filter(owner=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """Override to use metadata serializer for retrieval"""
        instance = self.get_object()
        serializer = AccessTokenMetadataSerializer(instance)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    """Login endpoint that returns JWT token"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username and password required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(username=username, password=password)
    if user is None:
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Generate JWT token
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    
    return Response({
        'token': access_token,
        'user_id': user.id,
        'username': user.username,
        'email': user.email
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """Return authenticated user info"""
    user = request.user
    return Response({
        "id": user.id,
        "username": user.get_username(),
        "email": getattr(user, "email", "")
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_tokens_view(request):
    """Return currently active token metadata per service"""
    tokens = AccessToken.objects.filter(owner=request.user)
    serializer = AccessTokenMetadataSerializer(tokens, many=True)
    return Response(serializer.data)