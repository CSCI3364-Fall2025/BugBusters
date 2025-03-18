# EagleOps Peer Evaluation

A streamlined peer assessment and team management platform.

## Quick Start

The easiest way to set up this project is to use the provided setup script:

```
git clone <repository-url>
cd EagleOps
./setup.py
```

This script will:
1. Install all required dependencies
2. Run database migrations
3. Ask if you want to create a superuser
4. Set up OAuth automatically

## Manual Setup Instructions

If you prefer to set up the project manually:

1. Clone the repository
   ```
   git clone <repository-url>
   cd EagleOps
   ```

2. Install dependencies
   ```
   pip install -r requirements.txt --use-pep517
   ```

3. Run migrations
   ```
   python manage.py migrate
   ```

4. Create a superuser (optional)
   ```
   python manage.py createsuperuser
   ```

5. Run the server
   ```
   python manage.py runserver
   ```

## OAuth Configuration

The application is configured to use Google OAuth for authentication. The OAuth setup happens automatically when:

1. You run migrations - a data migration will create the site and social application
2. You start the application - the app initialization will check and create the social app if needed

### Manual OAuth Setup (only if needed)

If the automatic setup fails for any reason, you can manually set up OAuth:

1. Access the Django admin at `/admin/` and log in as a superuser
2. Navigate to "Sites" and ensure that Site ID 2 exists with appropriate domain
3. Navigate to "Social applications" and add a new Google social application with:
   - Provider: Google
   - Name: Google OAuth
   - Client ID: From settings.py
   - Secret key: From settings.py
   - Add the site to the "Chosen sites"

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