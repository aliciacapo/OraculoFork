from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Repository, AccessToken


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['email'],  # Use email as username
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class RepositorySerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Repository
        fields = ('id', 'name', 'url', 'owner', 'created_at', 'updated_at')
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class AccessTokenSerializer(serializers.ModelSerializer):
    token = serializers.CharField(write_only=True, help_text="The actual token (will be encrypted)")
    masked_token = serializers.SerializerMethodField(read_only=True)
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AccessToken
        fields = ('id', 'service', 'token', 'masked_token', 'owner', 'created_at', 'updated_at')
        read_only_fields = ('id', 'owner', 'masked_token', 'created_at', 'updated_at')

    def get_masked_token(self, obj):
        return obj.get_masked_token()

    def create(self, validated_data):
        token = validated_data.pop('token')
        validated_data['owner'] = self.context['request'].user
        
        # Always create new token (no unique constraint anymore)
        access_token = AccessToken.objects.create(**validated_data)
        access_token.set_token(token)
        access_token.save()
        return access_token

    def update(self, instance, validated_data):
        token = validated_data.pop('token', None)
        if token:
            instance.set_token(token)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class AccessTokenMetadataSerializer(serializers.ModelSerializer):
    """Serializer for returning only metadata without token field"""
    masked_token = serializers.SerializerMethodField()
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AccessToken
        fields = ('id', 'service', 'masked_token', 'owner', 'created_at', 'updated_at')

    def get_masked_token(self, obj):
        return obj.get_masked_token()