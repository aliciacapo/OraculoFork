from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

app_name = 'auth_app'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.UserProfileView.as_view(), name='user_profile'),
    
    # Repository endpoints
    path('repositories/', views.RepositoryListCreateView.as_view(), name='repository_list_create'),
    path('repositories/<int:pk>/', views.RepositoryDetailView.as_view(), name='repository_detail'),
    
    # Token endpoints
    path('tokens/', views.AccessTokenListCreateView.as_view(), name='token_list_create'),
    path('tokens/<int:pk>/', views.AccessTokenDetailView.as_view(), name='token_detail'),
    path('tokens/current/', views.current_tokens_view, name='current_tokens'),
]