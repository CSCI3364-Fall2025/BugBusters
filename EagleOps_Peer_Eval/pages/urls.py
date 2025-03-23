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
    
    # Course management URLs - only include patterns not in main URLs
    path('', views.home_view, name='home'),
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('profile/', views.profile, name='profile'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('courses/create/', views.create_course, name='create_course'),
    path('courses/<int:course_id>/edit/', views.edit_course, name='edit_course'),
    
    # Form template management URLs
    path('courses/<int:course_id>/templates/new/', views.template_create_edit, name='template_create'),
    path('courses/<int:course_id>/templates/<int:template_id>/edit/', views.template_create_edit, name='template_edit'),
    path('courses/<int:course_id>/templates/<int:template_id>/duplicate/', views.template_duplicate, name='template_duplicate'),
    path('courses/<int:course_id>/templates/<int:template_id>/delete/', views.template_delete, name='template_delete'),
    
    # Form management URLs
    path('courses/<int:course_id>/forms/new/', views.form_create_edit, name='form_create'),
    path('courses/<int:course_id>/forms/<int:form_id>/edit/', views.form_create_edit, name='form_edit'),
    path('courses/<int:course_id>/forms/<int:form_id>/publish/', views.form_publish, name='form_publish'),
    path('courses/<int:course_id>/forms/<int:form_id>/unpublish/', views.form_unpublish, name='form_unpublish'),
    path('courses/<int:course_id>/forms/<int:form_id>/delete/', views.form_delete, name='form_delete'),
] 