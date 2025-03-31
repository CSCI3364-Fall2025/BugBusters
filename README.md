# EagleOps Peer Evaluation

A streamlined peer assessment and team management platform.

## Quick Start

Use Makefile to set up Project.
"make install" will create a venv with all dependencies
"make migrate" will handle migrations, including automaticaly creating social app for oauth
"make run" will runserver

## Admin Access

The application uses a custom admin permission system. To make a user an admin:

1. Users with specific emails (configured in `pages/signals.py`) automatically get admin status
2. You can also grant admin status via the Django admin interface

## Superuser Creation

Create a superuser with:
```
python manage.py createsuperuser
```

## Development Notes

- The application has automatic OAuth setup to ensure a smooth experience for all developers
- OAuth credentials are stored in settings.py
- For production, ensure you use environment variables instead of hardcoded credentials

## Data Models

The application uses the following key models:

### User and Authentication Models

1. **User**
   - Django's built-in User model (`django.contrib.auth.models.User`)
   - Stores authentication data (username, email, password)
   - Extended by UserProfile for application-specific data

2. **UserProfile**
   - One-to-one relationship with User model
   - Stores additional user information:
     - First name and last name (separate from the built-in User model)
     - Admin status (determines application-level permissions)
   - Provides `full_name` property that combines first and last name

3. **Social Authentication**
   - Uses Django AllAuth for OAuth integration
   - Automatically links social accounts to existing users by email
   - Custom signal handlers update UserProfile data when users log in via OAuth

### Team Management Models

1. **Team**
   - Represents a group of users working together
   - Fields:
     - Name: The team's display name
     - Members: Many-to-many relationship with UserProfile
     - Created At: Timestamp of team creation
   - Each UserProfile can be a member of multiple teams

### Data Flow and Relationships

- User authentication data (username, email, password) is stored in the Django User model
- Extended user data (first_name, last_name, admin status) is stored in UserProfile
- Teams can have multiple members (UserProfiles), and users can belong to multiple teams
- OAuth login automatically populates UserProfile data from social account information
- Admin status is determined by email address (configured in signals.py) or manual assignment

This data model structure supports the core functionality of user management, authentication, and team organization within the application.
