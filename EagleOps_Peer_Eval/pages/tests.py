import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from pages.models import UserProfile, Course, Form, FormTemplate, FormResponse, Team
from django.utils import timezone
from datetime import timedelta

@pytest.mark.django_db
def test_student_cannot_view_other_member_feedback(client):
    """
    Student A should not be able to view Student B's feedback results.
    """
    # Create two base users + profiles
    user_a = User.objects.create_user(username="studenta", password="pass1234")
    user_b = User.objects.create_user(username="studentb", password="pass1234")
    profile_a = UserProfile.objects.create(user=user_a)
    profile_b = UserProfile.objects.create(user=user_b)

    # Create a course and enroll both
    course = Course.objects.create(name="Algorithms", code="CS101")
    course.students.add(profile_a, profile_b)

    # Create a template and form for this course
    template = FormTemplate.objects.create(title="Eval Template", created_by=profile_a, course=course)
    form = Form.objects.create(
        title="Peer Eval 1",
        template=template,
        course=course,
        created_by=profile_a,
        publication_date=timezone.now() - timedelta(days=1),
        closing_date=timezone.now() + timedelta(days=1),
    )

    # Attach a dummy team so the form is valid
    team = Team.objects.create(name="Team A", course=course)
    team.members.add(profile_a, profile_b)
    form.teams.add(team)

    # Log in as student A
    client.force_login(user_a)

    # Try to view student B's feedback
    url = reverse("member_feedback", args=[course.id, form.id, profile_b.id])
    resp = client.get(url)

    # This should be forbidden if object-level checks are in place
    assert resp.status_code == 403


@pytest.mark.django_db
def test_non_admin_email_not_escalated(client):
    """
    A user not in the privileged list should not automatically be elevated
    to staff/superuser by login signals.
    """
    user = User.objects.create_user(username="random", email="random@example.com", password="pass1234")
    profile = UserProfile.objects.create(user=user)

    # Trigger login to fire any signals
    client.login(username="random", password="pass1234")

    user.refresh_from_db()
    profile.refresh_from_db()

    assert not user.is_staff
    assert not user.is_superuser
    assert not profile.admin
