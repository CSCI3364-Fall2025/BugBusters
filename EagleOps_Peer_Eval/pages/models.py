from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE) # link default user model to custom UserProfile model
    admin = models.BooleanField(default=False) # admin field to denote if user is admin or not

    def __str__(self):
        return self.user.username