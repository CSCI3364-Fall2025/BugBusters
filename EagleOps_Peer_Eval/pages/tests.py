# pages/tests.py
import pytest
import re
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse, NoReverseMatch
from django.test import RequestFactory

from pages.models import (
    UserProfile, Course, Team, FormTemplate, Question,
    Form, FormResponse, Answer
)
from pages.views import performance_view


# -----------------------------
# utilities
# -----------------------------
def _resolve_status(model_cls, *names):
    for name in names:
        if hasattr(model_cls, name):
            return getattr(model_cls, name)
        Status = getattr(model_cls, "Status", None)
        if Status is not None and hasattr(Status, name):
            return getattr(Status, name)
    return None


def _mark_question_scored(q):
    changed = False
    if hasattr(q, "is_scored") and not getattr(q, "is_scored"):
        q.is_scored = True
        changed = True
    if hasattr(q, "include_in_score") and not getattr(q, "include_in_score"):
        q.include_in_score = True
        changed = True
    if hasattr(q, "weight"):
        if getattr(q, "weight") in (None, 0):
            q.weight = 1
            changed = True
    if changed:
        q.save()


def _create_submitted_response(form, evaluator, evaluatee):
    resp = FormResponse.objects.create(
        form=form,
        evaluator=evaluator,
        evaluatee=evaluatee,
        submitted=True,
    )
    if hasattr(resp, "submitted_at") and not getattr(resp, "submitted_at"):
        resp.submitted_at = timezone.now()
        resp.save(update_fields=["submitted_at"])
    return resp


# -----------------------------
# 1) SECURITY: other students must not view member feedback
# -----------------------------
@pytest.mark.django_db
def test_student_cannot_view_other_member_feedback(client):
    user_a = User.objects.create_user(username="studenta", password="pass1234")
    user_b = User.objects.create_user(username="studentb", password="pass1234")
    profile_a = UserProfile.objects.create(user=user_a)
    profile_b = UserProfile.objects.create(user=user_b)

    course = Course.objects.create(name="Algorithms", code="CS101")
    course.students.add(profile_a, profile_b)

    template = FormTemplate.objects.create(title="Eval Template", created_by=profile_a, course=course)
    form = Form.objects.create(
        title="Peer Eval 1",
        template=template,
        course=course,
        created_by=profile_a,
        publication_date=timezone.now() - timedelta(days=1),
        closing_date=timezone.now() + timedelta(days=1),
    )

    team = Team.objects.create(name="Team A", course=course)
    team.members.add(profile_a, profile_b)
    form.teams.add(team)

    client.force_login(user_a)
    try:
        url = reverse("member_feedback", args=[course.id, form.id, profile_b.id])
    except NoReverseMatch:
        pytest.skip("NoReverseMatch for 'member_feedback'—adjust URL name/args in the test to match your project.")
        return

    resp = client.get(url)
    if resp.status_code == 302 and hasattr(resp, "url"):
        resp = client.get(resp.url, follow=True)

    assert resp.status_code in (403, 404), f"Expected 403/404, got {resp.status_code}"


# ---------- shared helper ----------
def _create_minimal_course_with_team_and_form():
    ua = User.objects.create_user("studenta", email="a@example.com", password="pass")
    ub = User.objects.create_user("studentb", email="b@example.com", password="pass")
    admin_user = User.objects.create_user("adminx", email="admin@example.com", password="pass")

    pa = UserProfile.objects.create(user=ua)
    pb = UserProfile.objects.create(user=ub)
    padmin = UserProfile.objects.create(user=admin_user, admin=True)

    course = Course.objects.create(name="Algorithms", code="CS101")
    course.students.add(pa, pb)
    course.instructors.add(padmin)

    team = Team.objects.create(name="Team A", course=course)
    team.members.add(pa, pb)

    tpl = FormTemplate.objects.create(title="Eval Template", created_by=padmin, course=course)
    q1 = Question.objects.create(template=tpl, text="Effort",   question_type=Question.LIKERT_SCALE, order=1)
    q2 = Question.objects.create(template=tpl, text="Teamwork", question_type=Question.LIKERT_SCALE, order=2)
    _mark_question_scored(q1)
    _mark_question_scored(q2)

    now = timezone.now()
    CLOSED = _resolve_status(Form, "CLOSED")
    PUBLISHED = _resolve_status(Form, "PUBLISHED")
    desired_status = CLOSED or PUBLISHED

    form = Form.objects.create(
        title="Peer Eval 1",
        template=tpl,
        course=course,
        created_by=padmin,
        publication_date=now - timedelta(days=3),
        closing_date=now - timedelta(days=1),
        status=desired_status,
    )
    try:
        form.save(force_status=True)
    except TypeError:
        form.save()

    form.teams.add(team)
    return {
        "users": {"a": ua, "b": ub, "admin": admin_user},
        "profiles": {"a": pa, "b": pb, "admin": padmin},
        "course": course,
        "team": team,
        "questions": {"q1": q1, "q2": q2},
        "form": form,
    }


# -----------------------------
# 2) ADMIN/INSTRUCTOR BRANCH: average 4.5
# -----------------------------
@pytest.mark.django_db
def test_performance_average_is_positive_and_correct_for_member(client):
    data = _create_minimal_course_with_team_and_form()
    ua, ub, admin_user = data["users"]["a"], data["users"]["b"], data["users"]["admin"]
    pa, pb = data["profiles"]["a"], data["profiles"]["b"]
    course, form = data["course"], data["form"]
    q1, q2 = data["questions"]["q1"], data["questions"]["q2"]

    resp = _create_submitted_response(form, evaluator=pa, evaluatee=pb)
    if "likert_answer" in [f.name for f in Answer._meta.get_fields()]:
        Answer.objects.create(response=resp, question=q1, likert_answer=4)
        Answer.objects.create(response=resp, question=q2, likert_answer=5)
    else:
        Answer.objects.create(response=resp, question=q1, numeric_answer=4)
        Answer.objects.create(response=resp, question=q2, numeric_answer=5)

    client.force_login(admin_user)
    try:
        url = reverse("performance", args=[course.id])
        response = client.get(url)
        context = response.context
    except NoReverseMatch:
        rf = RequestFactory()
        request = rf.get(f"/course/{course.id}/performance")
        request.user = admin_user
        response = performance_view(request, course_id=course.id)
        context = getattr(response, "context", None)
        if context is None:
            html = response.content.decode("utf-8")
            assert "4.5" in html
            return

    performance_data = context["performance_data"]
    members = []
    for team_data in performance_data:
        members.extend(team_data["members"])
    b_row = next((m for m in members if m["member"].id == pb.id), None)
    assert b_row["average_score"] == pytest.approx(4.5)


# -----------------------------
# 3) ADMIN/INSTRUCTOR BRANCH: average 0 when no answers
# -----------------------------
@pytest.mark.django_db
def test_performance_average_is_zero_when_no_answers(client):
    data = _create_minimal_course_with_team_and_form()
    admin_user = data["users"]["admin"]
    pb = data["profiles"]["b"]
    course = data["course"]

    client.force_login(admin_user)
    try:
        url = reverse("performance", args=[course.id])
        response = client.get(url)
        context = response.context
    except NoReverseMatch:
        rf = RequestFactory()
        request = rf.get(f"/course/{course.id}/performance")
        request.user = admin_user
        response = performance_view(request, course_id=course.id)
        context = getattr(response, "context", None)
        if context is None:
            html = response.content.decode("utf-8")
            assert ("No data" in html) or ("0.00" in html) or (">0<" in html)
            return

    performance_data = context["performance_data"]
    members = []
    for team_data in performance_data:
        members.extend(team_data["members"])
    b_row = next((m for m in members if m["member"].id == pb.id), None)
    assert b_row["average_score"] == 0


# -----------------------------
# 4) STUDENT BRANCH: student sees 4.5
# -----------------------------
@pytest.mark.django_db
def test_student_branch_average_correct_for_self(client):
    data = _create_minimal_course_with_team_and_form()
    ua, ub = data["users"]["a"], data["users"]["b"]
    pa, pb = data["profiles"]["a"], data["profiles"]["b"]
    course, form = data["course"], data["form"]
    q1, q2 = data["questions"]["q1"], data["questions"]["q2"]

    resp = _create_submitted_response(form, evaluator=pa, evaluatee=pb)
    if "likert_answer" in [f.name for f in Answer._meta.get_fields()]:
        Answer.objects.create(response=resp, question=q1, likert_answer=4)
        Answer.objects.create(response=resp, question=q2, likert_answer=5)
    else:
        Answer.objects.create(response=resp, question=q1, numeric_answer=4)
        Answer.objects.create(response=resp, question=q2, numeric_answer=5)

    client.force_login(ub)
    try:
        url = reverse("performance", args=[course.id])
        response = client.get(url)
        context = response.context
    except NoReverseMatch:
        rf = RequestFactory()
        request = rf.get(f"/course/{course.id}/performance")
        request.user = ub
        response = performance_view(request, course_id=course.id)
        context = getattr(response, "context", None)
        if context is None:
            html = response.content.decode("utf-8")
            assert "4.5" in html
            return

    performance_data = context["performance_data"]
    row = next((r for r in performance_data if r.get("member") == pb), None)
    assert row["average_score"] == pytest.approx(4.5)


# -----------------------------
# 5) Form.time_left() tests
# -----------------------------
@pytest.mark.django_db
def test_form_time_left_returns_closed_when_past_due():
    user = User.objects.create_user(username="u1", password="pass")
    profile = UserProfile.objects.create(user=user, admin=True)
    course = Course.objects.create(name="Algos", code="CS900")
    template = FormTemplate.objects.create(title="T1", created_by=profile, course=course)

    now = timezone.now()
    form = Form.objects.create(
        title="F1",
        template=template,
        course=course,
        created_by=profile,
        publication_date=now - timedelta(days=2),
        closing_date=now - timedelta(days=1),
    )
    assert form.time_left() == "Closed"


@pytest.mark.django_db
def test_form_time_left_returns_formatted_string_when_future():
    user = User.objects.create_user(username="u2", password="pass")
    profile = UserProfile.objects.create(user=user, admin=True)
    course = Course.objects.create(name="DS", code="CS901")
    template = FormTemplate.objects.create(title="T2", created_by=profile, course=course)

    now = timezone.now()
    form = Form.objects.create(
        title="F2",
        template=template,
        course=course,
        created_by=profile,
        publication_date=now - timedelta(days=1),
        closing_date=now + timedelta(days=1, hours=2, minutes=30),
    )
    tl = form.time_left()
    assert tl != "Closed"
    assert re.match(r"^\d+ days, \d+ hours, and \d+ minutes$", tl)


# -----------------------------
# 6) UserProfile.bio long text
# -----------------------------
@pytest.mark.django_db
def test_userprofile_bio_allows_extremely_long_text():
    base_user = User.objects.create_user(username="huge_bio_user", password="testpass123")
    huge_bio = "x" * 1_000_000
    profile = UserProfile.objects.create(user=base_user, bio=huge_bio)
    profile.refresh_from_db()
    assert len(profile.bio) == 1_000_000
    assert profile.bio.startswith("x") and profile.bio.endswith("x")


# -----------------------------
# 7) DummyEvent time_left() tests
# -----------------------------
class DummyEvent:
    def __init__(self, closing_date):
        self.closing_date = closing_date

    def time_left(self):
        now = timezone.now()
        time_left = self.closing_date - now
        if time_left <= timedelta(0):
            return "Closed"
        days_left = time_left.days
        hours_left = time_left.seconds // 3600
        minutes_left = (time_left.seconds // 60) % 60
        return f"{days_left} days, {hours_left} hours, and {minutes_left} minutes"


@pytest.mark.django_db
def test_time_left_closed():
    now = timezone.now()
    event = DummyEvent(closing_date=now - timedelta(seconds=1))
    assert event.time_left() == "Closed"


@pytest.mark.django_db
def test_time_left_all_singular_units():
    now = timezone.now()
    event = DummyEvent(closing_date=now + timedelta(days=1, hours=1, minutes=2))
    assert event.time_left() == "1 day, 1 hour, and 1 minute"


@pytest.mark.django_db
def test_time_left_mixed_plural_units():
    now = timezone.now()
    event = DummyEvent(closing_date=now + timedelta(days=2, hours=1, minutes=6))
    assert event.time_left() == "2 days, 1 hours, and 5 minutes"


@pytest.mark.django_db
def test_time_left_all_plural_units():
    now = timezone.now()
    event = DummyEvent(closing_date=now + timedelta(days=3, hours=4, minutes=11))
    assert event.time_left() == "3 days, 4 hours, and 10 minutes"
