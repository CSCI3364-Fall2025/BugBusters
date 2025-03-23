from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.conf import settings
from .models import Team

def home_view(request):
    # If the user is not authenticated and there's a 'next' parameter pointing to signup
    if not request.user.is_authenticated and request.GET.get('next') and '3rdparty/signup' in request.GET.get('next'):
        # Redirect to the home page instead
        return redirect('/')
    
    return render(request, "home.html")  # render home.html template

def todo_view(request):
    return render(request, "to_do.html")

def teams(request):
    user = request.user.userprofile

    if user.admin:
        # Admins see all teams
        teams = Team.objects.prefetch_related('members__user').all()
    else:
        # Non-admins see only their team(s)
        teams = Team.objects.prefetch_related('members__user').filter(members=user)
    
    return render(request, 'teams.html', {'teams': teams})
