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
import json
from django.contrib.auth import logout
from django.db.utils import IntegrityError

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

def todo_view(request):
    return render(request, "to_do.html")

@login_required
def teams(request):
    user = request.user.userprofile

    if user.admin:
        # Admins see all teams
        teams = Team.objects.prefetch_related('members__user').all()
    else:
        # Non-admins see only their team(s)
        teams = Team.objects.prefetch_related('members__user').filter(members=user)
    
    return render(request, 'teams.html', {'teams': teams})

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
        
        # Combine the two querysets and remove duplicates
        course_list = (instructor_courses | team_courses).distinct().order_by('name')
    
    context = {
        'courses': course_list,
        'is_admin': user_profile.admin,
    }
    
    return render(request, 'courses.html', context)

@login_required
def course_detail(request, course_id):
    """
    View for displaying course details including form templates and forms.
    """
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return redirect('courses')
    
    user_profile = request.user.userprofile
    
    # Check if user has access to this course
    if not user_profile.admin and not course.instructors.filter(id=user_profile.id).exists() and not course.teams.filter(members=user_profile).exists():
        return redirect('courses')
    
    # Get form templates for this course
    templates = FormTemplate.objects.filter(course=course).order_by('-created_at')
    
    # Get forms for this course
    forms = Form.objects.filter(course=course).order_by('-created_at')
    
    # Get teams for this course
    teams = course.teams.all()
    
    # Find if the user is in any of these teams
    user_teams = []
    for team in teams:
        if team.members.filter(id=user_profile.id).exists():
            user_teams.append(team)
    
    context = {
        'course': course,
        'templates': templates,
        'forms': forms,
        'teams': teams,
        'user_teams': user_teams,
        'is_instructor': course.instructors.filter(id=user_profile.id).exists(),
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
            
            # Return response based on request type
            if is_ajax:
                return JsonResponse({'status': 'success', 'template_id': template.id})
            else:
                # Redirect based on save_exit flag
                if save_exit:
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

@login_required
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
    teams = Team.objects.filter(courses=course)
    
    if request.method == 'POST':
        # Handle save action
        data = json.loads(request.body)
        title = data.get('title', '')
        template_id = data.get('template_id')
        publication_date = data.get('publication_date')
        closing_date = data.get('closing_date')
        team_ids = data.get('team_ids', [])
        self_assessment = data.get('self_assessment', False)
        
        if not title or not template_id or not publication_date or not closing_date:
            return JsonResponse({'status': 'error', 'message': 'All required fields must be provided'}, status=400)
        
        if not team_ids:
            return JsonResponse({'status': 'error', 'message': 'At least one team must be selected'}, status=400)
        
        template = get_object_or_404(FormTemplate, id=template_id, course=course)
        
        if form:
            # Update existing form
            form.title = title
            form.template = template
            form.publication_date = publication_date
            form.closing_date = closing_date
            form.self_assessment = self_assessment
            form.save()
            
            # Update teams
            form.teams.set(team_ids)
        else:
            # Create new form
            form = Form.objects.create(
                title=title,
                template=template,
                course=course,
                created_by=user,
                publication_date=publication_date,
                closing_date=closing_date,
                self_assessment=self_assessment
            )
            
            # Set teams
            form.teams.set(team_ids)
            
            # Create FormResponse objects for each evaluation
            for team in Team.objects.filter(id__in=team_ids):
                members = team.members.all()
                for evaluator in members:
                    for evaluatee in members:
                        # If self-assessment is disabled, skip self-evaluations
                        if not self_assessment and evaluator == evaluatee:
                            continue
                            
                        FormResponse.objects.create(
                            form=form,
                            evaluator=evaluator,
                            evaluatee=evaluatee
                        )
        
        return JsonResponse({'status': 'success', 'form_id': form.id})
    
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
@require_POST
def form_publish(request, course_id, form_id):
    """Publish a form"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can publish forms
    if not user.admin:
        raise PermissionDenied
    
    form = get_object_or_404(Form, id=form_id, course=course)
    
    # Change status to scheduled or active based on current time
    now = timezone.now()
    if now < form.publication_date:
        form.status = Form.SCHEDULED
    else:
        form.status = Form.ACTIVE
    
    form.save()
    
    return redirect('course_detail', course_id=course_id)

@login_required
@require_POST
def form_unpublish(request, course_id, form_id):
    """Unpublish a form"""
    user = request.user.userprofile
    course = get_object_or_404(Course, id=course_id)
    
    # Only admins can unpublish forms
    if not user.admin:
        raise PermissionDenied
    
    form = get_object_or_404(Form, id=form_id, course=course)
    form.status = Form.DRAFT
    form.save()
    
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
