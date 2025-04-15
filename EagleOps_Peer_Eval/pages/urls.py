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
    path('courses/', views.courses, name='courses'),
    path('courses/join/', views.join_course, name='join_course'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('courses/create/', views.create_course, name='create_course'),
    path('courses/<int:course_id>/edit/', views.edit_course, name='edit_course'),
    
    # Form template management URLs
    path('courses/<int:course_id>/templates/new/', views.template_create_edit, name='template_create'),
    path('courses/<int:course_id>/templates/<int:template_id>/edit/', views.template_create_edit, name='template_edit'),
    path('courses/<int:course_id>/templates/<int:template_id>/duplicate/', views.template_duplicate, name='template_duplicate'),
    path('courses/<int:course_id>/templates/<int:template_id>/delete/', views.template_delete, name='template_delete'),
    path('courses/<int:course_id>/templates/<int:template_id>/preview/', views.template_preview, name='template_preview'),
    
    # Form management URLs
    path('courses/<int:course_id>/forms/create/', views.form_create_edit, name='form_create'),
    path('courses/<int:course_id>/forms/<int:form_id>/edit/', views.form_create_edit, name='form_edit'),
    path('courses/<int:course_id>/forms/<int:form_id>/open/', views.form_open, name='form_open'),
    path('courses/<int:course_id>/forms/<int:form_id>/close/', views.form_close, name='form_close'),
    path('courses/<int:course_id>/forms/<int:form_id>/delete/', views.form_delete, name='form_delete'),
    path('courses/<int:course_id>/forms/<int:form_id>/preview/', views.form_preview, name='form_preview'),
    
    # Form response URLs (for students to complete evaluations)
    path('courses/<int:course_id>/forms/<int:form_id>/evaluations/', views.form_evaluations, name='form_evaluations'),
    path('courses/<int:course_id>/forms/<int:form_id>/evaluate/<int:evaluatee_id>/', views.form_response, name='form_response'),
    path('responses/<int:response_id>/submit/', views.submit_form_response, name='submit_form_response'),
    
    # Form results management URLs
    path('courses/<int:course_id>/forms/<int:form_id>/results/', views.form_results, name='form_results'),
    path('courses/<int:course_id>/forms/<int:form_id>/member/<int:member_id>/', views.member_feedback, name='member_feedback'),
    path('responses/<int:response_id>/edit/', views.edit_response, name='edit_response'),
    path('forms/<int:form_id>/publish/', views.publish_results, name='publish_results'),
    
    # Form submission for managing teams in courses
    path("courses/<int:course_id>/teams/create/", views.create_team, name="create_team"),
    path("teams/<int:team_id>/edit/", views.edit_team, name="edit_team"),
    path('form/<int:course_id>/<int:form_id>/results/<int:member_id>/', views.member_feedback, name='member_feedback'),
    path('update-selected-course/', views.update_selected_course, name='update_selected_course'),
] 