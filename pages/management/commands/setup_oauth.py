from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings


class Command(BaseCommand):
    help = 'Sets up social applications for OAuth'

    def handle(self, *args, **options):
        # Get or create site
        site, _ = Site.objects.get_or_create(
            id=settings.SITE_ID,
            defaults={
                'domain': 'example.com',
                'name': 'EagleOps'
            }
        )
        
        # Create Google social app if it doesn't exist
        if not SocialApp.objects.filter(provider='google').exists():
            self.stdout.write('Creating Google social app...')
            social_app = SocialApp.objects.create(
                provider='google',
                name='Google OAuth',
                client_id=settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                secret=settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                key=''  # Not needed for Google
            )
            social_app.sites.add(site)
            self.stdout.write(self.style.SUCCESS('Successfully created Google social app'))
        else:
            self.stdout.write('Google social app already exists') 