from django.shortcuts import render, redirect

def home_view(request):
    return render(request, "home.html")  

def success_login_view(request):
    return render(request, "success_login.html")

def login_view(request):
    return render(request, "users/login.html")

# def landing_view(request):
#     if request.user.is_authenticated:
#         try:
#             google_profile = GoogleOAuthProfile.objects.get(user=request.user)
#         except GoogleOAuthProfile.DoesNotExist:
#             google_profile = None
#         return render(request, "landing.html", {"google_profile": google_profile})

#     return redirect('login')
