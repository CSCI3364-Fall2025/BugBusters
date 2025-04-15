from django.db import migrations
from django.conf import settings

def create_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    Site.objects.get_or_create(
        id=settings.SITE_ID,
        defaults={
            'domain': 'localhost:8000',
            'name': 'EagleOps Peer Evaluation'
        }
    )

def delete_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    Site.objects.filter(id=settings.SITE_ID).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('pages', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(create_site, delete_site),
    ] 