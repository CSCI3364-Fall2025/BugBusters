from django.apps import AppConfig
import os
import sys

class PagesConfig(AppConfig):
    name = 'pages'

    def ready(self):
        import pages.signals  # import signals when the app is ready
        
        # Only run when using the runserver command or when not running migrations
        if (os.environ.get('RUN_MAIN') == 'true' and 'runserver' in sys.argv) or \
           ('migrate' not in sys.argv and 'makemigrations' not in sys.argv and 'test' not in sys.argv):
            # Import and run the command to set up OAuth
            try:
                # Using this approach to avoid import errors during migrations
                from django.core.management import call_command
                call_command('setup_oauth')
            except Exception as e:
                print(f"Could not set up OAuth automatically: {e}")
                # Don't raise the exception, as we don't want to prevent the app from starting 