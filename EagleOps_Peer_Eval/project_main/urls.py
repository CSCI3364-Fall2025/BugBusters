"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from pages import views as page_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", page_views.home_view, name="home"),  # Home Page w/ ifs dependent on user authentication
    path("todo/", page_views.todo_view, name="todo"),

    # Include our custom URLs first so they take precedence 
    path("", include("pages.urls")),
    
    # Allauth URLs come after our custom paths
    path("accounts/", include("allauth.urls")),  # Allauth for authentication

    # Path to the teams page
    path('teams/', page_views.teams, name='teams'),
]