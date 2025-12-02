from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Repository, AccessToken
from .ui_views import generate_jwt_token
from cryptography.fernet import Fernet
import json
import jwt


class AuthModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_repository_creation(self):
        repo = Repository.objects.create(
            name='test-repo',
            url='https://github.com/user/test-repo',
            owner=self.user
        )
        self.assertEqual(str(repo), 'test@example.com/test-repo')

    def test_access_token_encryption(self):
        token = AccessToken.objects.create(
            owner=self.user,
            service='github'
        )
        plain_token = 'ghp_1234567890abcdef'
        token.set_token(plain_token)
        token.save()
        
        # Token should be encrypted in database
        self.assertNotEqual(token.encrypted_token, plain_token.encode())
        # Should be able to decrypt
        self.assertEqual(token.get_token(), plain_token)
        # Should show masked version
        self.assertEqual(token.get_masked_token(), '****cdef')

    def test_access_token_unique_per_service(self):
        AccessToken.objects.create(owner=self.user, service='github')
        # Should not be able to create another github token for same user
        with self.assertRaises(Exception):
            AccessToken.objects.create(owner=self.user, service='github')


class AuthAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_user_registration(self):
        url = reverse('auth_app:register')
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    def test_jwt_token_obtain(self):
        url = reverse('auth_app:token_obtain_pair')
        data = {
            'username': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_repository_acl(self):
        # Create another user
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Create repository for other user
        other_repo = Repository.objects.create(
            name='other-repo',
            url='https://github.com/other/repo',
            owner=other_user
        )
        
        # Login as first user
        self.client.force_authenticate(user=self.user)
        
        # Should not see other user's repository
        url = reverse('auth_app:repository_list_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        
        # Should not be able to access other user's repository directly
        url = reverse('auth_app:repository_detail', kwargs={'pk': other_repo.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_token_acl(self):
        # Create another user with token
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='otherpass123'
        )
        other_token = AccessToken.objects.create(
            owner=other_user,
            service='github'
        )
        other_token.set_token('ghp_other_token')
        other_token.save()
        
        # Login as first user
        self.client.force_authenticate(user=self.user)
        
        # Should not see other user's tokens
        url = reverse('auth_app:token_list_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        
        # Should not be able to access other user's token directly
        url = reverse('auth_app:token_detail', kwargs={'pk': other_token.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_token_creation_and_masking(self):
        self.client.force_authenticate(user=self.user)
        
        url = reverse('auth_app:token_list_create')
        data = {
            'service': 'github',
            'token': 'ghp_1234567890abcdef'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that token is masked in response
        self.assertEqual(response.data['masked_token'], '****cdef')
        self.assertNotIn('token', response.data)  # Full token should not be returned
        
        # Verify token is encrypted in database
        token = AccessToken.objects.get(pk=response.data['id'])
        self.assertEqual(token.get_token(), 'ghp_1234567890abcdef')


class AuthUITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_required_for_token_pages(self):
        # Should redirect to login
        response = self.client.get('/tokens/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_token_list_view(self):
        self.client.login(username='test@example.com', password='testpass123')
        
        # Create a token
        token = AccessToken.objects.create(owner=self.user, service='github')
        token.set_token('ghp_test_token')
        token.save()
        
        response = self.client.get('/tokens/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GitHub')
        self.assertContains(response, '****')  # Masked token

    def test_token_creation_form(self):
        self.client.login(username='test@example.com', password='testpass123')
        
        # GET form
        response = self.client.get('/tokens/new/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add New Token')
        
        # POST form
        response = self.client.post('/tokens/new/', {
            'service': 'github',
            'token': 'ghp_new_test_token'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verify token was created
        self.assertTrue(AccessToken.objects.filter(owner=self.user, service='github').exists())

    def test_registration_form(self):
        response = self.client.post('/register/', {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())


class JWTTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_generate_jwt_token_returns_string_and_contains_user_id(self):
        """Unit: test_generate_jwt_token_returns_string_and_contains_user_id"""
        token = generate_jwt_token(self.user)
        
        # Should return a string
        self.assertIsInstance(token, str)
        
        # Should be decodable with our secret
        decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        
        # Should contain user_id
        self.assertEqual(decoded['user_id'], self.user.id)
        self.assertEqual(decoded['username'], self.user.get_username())
        self.assertIn('iat', decoded)
        self.assertIn('exp', decoded)

    def test_token_creation_flow_one_time_display(self):
        """Integration: test_token_creation_flow_one_time_display"""
        self.client.login(username='test@example.com', password='testpass123')
        
        # POST to create token
        response = self.client.post('/tokens/new/', {
            'service': 'github',
        })
        
        # Should redirect to created page
        self.assertEqual(response.status_code, 302)
        token_id = AccessToken.objects.get(owner=self.user, service='github').pk
        self.assertIn(f'/tokens/{token_id}/created/', response.url)
        
        # GET the created page - should show token
        response = self.client.get(f'/tokens/{token_id}/created/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'copy it now')
        self.assertContains(response, 'eyJ')  # JWT tokens start with eyJ
        
        # GET the same page again - should redirect with error
        response = self.client.get(f'/tokens/{token_id}/created/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/tokens/', response.url)

    def test_encrypted_token_saved(self):
        """DB: test_encrypted_token_saved"""
        self.client.login(username='test@example.com', password='testpass123')
        
        # Create token via UI
        response = self.client.post('/tokens/new/', {
            'service': 'github',
        })
        
        # Check database record
        token = AccessToken.objects.get(owner=self.user, service='github')
        
        # Should have encrypted_token
        self.assertIsNotNone(token.encrypted_token)
        
        # Decrypt and verify it's a valid JWT
        fernet = Fernet(settings.FERNET_KEY.encode())
        decrypted_token = fernet.decrypt(token.encrypted_token).decode()
        
        # Should be decodable JWT
        decoded = jwt.decode(decrypted_token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(decoded['user_id'], self.user.id)
        
        # Last four should match
        self.assertEqual(token.last_four, decrypted_token[-4:])