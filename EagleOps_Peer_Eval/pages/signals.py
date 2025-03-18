from django.db.models.signals import post_save
from django.dispatch import receiver
from social_django.models import UserSocialAuth
from .models import GoogleOAuthProfile

ADMIN_EMAILS = [
    "spotob@bc.edu",
]

@receiver(post_save, sender = UserSocialAuth)
def save_google_oauth_info(sender, instance, created, **kwargs):
    if created:
        user = instance.user

        # Fetch the necessary info from the instance's extra_data (which stores OAuth info)
        name = instance.extra_data.get('name')
        print(name)
        google_email = instance.extra_data.get('email')
        print(google_email)

        if name and google_email:
            admin = google_email in ADMIN_EMAILS

            google_oauth_profile, created = GoogleOAuthProfile.objects.update_or_create(
                user=user,
                defaults={
                    'google_name': name,
                    'google_email': google_email,
                    'admin': admin
                }
            )