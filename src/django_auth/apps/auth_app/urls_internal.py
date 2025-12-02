from django.urls import path
from .views_internal import validate_token_for_backend

urlpatterns = [
    path('validate-token/', validate_token_for_backend, name='validate-token-internal'),
]