from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import social_account_added, pre_social_login
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.conf import settings

@receiver(user_logged_in)
def update_user_profile_on_login(sender, request, user, **kwargs):
    admin_emails = ['hazardo@bc.edu'] # Existing superuser email
    user_profile, created = UserProfile.objects.get_or_create(user = user)

    if user.email in admin_emails: # check if user email is in admin_emails
        user_profile.admin = True
        # Also ensure the user has superuser permissions if their email matches
        if not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save()
            print(f"User {user.username} granted superuser and staff status")
    else:
        user_profile.admin = False

    user_profile.save() # save the user profile
    print(f"User {user.username} admin status updated to {user_profile.admin}") # print user status to the console

@receiver(social_account_added)
def process_social_account(request, sociallogin, **kwargs):
    """Handle new social accounts and link to existing users if needed."""
    user = sociallogin.user
    email = user.email
    
    # Check if we have an existing superuser with the same email
    try:
        existing_super = User.objects.filter(is_superuser=True, email=email).first()
        if existing_super and existing_super != user:
            print(f"Found existing superuser {existing_super.username} with matching email")
            
            # Transfer social account to the existing superuser
            social_account = sociallogin.account
            social_account.user = existing_super
            social_account.save()
            
            print(f"Transferred social account to existing superuser {existing_super.username}")
            
            # Log in as the superuser instead
            return existing_super
    except Exception as e:
        print(f"Error linking social account: {e}")
    
    return None

@receiver(pre_social_login)
def auto_login_without_signup_form(sender, request, sociallogin, **kwargs):
    """Prevent redirect to signup form by auto-connecting the social account."""
    # If this social account is already connected to a user, allow normal flow
    if sociallogin.is_existing:
        return

    # If we have an email from social account
    if sociallogin.email_addresses:
        email = sociallogin.email_addresses[0].email
        # Try to find a user with this email
        try:
            user = User.objects.get(email=email)
            # Connect the social account to the existing user
            sociallogin.connect(request, user)
            # Print info
            print(f"Auto-connected social account to existing user: {user.username}")
        except User.DoesNotExist:
            # Create a new user automatically instead of showing the signup form
            pass