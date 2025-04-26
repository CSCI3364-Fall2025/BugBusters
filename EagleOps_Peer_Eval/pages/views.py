from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from django.core.exceptions import PermissionDenied
from django.conf import settings
from .models import Team, Course, FormTemplate, Question, Form, FormResponse, Answer, UserProfile
from .utils import calculate_team_scores, get_member_feedback
import json
from django.contrib.auth import logout
from django.db.utils import IntegrityError
from django.contrib import messages
from .forms import TeamForm
from datetime import timedelta
from django.core.mail import send_mail

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

def signin(request):
    """View for redirecting to login page"""
    # This view is mainly for explicitly naming the signin URL
    # The actual authentication is handled by allauth
    return redirect('account_login')

def signout(request):
    """View for signing out users"""
    logout(request)
    return redirect('home')

from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

@login_required
def todo_view(request):
    """Student To-Do Page: Select course, join courses, and view forms organized by status."""
    user_profile = request.user.userprofile
    join_error_message = None
    join_success_message = None
    
    # Handle join course form submission
    if request.method == 'POST' and 'join_code' in request.POST:
        join_code = request.POST.get('join_code', '').strip().upper()
        if not join_code:
            join_error_message = 'Please enter a course join code'
        else:
            try:
                course = Course.objects.get(course_join_code=join_code)
                if course.students.filter(id=user_profile.id).exists():
                    join_error_message = f'You are already enrolled in {course.name}'
                else:
                    course.students.add(user_profile)
                    join_success_message = f'Successfully joined {course.name}'
            except Course.DoesNotExist:
                join_error_message = 'Invalid course code. Please check and try again.'

    # Get all relevant courses
    instructor_courses = Course.objects.filter(instructors=user_profile)
    team_courses = Course.objects.filter(teams__members=user_profile)
    enrolled_courses = Course.objects.filter(students=user_profile)
    course_list = (instructor_courses | team_courses | enrolled_courses).distinct().order_by('name')

    # Select course from session or default
    selected_course_id = request.session.get('selected_course_id')
    selected_course = None
    if selected_course_id:
        selected_course = course_list.filter(id=selected_course_id).first()
    if not selected_course:
        selected_course = course_list.first()
        if selected_course:
            request.session['selected_course_id'] = selected_course.id

    now = timezone.now()
    course_data = []

    if selected_course:
        user_teams = selected_course.teams.filter(members=user_profile)

        for team in user_teams:
            forms = Form.objects.filter(course=selected_course, teams=team).exclude(status='draft').order_by('-created_at')
            active_forms = []
            scheduled_forms = []
            closed_forms = []

            for form in forms:
                if now < form.publication_date:
                    live_status = 'scheduled'
                elif form.publication_date <= now < form.closing_date:
                    live_status = 'active'
                else:
                    live_status = 'closed'

                is_urgent = (
                    live_status == 'active' and
                    (form.closing_date - now) <= timedelta(hours=24)
                )
                form_data = {
                    'id': form.id,
                    'title': form.title,
                    'publication_date': form.publication_date,
                    'closing_date': form.closing_date,
                    'live_status': live_status,
                    'is_urgent': is_urgent,
                    'course_id': selected_course.id,
                    'time_left': str(form.closing_date - now).split('.')[0] if live_status == 'active' else '',
                }

                if live_status == 'active':
                    active_forms.append(form_data)
                elif live_status == 'scheduled':
                    scheduled_forms.append(form_data)
                elif live_status == 'closed':
                    closed_forms.append(form_data)

            course_data.append({
                'team': team,
                'course_name': selected_course.name,
                'course_code': selected_course.code,
                'active_forms': active_forms,
                'scheduled_forms': scheduled_forms,
                'closed_forms': closed_forms,
            })

    has_active_forms = any(item['active_forms'] for item in course_data)
    has_scheduled_forms = any(item['scheduled_forms'] for item in course_data)
    has_closed_forms = any(item['closed_forms'] for item in course_data)

    context = {
        'course_data': course_data,
        'join_error_message': join_error_message,
        'join_success_message': join_success_message,
        'selected_course': selected_course,
        'has_active_forms': has_active_forms,
        'has_scheduled_forms': has_scheduled_forms,
        'has_closed_forms': has_closed_forms,
    }

    return render(request, "to_do.html", context)

@login_required
def teams(request):
    user = request.user.userprofile

    # Get the selected course from session
    selected_course_id = request.session.get('selected_course_id')
    selected_course = None
    
    if selected_course_id:
        try:
            selected_course = Course.objects.get(id=selected_course_id)
        except Course.DoesNotExist:
            pass

    if user.admin:
        # Admins see all teams
        if selected_course:
            teams = Team.objects.prefetch_related('members__user').filter(course=selected_course)
        else:
            teams = Team.objects.prefetch_related('members__user').all()
        courses = Course.objects.all()
    else:
        # Non-admins see only their team(s)
        if selected_course:
            teams = Team.objects.prefetch_related('members__user').filter(
                members=user,
                course=selected_course
            )
        else:
            teams = Team.objects.prefetch_related('members__user').filter(members=user)
    
    return render(request, 'teams.html', {
        'teams': teams,
        'selected_course': selected_course
    })

@login_required
def courses(request):
    """
    View for displaying all courses a user has access to.
    If the user is an admin, they see all courses.
    Otherwise, they only see courses they are instructors for or are in teams enrolled in the course.
    """
    user_profile = request.user.userprofile
    
    if user_profile.admin:
        # Admins see all courses
        course_list = Course.objects.all().order_by('name')
    else:
        # Get courses where user is an instructor
        instructor_courses = Course.objects.filter(instructors=user_profile)
        
        # Get courses where user is in a team
        team_courses = Course.objects.filter(teams__members=user_profile)
        
        # Get courses where user is directly enrolled
        enrolled_courses = Course.objects.filter(students=user_profile)
        
        # Combine the querysets and remove duplicates
        course_list = (instructor_courses | team_courses | enrolled_courses).distinct().order_by('name')
    
    # For non-admin users, attach the teams they belong to for each course
    if not user_profile.admin:
        for course in course_list:
            course.user_teams = course.teams.filter(members=user_profile)
    
    context = {
        'courses': course_list,
        'is_admin': user_profile.admin,
    }
    
    return render(request, 'courses.html', context)

@login_required
def join_course(request):
    """View for students to join a course using a join code"""
    user_profile = request.user.userprofile
    error_message = None
    success_message = None
    
    if request.method == 'POST':
        join_code = request.POST.get('join_code', '').strip().upper()
        
        if not join_code:
            error_message = 'Please enter a course join code'
        else:
            try:
                course = Course.objects.get(course_join_code=join_code)
                
                # Check if already enrolled
                if course.students.filter(id=user_profile.id).exists():
                    error_message = f'You are already enrolled in {course.name}'
                else:
                    # Add student to course
                    course.students.add(user_profile)
                    success_message = f'Successfully joined {course.name}'
            except Course.DoesNotExist:
                error_message = 'Invalid course code. Please check and try again.'
    
    # Get courses where user is enrolled
    enrolled_courses = Course.objects.filter(students=user_profile)
    
    context = {
        'error_message': error_message,
        'success_message': success_message,
        'enrolled_courses': enrolled_courses
    }
    
    return render(request, 'join_course.html', context)

@login_required
def course_detail(request, course_id):
    """
    View for displaying course details including form templates, forms, and teams.
    """
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return redirect('courses')
    
    user_profile = request.user.userprofile
    
    # Get all teams for this course
    course_teams = course.teams.all()
    
    # Check if user has access to this course
    is_team_member = course_teams.filter(members=user_profile).exists()
    is_instructor = course.instructors.filter(id=user_profile.id).exists()
    is_student = course.students.filter(id=user_profile.id).exists()
    
    if not user_profile.admin and not is_instructor and not is_team_member and not is_student:
        return redirect('courses')
    
    # Get form templates for this course
    templates = FormTemplate.objects.filter(course=course).order_by('-created_at')
    
    # Get forms for this course
    forms = Form.objects.filter(course=course).order_by('-created_at')
    
    # Find teams the user is a member of
    user_teams = course_teams.filter(members=user_profile)
    
    # Get all students in the course
    enrolled_students = course.students.all().select_related('user').order_by('last_name', 'first_name')
    
    # Get all students that are members of any team in this course but might not be directly enrolled
    team_members = UserProfile.objects.filter(teams__course=course).select_related('user').distinct()
    
    # Combine both querysets using union to avoid the "Cannot combine a unique query with a non-unique query" error
    all_students = enrolled_students.union(team_members).order_by('last_name', 'first_name')
    
    context = {
        'course': course,
        'templates': templates,
        'forms': forms,
        'teams': course_teams,
        'user_teams': user_teams,
        'enrolled_students': enrolled_students,
        'is_instructor': is_instructor,
        'is_admin': user_profile.admin,
    }
    
    return render(request, 'course_detail.html', context)

@login_required
def template_create_edit(request, course_id, template_id=None):
    """
    View for creating or editing a form template
    Handles both AJAX requests and regular form submissions
    """
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can create/edit templates
    if not user.admin:
        raise PermissionDenied
    
    template = None
    error_message = None
    
    # Get existing template if editing
    if template_id:
        template = get_object_or_404(FormTemplate, id=template_id, course=course)
        
    if request.method == 'POST':
        try:
            # Determine if this is an AJAX request or regular form submit
            is_ajax = request.headers.get('Content-Type') == 'application/json'
            
            # Check if this is a preview request
            is_preview = request.GET.get('preview') == '1'
            
            # Extract data based on request type
            if is_ajax:
                # Parse JSON data for AJAX requests
                data = json.loads(request.body)
                title = data.get('title', '')
                description = data.get('description', '')
                questions = data.get('questions', [])
                save_exit = data.get('save_exit', False)
            else:
                # Parse form data for regular submissions
                title = request.POST.get('template-title', '')
                description = request.POST.get('template-description', '')
                save_exit = request.POST.get('save-exit') == '1'
                
                # Parse questions JSON from form data
                questions_json = request.POST.get('questions-data', '[]')
                try:
                    questions = json.loads(questions_json)
                except json.JSONDecodeError:
                    questions = []
            
            # Validate required fields
            if not title:
                error_message = 'Title is required'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': error_message}, status=400)
                else:
                    # For form submissions, render template with error
                    context = {
                        'course': course,
                        'template': template,
                        'questions': template.questions.all() if template else [],
                        'is_edit': template is not None,
                        'error_message': error_message
                    }
                    return render(request, 'template_edit.html', context)
            
            # Save or update the template
            if template:
                # Update existing template
                template.title = title
                template.description = description
                template.save()
                
                # Delete questions not in the updated list (keeping only those with IDs in the new list)
                question_ids = [q.get('id') for q in questions if q.get('id') and not str(q.get('id')).startswith('temp_')]
                template.questions.exclude(id__in=question_ids).delete()
            else:
                # Create new template
                template = FormTemplate.objects.create(
                    title=title,
                    description=description,
                    course=course,
                    created_by=user
                )
            
            # Process each question from the request
            for order, question_data in enumerate(questions):
                question_id = question_data.get('id')
                text = question_data.get('text', '')
                question_type = question_data.get('type', Question.LIKERT_SCALE)
                
                # Skip temporary IDs (client-side only IDs)
                if question_id and str(question_id).startswith('temp_'):
                    question_id = None
                
                if question_id and not str(question_id).startswith('temp_'):
                    try:
                        # Update existing question
                        Question.objects.filter(id=question_id, template=template).update(
                            text=text,
                            question_type=question_type,
                            order=order
                        )
                    except Exception as e:
                        print(f"Error updating question {question_id}: {str(e)}")
                else:
                    try:
                        # Create new question
                        Question.objects.create(
                            template=template,
                            text=text,
                            question_type=question_type,
                            order=order
                        )
                    except Exception as e:
                        print(f"Error creating question: {str(e)}")
            
            # Return response based on request type and action
            if is_ajax:
                return JsonResponse({'status': 'success', 'template_id': template.id})
            else:
                # Redirect based on save_exit flag or preview flag
                if is_preview:
                    return redirect('template_preview', course_id=course_id, template_id=template.id)
                elif save_exit:
                    return redirect('course_detail', course_id=course_id)
                else:
                    return redirect('template_edit', course_id=course_id, template_id=template.id)
                
        except Exception as e:
            # Handle unexpected errors
            print(f"Error in template_create_edit: {str(e)}")
            error_message = f"An error occurred: {str(e)}"
            
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'status': 'error', 'message': error_message}, status=500)
    
    # Display the create/edit form (for GET requests or after errors)
    context = {
        'course': course,
        'template': template,
        'questions': template.questions.all() if template else [],
        'is_edit': template is not None,
        'error_message': error_message
    }
    
    return render(request, 'template_edit.html', context)

@login_required
def template_duplicate(request, course_id, template_id):
    """Duplicate a template"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can duplicate templates
    if not user.admin:
        raise PermissionDenied
    
    template = get_object_or_404(FormTemplate, id=template_id, course=course)
    new_template = template.duplicate()
    
    return redirect('template_edit', course_id=course_id, template_id=new_template.id)

@login_required
@require_POST
def template_delete(request, course_id, template_id):
    """Delete a template"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can delete templates
    if not user.admin:
        raise PermissionDenied
    
    template = get_object_or_404(FormTemplate, id=template_id, course=course)
    template.delete()
    
    return redirect('course_detail', course_id=course_id)

from django.utils import timezone
from datetime import datetime

def form_create_edit(request, course_id, form_id=None):
    """View for creating or editing a form"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can create/edit forms
    if not user.admin:
        raise PermissionDenied
    
    form = None
    if form_id:
        form = get_object_or_404(Form, id=form_id, course=course)
    
    templates = FormTemplate.objects.filter(course=course)
    teams = Team.objects.filter(course=course)
    
    if request.method == 'POST':
        try:
            # Handle save action
            data = json.loads(request.body)
            print(f"Received POST data: {data}")
            
            title = data.get('title', '')
            template_id = data.get('template_id')
            publication_date = data.get('publication_date')
            closing_date = data.get('closing_date')
            team_ids = data.get('team_ids', [])
            self_assessment = data.get('self_assessment', False)
            
            # Convert publication_date and closing_date to timezone-aware datetime
            publication_date = timezone.make_aware(datetime.strptime(publication_date, '%Y-%m-%dT%H:%M'))
            closing_date = timezone.make_aware(datetime.strptime(closing_date, '%Y-%m-%dT%H:%M'))
            
            # Validate required fields
            if not title:
                return JsonResponse({'status': 'error', 'message': 'Form title is required'}, status=400)
            
            if not template_id:
                return JsonResponse({'status': 'error', 'message': 'Template selection is required'}, status=400)
            
            if not publication_date:
                return JsonResponse({'status': 'error', 'message': 'Publication date is required'}, status=400)
                
            if not closing_date:
                return JsonResponse({'status': 'error', 'message': 'Closing date is required'}, status=400)
            
            if not team_ids:
                return JsonResponse({'status': 'error', 'message': 'At least one team must be selected'}, status=400)
            
            # Make sure template exists
            try:
                template = FormTemplate.objects.get(id=template_id, course=course)
            except FormTemplate.DoesNotExist:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Template with ID {template_id} does not exist for this course'
                }, status=404)
            
            # Convert team_ids to integers if they're strings
            team_ids = [int(team_id) for team_id in team_ids]
            
            # Verify teams exist
            teams_to_assign = Team.objects.filter(id__in=team_ids)
            if len(teams_to_assign) != len(team_ids):
                missing = set(team_ids) - set(team.id for team in teams_to_assign)
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Some teams do not exist: {missing}'
                }, status=400)
            
            if form:
                # Update existing form
                print(f"Updating existing form: {form.id}")
                form.title = title
                form.template = template
                form.publication_date = publication_date
                form.closing_date = closing_date
                form.self_assessment = self_assessment
                form.save()
                
                # Update teams
                form.teams.set(teams_to_assign)
                
                return JsonResponse({'status': 'success', 'form_id': form.id})
            else:
                # Create new form
                print(f"Creating new form with template: {template.id}")
                form = Form.objects.create(
                    title=title,
                    template=template,
                    course=course,
                    created_by=user,
                    publication_date=publication_date,
                    closing_date=closing_date,
                    self_assessment=self_assessment
                )
                
                # Now we can set the teams
                form.teams.add(*teams_to_assign)
                
                return JsonResponse({'status': 'success', 'form_id': form.id})
        except Exception as e:
            # Handle unexpected errors
            print(f"Error in form_create_edit: {str(e)}")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
            error_message = f"An error occurred: {str(e)}"
            return JsonResponse({'status': 'error', 'message': error_message}, status=500)
    
    # Display the create/edit form
    context = {
        'course': course,
        'form': form,
        'templates': templates,
        'teams': teams,
        'selected_teams': [t.id for t in form.teams.all()] if form else [],
        'is_edit': form is not None
    }
    
    return render(request, 'form_edit.html', context)

@login_required
def form_open(request, course_id, form_id):
    if request.method == 'POST':
        form = get_object_or_404(Form, id=form_id, course_id=course_id)
        
        # If form is in draft status, check publication date to determine status
        if form.status == 'draft':
            now = timezone.now()
            if now >= form.publication_date:
                form.status = 'active'
                messages.success(request, f"Form '{form.title}' is now active.")
            else:
                form.status = 'scheduled'
                messages.success(request, f"Form '{form.title}' has been scheduled to open.")
            form.save(force_status=True)  # Ensure the status is updated with force_status
        
        # If form is closed, change to active
        elif form.status == 'closed':
            form.status = 'active'
            form.save(force_status=True)  # Ensure the status is updated with force_status
            messages.success(request, f"Form '{form.title}' has been reopened.")
        
        else:
            messages.warning(request, f"Form '{form.title}' cannot be opened in its current state.")
    
    return redirect('course_detail', course_id=course_id)

@login_required
def form_close(request, course_id, form_id):
    print("Closing form")
    if request.method == 'POST':
        form = get_object_or_404(Form, id=form_id, course_id=course_id)
        # Only allow closing if form is scheduled or active
        if form.status in [Form.SCHEDULED, Form.ACTIVE]:
            form.status = Form.CLOSED
            print(form.status)
            form.save(force_status=True)
            messages.success(request, f"Form '{form.title}' has been closed. Results can now be published.")
        else:
            messages.warning(request, f"Form '{form.title}' cannot be closed in its current state.")
    return redirect('course_detail', course_id=course_id)

@login_required
@require_POST
def form_delete(request, course_id, form_id):
    """Delete a form"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can delete forms
    if not user.admin:
        raise PermissionDenied
    
    form = get_object_or_404(Form, id=form_id, course=course)
    form.delete()
    
    return redirect('course_detail', course_id=course_id)

@login_required
def profile(request):
    """
    View for displaying and updating user profile information.
    """
    user_profile = request.user.userprofile
    
    if request.method == 'POST':
        # Extract form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Update user profile
        if first_name is not None:
            user_profile.first_name = first_name
        if last_name is not None:
            user_profile.last_name = last_name
        
        user_profile.save()
        
        # Redirect to profile page to show updated info
        return redirect('profile')
    
    # Get teams the user is a member of
    teams = Team.objects.filter(members=user_profile)
    
    # Get courses the user is enrolled in
    courses = Course.objects.filter(teams__members=user_profile).distinct()
    
    context = {
        'user_profile': user_profile,
        'teams': teams,
        'courses': courses,
        'is_admin': user_profile.admin,
    }
    
    return render(request, 'profile.html', context)

@login_required
def create_course(request):
    """
    View for creating a new course. Only admins can create courses.
    """
    user_profile = request.user.userprofile
    
    # Only admins can create courses
    if not user_profile.admin:
        return redirect('courses')
    
    error_message = None
    
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description', '')
        
        # Create new course
        if name and code:
            try:
                course = Course.objects.create(
                    name=name,
                    code=code,
                    description=description
                )
                
                # Add current user as instructor
                course.instructors.add(user_profile)
                
                return redirect('course_detail', course_id=course.id)
            except IntegrityError:
                # Handle the case where course code already exists
                error_message = f"Course code '{code}' already exists. Please choose a different code."
    
    return render(request, 'course_edit.html', {
        'is_admin': user_profile.admin,
        'error_message': error_message
    })

@login_required
def edit_course(request, course_id):
    """
    View for editing an existing course. Only admins or instructors can edit.
    """
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return redirect('courses')
    
    user_profile = request.user.userprofile
    
    # Check if user has permission to edit
    if not user_profile.admin and not course.instructors.filter(id=user_profile.id).exists():
        return redirect('courses')
    
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description', '')
        
        # Update course
        if name and code:
            course.name = name
            course.code = code
            course.description = description
            course.save()
            
            return redirect('course_detail', course_id=course.id)
    
    context = {
        'course': course,
        'is_admin': user_profile.admin,
    }
    
    return render(request, 'course_edit.html', context)

@login_required
def delete_course(request, course_id):
    """
    View for deleting an existing course. Only admins can delete courses.
    """
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return redirect('courses')
    
    user_profile = request.user.userprofile

    # Only admins are allowed to delete a course.
    if not user_profile.admin:
        return redirect('courses')
    
    if request.method == 'POST':
        course.delete()
        return redirect('courses')
    
    # Optionally, render a confirmation page if GET request is used.
    return render(request, 'confirm_delete_course.html', {'course': course})

@login_required
def create_team(request, course_id):
    """View for creating a new team within a course"""
    user_profile = request.user.userprofile
    
    # Get the course
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can create teams
    if not user_profile.admin:
        return redirect('course_detail', course_id=course_id)
    
    # Get all potential team members (students enrolled in the course and instructors)
    course_students = course.students.all()
    course_instructors = course.instructors.all()
    available_users = (course_students | course_instructors).exclude(id=user_profile.id).distinct()
    
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            # Create the team without saving to DB yet
            team = form.save(commit=False)
            team.course = course  # Assign the team to the course
            team.save()  # Save team with course relationship
            
            # Now form.save_m2m() is needed since we used commit=False
            form.save_m2m()
            
            # Get the selected user IDs and update members
            selected_user_ids = request.POST.getlist('users')
            selected_users = UserProfile.objects.filter(id__in=selected_user_ids)
            team.members.set(selected_users)
            
            # Redirect back to the course detail page
            return redirect('course_detail', course_id=course_id)
    else:
        form = TeamForm()
    
    context = {
        'form': form,
        'user_profiles': available_users,
        'course': course
    }
    return render(request, 'create_team.html', context)

@login_required
def edit_team(request, team_id):
    """View for editing an existing team"""
    user_profile = request.user.userprofile
    team = get_object_or_404(Team, id=team_id)
    course = team.course  # Get the course directly from the team
    
    # Only admins can edit teams
    if not user_profile.admin:
        return redirect('course_detail', course_id=course.id)
    
    # Get all potential team members (students enrolled in the course and instructors)
    course_students = course.students.all()
    course_instructors = course.instructors.all()
    available_users = (course_students | course_instructors).exclude(id=user_profile.id).distinct()
    
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            # Save the team - no need to set course as it's already set
            team = form.save()
            
            # Get the selected user IDs and update members
            selected_user_ids = request.POST.getlist('users')
            selected_users = UserProfile.objects.filter(id__in=selected_user_ids)
            team.members.set(selected_users)
            
            # Redirect back to the course detail page
            return redirect('course_detail', course_id=course.id)
    else:
        form = TeamForm(instance=team)
    
    context = {
        'form': form,
        'team': team,
        'user_profiles': available_users,
        'selected_user_ids': [user.id for user in team.members.all()],
        'course': course
    }
    
    return render(request, 'edit_team.html', context)

@login_required
def template_preview(request, course_id, template_id):
    """Preview a form template"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    template = get_object_or_404(FormTemplate, id=template_id, course=course)
    
    # Only admins can preview templates
    if not user.admin:
        raise PermissionDenied
    
    context = {
        'course': course,
        'template': template,
        'questions': template.questions.all().order_by('order'),
        'preview_mode': True,
    }
    
    return render(request, 'template_preview.html', context)

@login_required
def form_preview(request, course_id, form_id):
    """Preview a form instance"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    form = get_object_or_404(Form, id=form_id, course=course)
    
    # Only admins can preview forms
    if not user.admin:
        raise PermissionDenied
    
    # Get all questions from the template
    questions = form.template.questions.all().order_by('order')
    
    context = {
        'course': course,
        'form': form,
        'questions': questions,
        'preview_mode': True,
    }
    
    return render(request, 'form_preview.html', context)

@login_required
def form_response(request, course_id, form_id, evaluatee_id):
    """View for filling out a form response for a specific evaluatee"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    form = get_object_or_404(Form, id=form_id, course=course)
    evaluatee = get_object_or_404(UserProfile, id=evaluatee_id)
    
    # Check if this form is active
    if form.status not in [Form.ACTIVE, Form.SCHEDULED]:
        messages.error(request, "This form is not currently active.")
        return redirect('form_evaluations', course_id=course.id, form_id=form.id)
    
    # Check if user is in a team assigned to this form
    user_teams = form.teams.filter(members=user)
    if not user_teams.exists():
        messages.error(request, "You are not assigned to this form.")
        return redirect('form_evaluations', course_id=course.id, form_id=form.id)
    
    # Check if evaluatee is in user's team
    evaluatee_teams = form.teams.filter(members=evaluatee)
    if not evaluatee_teams.filter(pk__in=user_teams.values_list('pk', flat=True)).exists():
        messages.error(request, "You cannot evaluate this person.")
        return redirect('form_evaluations', course_id=course.id, form_id=form.id)
    
    # Check if self-assessment is allowed, or if not evaluating self
    if not form.self_assessment and user.id == evaluatee.id:
        messages.error(request, "Self-assessment is not enabled for this form.")
        return redirect('form_evaluations', course_id=course.id, form_id=form.id)
    
    # Get or create form response
    form_response, created = FormResponse.objects.get_or_create(
        form=form,
        evaluator=user,
        evaluatee=evaluatee
    )
    
    # Check if form is closed (past deadline)
    if timezone.now() > form.closing_date and not form_response.submitted:
        messages.warning(request, "The deadline for this form has passed. New evaluations cannot be submitted.")
        return redirect('form_evaluations', course_id=course.id, form_id=form.id)
    
    # If already submitted and past deadline, only allow viewing
    readonly = timezone.now() > form.closing_date and form_response.submitted
    
    # Get questions from template
    questions = form.template.questions.all().order_by('order')
    
    # Get existing answers to pre-fill the form
    existing_answers = {}
    for answer in form_response.answers.all():
        if answer.question.question_type == Question.LIKERT_SCALE:
            existing_answers[answer.question.id] = answer.likert_answer
        else:
            existing_answers[answer.question.id] = answer.text_answer
    
    context = {
        'course': course,
        'form': form,
        'evaluatee': evaluatee,
        'form_response': form_response,
        'questions': questions,
        'existing_answers': existing_answers,
        'readonly': readonly,
    }
    
    return render(request, 'form_response.html', context)

@login_required
@require_POST
def submit_form_response(request, response_id):
    """Handle submission of a completed form response"""
    form_response = get_object_or_404(FormResponse, id=response_id, evaluator=request.user.userprofile)
    
    # Check if form is still active
    form = form_response.form
    if form.status != Form.ACTIVE:
        messages.error(request, "This form is no longer active.")
        return redirect('form_evaluations', course_id=form.course.id, form_id=form.id)
    
    # Check if form closing date has passed
    if timezone.now() > form.closing_date:
        messages.error(request, "The deadline for this form has passed. Evaluations can no longer be submitted or edited.")
        return redirect('form_evaluations', course_id=form.course.id, form_id=form.id)
    
    # Process answers
    questions = form.template.questions.all()
    for question in questions:
        if question.question_type == Question.LIKERT_SCALE:
            likert_value = request.POST.get(f'likert_{question.id}')
            text_value = None
            
            # Validate likert value
            try:
                likert_value = int(likert_value)
                if likert_value < 1 or likert_value > 5:
                    messages.error(request, f"Invalid rating for question {question.text}")
                    return redirect('form_response', course_id=form.course.id, form_id=form.id, evaluatee_id=form_response.evaluatee.id)
            except (ValueError, TypeError):
                messages.error(request, f"Rating required for question {question.text}")
                return redirect('form_response', course_id=form.course.id, form_id=form.id, evaluatee_id=form_response.evaluatee.id)
        else:
            likert_value = None
            text_value = request.POST.get(f'text_{question.id}', '').strip()
            
            # Validate text answer
            if not text_value:
                messages.error(request, f"Response required for question {question.text}")
                return redirect('form_response', course_id=form.course.id, form_id=form.id, evaluatee_id=form_response.evaluatee.id)
        
        # Create or update answer
        answer, created = Answer.objects.update_or_create(
            response=form_response,
            question=question,
            defaults={
                'likert_answer': likert_value,
                'text_answer': text_value
            }
        )
    
    # Mark response as submitted if it hasn't been already
    was_already_submitted = form_response.submitted
    if not was_already_submitted:
        form_response.submit()
        messages.success(request, f"Your evaluation for {form_response.evaluatee.full_name} has been submitted.")
    else:
        # Just update the answers but keep the original submission date
        form_response.save()
        messages.success(request, f"Your evaluation for {form_response.evaluatee.full_name} has been updated.")
    
    # Redirect back to form evaluations page instead of todo
    return redirect('form_evaluations', course_id=form.course.id, form_id=form.id)

@login_required
def form_evaluations(request, course_id, form_id):
    """View to show all team members that need to be evaluated for a form"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    form = get_object_or_404(Form, id=form_id, course=course)
    
    # Check if user is in a team assigned to this form
    user_teams = form.teams.filter(members=user)
    if not user_teams.exists():
        messages.error(request, "You are not assigned to this form.")
        return redirect('todo')
    
    # Check if form is active
    if form.status not in [Form.ACTIVE, Form.SCHEDULED]:
        messages.error(request, "This form is not currently active.")
        return redirect('todo')
    
    # Get all team members that the user needs to evaluate
    evaluatees = []
    for team in user_teams:
        team_members = team.members.all()
        
        for member in team_members:
            # Skip if not self and self-assessment is not enabled
            if not form.self_assessment and member.id == user.id:
                continue
                
            # Check if response already exists
            response = FormResponse.objects.filter(
                form=form,
                evaluator=user,
                evaluatee=member
            ).first()
            
            evaluatees.append({
                'member': member,
                'response': response,
                'completed': response and response.submitted,
                'submission_date': response.submission_date if response and response.submitted else None
            })
    
    context = {
        'course': course,
        'form': form,
        'evaluatees': evaluatees,
    }
    
    return render(request, 'form_evaluations.html', context)

@login_required
def form_results(request, course_id, form_id):
    """View for professors to see and manage form results"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    form = get_object_or_404(Form, id=form_id, course=course)
    
    # Check if user is an instructor or admin
    if not user.admin and not course.instructors.filter(id=user.id).exists():
        messages.error(request, "You do not have permission to view these results.")
        return redirect('course_detail', course_id=course_id)
    
    # Get all teams assigned to this form
    teams = form.teams.all()
    
    # Calculate scores for each team
    team_scores = {}
    for team in teams:
        team_scores[team] = calculate_team_scores(form, team)
    
    # Get selected member if specified
    selected_member_id = request.GET.get('member')
    selected_member = None
    member_feedback = None
    
    if selected_member_id:
        try:
            selected_member = UserProfile.objects.get(id=selected_member_id)
            member_feedback = get_member_feedback(form, selected_member)
        except UserProfile.DoesNotExist:
            messages.error(request, "Selected member not found.")
    
    context = {
        'course': course,
        'form': form,
        'teams': teams,
        'team_scores': team_scores,
        'is_published': form.status == Form.PUBLISHED,
        'selected_member': selected_member,
        'member_feedback': member_feedback
    }
    
    return render(request, 'form_results.html', context)

@login_required
@require_POST
def edit_response(request, response_id):
    """View for professors to edit form responses"""
    response = get_object_or_404(FormResponse, id=response_id)
    form = response.form
    course = form.course
    user = request.user.userprofile
    
    # Check if user is an instructor or admin
    if not user.admin and not course.instructors.filter(id=user.id).exists():
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get the answer to edit
    answer_id = request.POST.get('answer_id')
    answer = get_object_or_404(Answer, id=answer_id, response=response)
    
    # Update the answer
    if answer.question.question_type == Question.OPEN_ENDED:
        answer.text_answer = request.POST.get('text_answer', '')
    else:
        answer.likert_answer = request.POST.get('likert_answer')
    
    answer.save()
    
    return JsonResponse({'success': True})

@login_required
@require_POST
def publish_results(request, form_id):
    """Publish form results for students to view."""
    form = get_object_or_404(Form, id=form_id)
    course = form.course
    user = request.user.userprofile

    # Check permissions
    if not (user.admin or course.instructors.filter(id=user.id).exists()):
        error_msg = "You do not have permission to publish results."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect('course_detail', course_id=course.id)

    # Check if form is already published
    if form.status == Form.PUBLISHED:
        error_msg = "Results are already published."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=400)
        messages.warning(request, error_msg)
        return redirect('form_results', course_id=course.id, form_id=form.id)

    # Check if form is closed
    if form.status != Form.CLOSED:
        error_msg = "Cannot publish results while form is not closed."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('form_results', course_id=course.id, form_id=form.id)

    try:
        # Update form status to published
        form.status = Form.PUBLISHED
        form.save(force_status=True)  # force_status to prevent automatic status updates
        
        success_msg = "Results have been published successfully."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': success_msg})
        
        messages.success(request, success_msg)
        return redirect('form_results', course_id=course.id, form_id=form.id)

    except Exception as e:
        error_msg = f"Error publishing results: {str(e)}"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=500)
        messages.error(request, error_msg)
        return redirect('form_results', course_id=course.id, form_id=form.id)

@login_required
@require_POST
def form_unpublish(request, course_id, form_id):
    """Unpublish a form to hide results again."""
    form = get_object_or_404(Form, id=form_id)
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)

    if not (user.admin or course.instructors.filter(id=user.id).exists()):
        messages.error(request, "You don't have permission to unpublish this form.")
        return redirect('course_detail', course_id=course_id)

    try:
        form.status = Form.CLOSED
        form.save(force_status=True)
        messages.success(request, f"'{form.title}' has been unpublished.")
    except Exception as e:
        messages.error(request, f"Error unpublishing form: {str(e)}")

    return redirect('course_detail', course_id=course_id)

@login_required
def member_feedback(request, course_id, form_id, member_id):
    """Moderate open-ended feedback for a team member on a specific form."""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    form = get_object_or_404(Form, id=form_id, course=course)
    member = get_object_or_404(UserProfile, id=member_id)

    if not (user.admin or course.instructors.filter(id=user.id).exists()):
        messages.error(request, "You do not have permission to moderate feedback.")
        return redirect('course_detail', course_id=course_id)

    feedback_data = get_member_feedback(form, member)

    if request.method == 'POST':
        # Save updated feedback responses
        updated = False
        for response in feedback_data['text_responses']:
            for answer in response['answers']:
                field_key = f"answer_{answer.id}"
                if field_key in request.POST:
                    new_text = request.POST.get(field_key, "").strip()
                    if new_text != answer.text_answer:
                        answer.text_answer = new_text
                        answer.save()
                        updated = True

        if updated:
            messages.success(request, "Feedback has been updated successfully.")
        else:
            messages.info(request, "No changes were made.")
        return redirect('member_feedback', course_id=course_id, form_id=form_id, member_id=member_id)

    context = {
        'course': course,
        'form': form,
        'member': member,
        'member_feedback': feedback_data
    }
    return render(request, 'member_feedback.html', context)

@require_POST
def update_selected_course(request):
    """
    View to update the selected course in the user's session.
    """
    try:
        data = json.loads(request.body)
        course_id = data.get('course_id')
        
        if not course_id:
            return JsonResponse({'error': 'No course ID provided'}, status=400)
            
        # Verify the course exists and user has access to it
        user_profile = request.user.userprofile
        if user_profile.admin:
            course = Course.objects.get(id=course_id)
        else:
            # Get courses where user is an instructor
            instructor_courses = Course.objects.filter(instructors=user_profile)
            
            # Get courses where user is in a team
            team_courses = Course.objects.filter(teams__members=user_profile)
            
            # Get courses where user is directly enrolled
            enrolled_courses = Course.objects.filter(students=user_profile)
            
            # Combine the querysets and remove duplicates
            available_courses = (instructor_courses | team_courses | enrolled_courses).distinct()
            
            try:
                course = available_courses.get(id=course_id)
            except Course.DoesNotExist:
                return JsonResponse({'error': 'Course not found or access denied'}, status=403)
        
        # Update the session
        request.session['selected_course_id'] = course.id
        return JsonResponse({'success': True})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def performance_view(request, course_id):
    """
    View to show performance metrics and assessment results.
    Admins and instructors can see the performance of all members.
    Students can see their own performance in the course.
    """
    course = get_object_or_404(Course, id=course_id)
    user_profile = request.user.userprofile
    
    # Initialize performance data structure
    performance_data = []
    
    # If the user is an admin or instructor, they can view all team members' performance
    if user_profile.admin or user_profile in course.instructors.all():
        # Get all teams in the course
        teams = Team.objects.filter(course=course)
        
        # Get all forms for this course
        forms = Form.objects.filter(course=course, status=Form.PUBLISHED)
        
        # Prepare performance data for each team and its members
        for team in teams:
            team_data = {
                'team': team,
                'members': [],
            }
            
            for member in team.members.all():
                member_data = {
                    'member': member,
                    'forms': [],
                    'average_score': 0,
                }
                
                total_score = 0
                form_count = 0
                
                for form in forms:
                    if form in team.assigned_forms.all():
                        # Get all responses for this member in this form
                        responses = FormResponse.objects.filter(
                            form=form,
                            evaluatee=member,
                            submitted=True
                        )
                        
                        if responses.exists():
                            form_score = 0
                            response_count = 0
                            open_responses = []
                            
                            for response in responses:
                                # Calculate average score for this response
                                likert_answers = Answer.objects.filter(
                                    response=response,
                                    question__question_type=Question.LIKERT_SCALE
                                )
                                
                                if likert_answers.exists():
                                    avg_score = sum(a.likert_answer for a in likert_answers) / len(likert_answers)
                                    form_score += avg_score
                                    response_count += 1
                                
                                # Get open-ended responses
                                text_answers = Answer.objects.filter(
                                    response=response,
                                    question__question_type=Question.OPEN_ENDED
                                )
                                for answer in text_answers:
                                    if answer.text_answer:
                                        open_responses.append(answer.text_answer)
                            
                            if response_count > 0:
                                form_score = form_score / response_count
                                total_score += form_score
                                form_count += 1
                                
                                # Calculate team average score
                                team_responses = FormResponse.objects.filter(
                                    form=form,
                                    evaluatee__in=team.members.all(),
                                    submitted=True
                                )
                                team_score = 0
                                team_response_count = 0
                                
                                for team_response in team_responses:
                                    team_likert_answers = Answer.objects.filter(
                                        response=team_response,
                                        question__question_type=Question.LIKERT_SCALE
                                    )
                                    if team_likert_answers.exists():
                                        team_avg = sum(a.likert_answer for a in team_likert_answers) / len(team_likert_answers)
                                        team_score += team_avg
                                        team_response_count += 1
                                
                                team_avg_score = team_score / team_response_count if team_response_count > 0 else 0
                                
                                member_data['forms'].append({
                                    'form': form,
                                    'score': round(form_score, 2),
                                    'team_score': round(team_avg_score, 2),
                                    'open_responses': open_responses[:3],  # Limit to 3 responses for preview
                                })
                
                if form_count > 0:
                    member_data['average_score'] = round(total_score / form_count, 2)
                
                team_data['members'].append(member_data)
            
            performance_data.append(team_data)
    
    # If the user is a student, show only their own performance
    else:
        student_data = {
            'member': user_profile,
            'forms': [],
            'average_score': 0,
        }

        # Get the forms for the course
        forms = Form.objects.filter(course=course, status=Form.PUBLISHED)

        total_score = 0
        form_count = 0

        for form in forms:
            # Get the student's responses for each form
            responses = FormResponse.objects.filter(
                form=form,
                evaluatee=request.user.userprofile,
                submitted=True
            )
            
            if responses.exists():
                form_score = 0
                response_count = 0
                open_responses = []
                
                for response in responses:
                    # Calculate average score for this response
                    likert_answers = Answer.objects.filter(
                        response=response,
                        question__question_type=Question.LIKERT_SCALE
                    )
                    
                    if likert_answers.exists():
                        avg_score = sum(a.likert_answer for a in likert_answers) / len(likert_answers)
                        form_score += avg_score
                        response_count += 1
                    
                    # Get open-ended responses
                    text_answers = Answer.objects.filter(
                        response=response,
                        question__question_type=Question.OPEN_ENDED
                    )
                    for answer in text_answers:
                        if answer.text_answer:
                            open_responses.append(answer.text_answer)
                
                if response_count > 0:
                    form_score = form_score / response_count
                    total_score += form_score
                    form_count += 1
                    
                    # Calculate team average score
                    team = form.teams.filter(members=user_profile).first()
                    if team:
                        team_responses = FormResponse.objects.filter(
                            form=form,
                            evaluatee__in=team.members.all(),
                            submitted=True
                        )
                        team_score = 0
                        team_response_count = 0
                        
                        for team_response in team_responses:
                            team_likert_answers = Answer.objects.filter(
                                response=team_response,
                                question__question_type=Question.LIKERT_SCALE
                            )
                            if team_likert_answers.exists():
                                team_avg = sum(a.likert_answer for a in team_likert_answers) / len(team_likert_answers)
                                team_score += team_avg
                                team_response_count += 1
                        
                        team_avg_score = team_score / team_response_count if team_response_count > 0 else 0
                    else:
                        team_avg_score = 0

                    student_data['forms'].append({
                        'form': form,
                        'score': round(form_score, 2),
                        'team_score': round(team_avg_score, 2),
                        'open_responses': open_responses[:3],  # Limit to 3 responses for preview
                    })
        
        if form_count > 0:
            student_data['average_score'] = round(total_score / form_count, 2)
        
        performance_data.append(student_data)
    
    context = {
        'course': course,
        'performance_data': performance_data,
    }
    
    return render(request, 'performance.html', context)

@login_required
def roster(request, course_id=None):
    """
    View for displaying a roster of all students in a course.
    Only admins can access this view.
    """
    user_profile = request.user.userprofile
    
    # Only admins can view roster
    if not user_profile.admin:
        messages.error(request, "Only administrators can access the roster page.")
        return redirect('courses')
    
    try:
        # Get the course - either from URL or from session
        if course_id:
            course = get_object_or_404(Course, id=course_id)
        else:
            # Get course from session (navbar dropdown)
            selected_course_id = request.session.get('selected_course_id')
            if not selected_course_id:
                messages.warning(request, "Please select a course from the dropdown first.")
                return redirect('courses')
            
            course = get_object_or_404(Course, id=selected_course_id)
        
        print(f"Processing roster for course: {course.name} (ID: {course.id})")
        
        # Get all enrolled students
        enrolled_students = course.students.all().select_related('user')
        print(f"Found {enrolled_students.count()} directly enrolled students")
        
        # Get all students that are members of any team in this course but might not be directly enrolled
        team_members = UserProfile.objects.filter(teams__course=course).select_related('user')
        print(f"Found {team_members.count()} team members")
        
        # Since we can't use union() directly due to the error, use a different approach
        # Create a set of user IDs and then fetch all those users
        enrolled_ids = set(enrolled_students.values_list('id', flat=True))
        team_member_ids = set(team_members.values_list('id', flat=True))
        all_student_ids = enrolled_ids.union(team_member_ids)
        
        # Fetch all students with these IDs in one query
        all_students = UserProfile.objects.filter(id__in=all_student_ids).select_related('user').order_by('last_name', 'first_name')
        print(f"Combined unique student count: {all_students.count()}")
        
        # Count stats
        student_count = all_students.count()
        team_count = course.teams.count()
        
        context = {
            'course': course,
            'students': all_students,
            'student_count': student_count,
            'team_count': team_count,
            'is_admin': user_profile.admin,
        }
        
        return render(request, 'roster.html', context)
    
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')
    except Exception as e:
        # Better error message and detailed logging
        error_message = str(e)
        print(f"Error in roster view: {error_message}")
        import traceback
        traceback.print_exc()  # Print full stack trace for debugging
        messages.error(request, f"An error occurred while loading the roster: {error_message}")
        return redirect('courses')

@login_required
def forms_dashboard(request):
    """
    Admin dashboard view showing all form templates and forms across all courses,
    categorized by their status.
    """
    user_profile = request.user.userprofile
    
    # Only admins can access this dashboard
    if not user_profile.admin:
        messages.error(request, "Only administrators can access the forms dashboard.")
        return redirect('courses')
    
    # Get the selected course from session
    selected_course_id = request.session.get('selected_course_id')
    selected_course = None
    
    if selected_course_id:
        try:
            selected_course = Course.objects.get(id=selected_course_id)
        except Course.DoesNotExist:
            selected_course = None
    
    # Define form statuses for categorization
    active_status = Form.ACTIVE
    scheduled_status = Form.SCHEDULED
    closed_status = Form.CLOSED
    published_status = Form.PUBLISHED
    
    # If a specific course is selected, filter by that course
    if selected_course:
        # Get templates for the selected course
        templates = FormTemplate.objects.filter(course=selected_course).order_by('-created_at')
        
        # Get forms for the selected course, categorized by status
        active_forms = Form.objects.filter(course=selected_course, status=active_status).order_by('closing_date')
        scheduled_forms = Form.objects.filter(course=selected_course, status=scheduled_status).order_by('publication_date')
        closed_pending_forms = Form.objects.filter(course=selected_course, status=closed_status).order_by('-closing_date')
        published_forms = Form.objects.filter(course=selected_course, status=published_status).order_by('-closing_date')
        
        # Get courses for the dropdown
        courses = Course.objects.all().order_by('name')
    else:
        # Get all templates across all courses
        templates = FormTemplate.objects.all().order_by('-created_at')
        
        # Get all forms across all courses, categorized by status
        active_forms = Form.objects.filter(status=active_status).order_by('closing_date')
        scheduled_forms = Form.objects.filter(status=scheduled_status).order_by('publication_date')
        closed_pending_forms = Form.objects.filter(status=closed_status).order_by('-closing_date')
        published_forms = Form.objects.filter(status=published_status).order_by('-closing_date')
        
        # Get courses for the dropdown
        courses = Course.objects.all().order_by('name')
    
    # Mark urgent forms (due within 24 hours)
    now = timezone.now()
    for form in active_forms:
        form.is_urgent = form.closing_date - now <= timedelta(hours=24)
    
    context = {
        'selected_course': selected_course,
        'courses': courses,
        'templates': templates,
        'active_forms': active_forms,
        'scheduled_forms': scheduled_forms,
        'closed_pending_forms': closed_pending_forms,
        'published_forms': published_forms,
        'available_courses': courses,  # For the navbar course selector
    }
    
    return render(request, 'forms_dashboard.html', context)

def invite_students(request, course_id):
    if request.method == 'POST':
        if not request.user.userprofile.admin:
            messages.error(request, "You do not have permission to invite students.")
            return redirect('course_detail', course_id=course_id)

        email = request.POST.get('email')
        course = get_object_or_404(Course, id=course_id)

        subject = f"You're invited to join {course.name}"
        message = f"""Hi there,

            You've been invited to join the course "{course.name}" on EagleOps.

            Use the following join code to access the course:
                
                {course.course_join_code}

            Visit the EagleOps site and enter the code to enroll.

            Best,
            The EagleOps Team"""

        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
            messages.success(request, f"Invite sent to {email}")
        except Exception as e:
            messages.error(request, f"Error sending email: {e}")

        return redirect('course_detail', course_id=course_id)
