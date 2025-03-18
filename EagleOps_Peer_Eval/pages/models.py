from django.db import models
from django.contrib.auth.models import User

class GoogleOAuthProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="google_oauth_profile")
    name = models.CharField(max_length=255, null=True, blank=True)
    google_email = models.EmailField(null=True, blank=True)
    admin = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.google_name} ({self.google_email})'