from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to bypass the signup form completely and
    auto-create and login users from social accounts.
    """
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a social login is successful but before the actual login.
        We're using this to bypass the signup form redirect.
        """
        # Check if this social login is for an existing user
        if sociallogin.is_existing:
            return

        # Check if we can match the social account email to an existing user
        if sociallogin.email_addresses:
            email = sociallogin.email_addresses[0].email
            try:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
                # Immediately redirect to prevent the signup form
                raise ImmediateHttpResponse(redirect(settings.LOGIN_REDIRECT_URL))
            except User.DoesNotExist:
                pass

    def save_user(self, request, sociallogin, form=None):
        """
        Custom save_user to automatically create user and skip the signup form.
        """
        user = super().save_user(request, sociallogin, form)
        
        # If user is created, make sure we don't show the signup form
        if not sociallogin.is_existing:
            # If user is created successfully, redirect to home
            sociallogin.state['next'] = settings.LOGIN_REDIRECT_URL
            
        return user
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user instance with data from social login.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # If username is not required, use the email as username
        if not getattr(settings, 'ACCOUNT_USERNAME_REQUIRED', True):
            user.username = sociallogin.email_addresses[0].email.split('@')[0]
            
        return user 