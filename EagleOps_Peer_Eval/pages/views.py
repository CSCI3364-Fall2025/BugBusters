from django.shortcuts import render

def home_view(request):
    return render(request, "home.html")  

def student_login_view(request):
    return render(request, "student_login.html")  

def admin_login_view(request):
    return render(request, "admin_login.html")  

def create_account_view(request):
    return render(request, "create_account.html")  
