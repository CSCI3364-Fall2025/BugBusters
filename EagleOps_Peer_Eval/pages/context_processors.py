from django.conf import settings
from .models import Course

def course_context(request):
    """
    Context processor that adds the user's courses and selected course to all templates.
    """
    if not request.user.is_authenticated:
        return {}
    
    user_profile = request.user.userprofile
    
    # Get all courses the user has access to
    if user_profile.admin:
        courses = Course.objects.all().order_by('name')
    else:
        # Get courses where user is an instructor
        instructor_courses = Course.objects.filter(instructors=user_profile)
        
        # Get courses where user is in a team
        team_courses = Course.objects.filter(teams__members=user_profile)
        
        # Get courses where user is directly enrolled
        enrolled_courses = Course.objects.filter(students=user_profile)
        
        # Combine the querysets and remove duplicates
        courses = (instructor_courses | team_courses | enrolled_courses).distinct().order_by('name')
    
    # Get the selected course from session or default to most recent
    selected_course_id = request.session.get('selected_course_id')
    selected_course = None
    
    if selected_course_id:
        try:
            selected_course = Course.objects.get(id=selected_course_id)
        except Course.DoesNotExist:
            pass
    
    # If no course is selected or the selected course is not in the user's courses,
    # select the most recent course
    if not selected_course or selected_course not in courses:
        selected_course = courses.first() if courses else None
        if selected_course:
            request.session['selected_course_id'] = selected_course.id
    
    return {
        'available_courses': courses,
        'selected_course': selected_course,
    } 