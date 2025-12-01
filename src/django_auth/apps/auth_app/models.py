from django.db import models
from django.contrib.auth.models import User
from cryptography.fernet import Fernet
from django.conf import settings


class Repository(models.Model):
    """Minimal repository model for user ownership"""
    name = models.CharField(max_length=255)
    url = models.URLField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='repositories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['owner', 'name']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.owner.username}/{self.name}"


class AccessToken(models.Model):
    """Encrypted token storage for various services"""
    SERVICE_CHOICES = [
        ('github', 'GitHub'),
        ('gitlab', 'GitLab'),
        ('bitbucket', 'Bitbucket'),
        ('other', 'Other'),
    ]
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_tokens')
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    encrypted_token = models.BinaryField()  # Stores encrypted token
    last_four = models.CharField(max_length=4)  # Last 4 chars for display
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def set_token(self, plain_token):
        """Encrypt and store token, save last 4 chars for display"""
        if not plain_token:
            raise ValueError("Token cannot be empty")
        
        fernet = Fernet(settings.FERNET_KEY.encode())
        self.encrypted_token = fernet.encrypt(plain_token.encode())
        self.last_four = plain_token[-4:] if len(plain_token) >= 4 else plain_token
        
    def get_token(self):
        """Decrypt and return the full token - use sparingly"""
        if not self.encrypted_token:
            return None
        
        fernet = Fernet(settings.FERNET_KEY.encode())
        return fernet.decrypt(self.encrypted_token).decode()
    
    def get_masked_token(self):
        """Return masked token for display"""
        if not self.last_four:
            return "****"
        return f"****{self.last_four}"

    def __str__(self):
        return f"{self.owner.username} - {self.service} (****{self.last_four})"