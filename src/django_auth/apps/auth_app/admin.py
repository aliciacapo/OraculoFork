from django.contrib import admin
from .models import Repository, AccessToken


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'url', 'created_at')
    list_filter = ('created_at', 'owner')
    search_fields = ('name', 'url', 'owner__username', 'owner__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ('owner', 'service', 'masked_token', 'created_at', 'updated_at')
    list_filter = ('service', 'created_at', 'owner')
    search_fields = ('owner__username', 'owner__email', 'service')
    readonly_fields = ('encrypted_token', 'last_four', 'created_at', 'updated_at')
    
    def masked_token(self, obj):
        return obj.get_masked_token()
    masked_token.short_description = 'Token (Masked)'
    
    def has_change_permission(self, request, obj=None):
        # Prevent editing encrypted tokens through admin
        return False