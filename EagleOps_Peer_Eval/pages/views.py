from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.conf import settings
from .models import Team

def home_view(request):
    if request.method == "POST":
        # Check which form is being submitted (here we assume it's the profile update)
        if "first_name" in request.POST:
            profile = request.user.userprofile
            profile.first_name = request.POST.get("first_name", profile.first_name)
            profile.last_name = request.POST.get("last_name", profile.last_name)
            profile.bio = request.POST.get("bio", profile.bio)
            if request.FILES.get("avatar"):
                profile.avatar = request.FILES["avatar"]
            profile.save()
            # Optionally, add a success message or redirect
            return redirect(request.path)
    return render(request, "home.html")

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
