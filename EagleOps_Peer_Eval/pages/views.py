from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.conf import settings

def home_view(request):
    # If the user is not authenticated and there's a 'next' parameter pointing to signup
    if not request.user.is_authenticated and request.GET.get('next') and '3rdparty/signup' in request.GET.get('next'):
        # Redirect to the home page instead
        return redirect('/')
    
    return render(request, "home.html")  # render home.html template
