from django.contrib.auth.models import User
from pages.models import UserProfile, Team, Course

# Get the first user
user = User.objects.first()

# Create or get user profile
if user:
    userprofile, created = UserProfile.objects.get_or_create(user=user, defaults={'admin': True})
    
    # Create a demo team
    team, created = Team.objects.get_or_create(name='Demo Team')
    if created:
        team.members.add(userprofile)
    
    # Create a demo course
    course, created = Course.objects.get_or_create(
        code='DEMO101',
        defaults={
            'name': 'Demo Course',
            'description': 'A demo course for testing form management features'
        }
    )
    
    if created:
        course.teams.add(team)
        course.instructors.add(userprofile)
    
    print('Demo data created successfully!')
else:
    print('No user found. Please create a user first.') 