from django.test import TestCase
from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_student_cannot_view_other_member_feedback(client, student_a, student_b, course, form):
    client.force_login(student_a)
    url = reverse("member_feedback", args=[course.id, form.id, student_b.id])
    resp = client.get(url)
    # should be forbidden
    assert resp.status_code == 403

# Create your tests here.
@pytest.mark.django_db
def test_non_admin_email_not_escalated(client, django_user_model):
    # create a random user not in the hard-coded list
    user = django_user_model.objects.create_user("random", "random@example.com", "pass")
    assert not user.is_staff
    assert not user.is_superuser
