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
