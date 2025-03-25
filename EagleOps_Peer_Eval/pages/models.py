from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # link default user model to custom UserProfile model
    first_name = models.CharField(max_length=100, blank=True, null=True)  # Store first name
    last_name = models.CharField(max_length=100, blank=True, null=True)  # Store last name
    avatar = models.ImageField(blank=True, null=True)  # New field for user avatar
    bio = models.TextField(blank=True, null=True)  # New field for user bio
    admin = models.BooleanField(default=False)  # Admin field to denote if user is admin or not

    def __str__(self):
        return self.user.username
    
    @property
    def full_name(self):
        # Combine first name and last name with a space, or return empty string if either is None
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else self.user.username
    
class Team(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(UserProfile, related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name