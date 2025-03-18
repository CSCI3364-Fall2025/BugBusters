from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from . import views

def bypass_signup(request):
    """Redirect all attempts to access signup page back to home."""
    return redirect('/')

urlpatterns = [
    # Add a custom URL pattern to catch and redirect the 3rdparty signup page
    path('accounts/3rdparty/signup/', bypass_signup, name='bypass_signup'),
] 