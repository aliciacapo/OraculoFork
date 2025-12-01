from django.urls import path
from django.contrib.auth import views as auth_views
from . import ui_views

urlpatterns = [
    # Authentication UI
    path('login/', auth_views.LoginView.as_view(template_name='auth_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', ui_views.register_view, name='register'),
    
    # Token management UI
    path('tokens/', ui_views.token_list_view, name='token_list'),
    path('tokens/new/', ui_views.token_create_view, name='token_create'),
    path('tokens/<int:pk>/edit/', ui_views.token_edit_view, name='token_edit'),
    path('tokens/<int:pk>/delete/', ui_views.token_delete_view, name='token_delete'),
    path('tokens/<int:pk>/created/', ui_views.token_created_view, name='token_created'),
    
    # Redirect root to tokens
    path('', ui_views.token_list_view, name='home'),
]