from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import AccessToken


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("User with this email already exists")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']  # Use email as username
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class TokenForm(forms.ModelForm):
    token = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave blank to generate JWT token automatically'
        }),
        help_text='A JWT token will be generated automatically for API authentication',
        required=False
    )

    class Meta:
        model = AccessToken
        fields = ['service', 'token']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # For editing, provide regeneration option
            self.fields['token'].help_text = 'Leave blank to keep current token, or enter any value to regenerate a new JWT token'
            self.fields['token'].widget.attrs['placeholder'] = 'Enter any value to regenerate token'