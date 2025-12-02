from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('django_auth.apps.auth_app.urls')),
    path('internal/', include('django_auth.apps.auth_app.urls_internal')),
    path('', include('django_auth.apps.auth_app.ui_urls')),
]