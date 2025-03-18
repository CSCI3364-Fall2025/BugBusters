from django import forms
from allauth.socialaccount.forms import SignupForm

class AutoSocialSignupForm(SignupForm):
    """
    A custom signup form that automatically saves the user without
    requiring any additional input.
    """
    
    def __init__(self, *args, **kwargs):
        # Initialize the form without any required fields
        super().__init__(*args, **kwargs)
        # Make sure no fields are required
        for field_name, field in self.fields.items():
            field.required = False
    
    def save(self, request):
        # Automatically save the user with information from the social account
        user = super().save(request)
        # We can add additional processing here if needed
        return user 