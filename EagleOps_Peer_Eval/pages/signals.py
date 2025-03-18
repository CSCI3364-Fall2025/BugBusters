from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(user_logged_in)
def update_user_profile_on_login(sender, request, user, **kwargs):
    admin_emails = [] # add admin emails here for hardcoding
    user_profile, created = UserProfile.objects.get_or_create(user = user)

    if user.email in admin_emails: # check if user email is in admin_emails
        user_profile.admin = True
    else:
        user_profile.admin = False

    user_profile.save() # save the user profile
    print(f"User {user.username} admin status updated to {user_profile.admin}") # print user status to the console