from django.db import migrations
from django.conf import settings

def setup_social_app(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    SocialApp = apps.get_model('socialaccount', 'SocialApp')
    
    # Get the site
    site = Site.objects.get(id=settings.SITE_ID)
    
    # Create or update the Google OAuth app
    SocialApp.objects.get_or_create(
        provider='google',
        defaults={
            'name': 'Google',
            'client_id': '78382397878-2ornph09voga6d32k4u0h6obkbpqe1ml.apps.googleusercontent.com',
            'secret': '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',
        }
    )
    
    # Get the app and add the site
    app = SocialApp.objects.get(provider='google')
    app.sites.add(site)

def remove_social_app(apps, schema_editor):
    SocialApp = apps.get_model('socialaccount', 'SocialApp')
    SocialApp.objects.filter(provider='google').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('pages', '0002_create_site'),
        ('socialaccount', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(setup_social_app, remove_social_app),
    ] 