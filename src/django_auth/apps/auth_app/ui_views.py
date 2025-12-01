from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from cryptography.fernet import Fernet
import jwt
from datetime import datetime, timedelta
from .models import AccessToken
from .forms import TokenForm, UserRegistrationForm


def generate_jwt_token(user, exp_hours: int = 2) -> str:
    from rest_framework_simplejwt.tokens import RefreshToken
    
    # Use SimpleJWT to generate a token exactly like the standard API does
    refresh = RefreshToken.for_user(user)
    access_token = refresh.access_token
    
    # DO NOT modify the token - let SimpleJWT handle everything
    return str(access_token)


def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('token_list')
    else:
        form = UserRegistrationForm()
    return render(request, 'auth_app/register.html', {'form': form})


@login_required
def token_list_view(request):
    tokens = AccessToken.objects.filter(owner=request.user)
    return render(request, 'auth_app/token_list.html', {'tokens': tokens})


@login_required
@csrf_protect
def token_create_view(request):
    if request.method == 'POST':
        form = TokenForm(request.POST)
        if form.is_valid():
            # Generate JWT token for the user
            raw_jwt = generate_jwt_token(request.user)
            
            # Create and save the AccessToken with encrypted JWT
            token = form.save(commit=False)
            token.owner = request.user
            
            # Encrypt and store the JWT token
            fernet = Fernet(settings.FERNET_KEY.encode())
            token.encrypted_token = fernet.encrypt(raw_jwt.encode())
            token.last_four = raw_jwt[-4:]
            token.save()
            
            # Store one-time display info in session
            request.session["show_token_id"] = token.pk
            request.session["show_token_value"] = raw_jwt
            
            messages.success(request, f'{token.service} token created successfully!')
            return redirect('token_created', pk=token.pk)
    else:
        form = TokenForm()
    return render(request, 'auth_app/token_form.html', {
        'form': form, 
        'title': 'Add New Token'
    })


@login_required
@csrf_protect
def token_edit_view(request, pk):
    token = get_object_or_404(AccessToken, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        form = TokenForm(request.POST, instance=token)
        if form.is_valid():
            # Check if user wants to regenerate the token
            regenerate_token = form.cleaned_data.get('token')
            
            if regenerate_token:  # User provided new token input (regenerate)
                # Generate new JWT token
                raw_jwt = generate_jwt_token(request.user)
                
                # Encrypt and store the new JWT token
                fernet = Fernet(settings.FERNET_KEY.encode())
                token.encrypted_token = fernet.encrypt(raw_jwt.encode())
                token.last_four = raw_jwt[-4:]
                token.save()
                
                # Store one-time display info in session
                request.session["show_token_id"] = token.pk
                request.session["show_token_value"] = raw_jwt
                
                messages.success(request, f'{token.service} token regenerated successfully!')
                return redirect('token_created', pk=token.pk)
            else:
                # Just update service type without regenerating token
                form.save()
                messages.success(request, f'{token.service} token updated successfully!')
                return redirect('token_list')
    else:
        form = TokenForm(instance=token)
    
    return render(request, 'auth_app/token_form.html', {
        'form': form, 
        'title': f'Edit {token.service} Token',
        'token': token
    })


@login_required
@require_http_methods(["POST"])
@csrf_protect
def token_delete_view(request, pk):
    token = get_object_or_404(AccessToken, pk=pk, owner=request.user)
    service = token.service
    token.delete()
    messages.success(request, f'{service} token deleted successfully!')
    return redirect('token_list')


@login_required
def token_created_view(request, pk):
    """
    Display the full JWT token exactly once after creation.
    Uses session-based security to prevent repeat access.
    """
    token = get_object_or_404(AccessToken, pk=pk, owner=request.user)
    
    # Check if this token was just created (stored in session)
    show_token_id = request.session.get("show_token_id")
    jwt_token = request.session.get("show_token_value")
    
    if not jwt_token or show_token_id != pk:
        # Token not in session or wrong token - redirect with error
        messages.error(request, 'Token display is only available immediately after creation.')
        return redirect('token_list')
    
    # Remove from session to prevent repeat access
    request.session.pop("show_token_id", None)
    request.session.pop("show_token_value", None)
    
    return render(request, 'auth_app/token_created.html', {
        'token': token,
        'jwt_token': jwt_token,
    })