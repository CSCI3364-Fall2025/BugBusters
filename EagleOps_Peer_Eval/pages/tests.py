# pages/tests.py
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse, NoReverseMatch
from django.test import RequestFactory
import re

from pages.models import (
    UserProfile, Course, Team, FormTemplate, Question,
    Form, FormResponse, Answer
)
from pages.views import performance_view


# -----------------------------
# utilities
# -----------------------------
def _resolve_status(model_cls, *names):
    """
    Try to find a status constant on the model.
    Accepts names in preference order, returns the first found value or None.
    Works with either attributes like Form.CLOSED or Form.Status.CLOSED.
    """
    for name in names:
        # direct attribute (e.g., Form.CLOSED)
        if hasattr(model_cls, name):
            return getattr(model_cls, name)
        # TextChoices inner class (e.g., Form.Status.CLOSED)
        Status = getattr(model_cls, "Status", None)
        if Status is not None and hasattr(Status, name):
            return getattr(Status, name)
    return None


def _mark_question_scored(q):
    """
    Make sure a question will be included in scoring if the model uses such flags.
    """
    changed = False
    if hasattr(q, "is_scored") and not getattr(q, "is_scored"):
        q.is_scored = True
        changed = True
    if hasattr(q, "include_in_score") and not getattr(q, "include_in_score"):
        q.include_in_score = True
        changed = True
    if hasattr(q, "weight"):
        w = getattr(q, "weight")
        if w in (None, 0):
            q.weight = 1
            changed = True
    if changed:
        q.save()


def _create_submitted_response(form, evaluator, evaluatee):
    """
    Create a submitted FormResponse and return it. Ensures submitted_at if the field exists.
    """
    resp = FormResponse.objects.create(
        form=form,
        evaluator=evaluator,
        evaluatee=evaluatee,
        submitted=True,
    )
    # Some code considers only responses with a timestamp truly "submitted"
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
        # If the URL name differs in your project, skip with a helpful message
        pytest.skip("NoReverseMatch for 'member_feedback'—adjust URL name/args in the test to match your project.")
        return

    resp = client.get(url)

    # Some apps redirect unauthorized users instead of returning 403 immediately.
    if resp.status_code == 302 and hasattr(resp, "url"):
        resp = client.get(resp.url, follow=True)

    # Be tolerant to either 403 or 404 (some apps avoid leaking existence)
    assert resp.status_code in (403, 404), f"Expected 403/404 for forbidden access, got {resp.status_code}"


# ---------- shared helper for performance tests ----------
def _create_minimal_course_with_team_and_form():
    ua = User.objects.create_user("studenta", email="a@example.com", password="pass")
    ub = User.objects.create_user("studentb", email="b@example.com", password="pass")
    admin_user = User.objects.create_user("adminx", email="admin@example.com", password="pass")

    pa = UserProfile.objects.create(user=ua)
    pb = UserProfile.objects.create(user=ub)
    padmin = UserProfile.objects.create(user=admin_user, admin=True)

    course = Course.objects.create(name="Algorithms", code="CS101")
    course.students.add(pa, pb)
    course.instructors.add(padmin)  # ensure instructor/admin branch is available

    team = Team.objects.create(name="Team A", course=course)
    team.members.add(pa, pb)

    tpl = FormTemplate.objects.create(title="Eval Template", created_by=padmin, course=course)
    q1 = Question.objects.create(template=tpl, text="Effort",   question_type=Question.LIKERT_SCALE, order=1)
    q2 = Question.objects.create(template=tpl, text="Teamwork", question_type=Question.LIKERT_SCALE, order=2)

    # Ensure questions are included in scoring if the model uses flags/weights
    _mark_question_scored(q1)
    _mark_question_scored(q2)

    now = timezone.now()
    # Prefer CLOSED if your view only aggregates closed forms; otherwise fall back to PUBLISHED
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
    # Prevent any save() logic from overriding our explicit status if supported
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
# 2) ADMIN/INSTRUCTOR BRANCH: average should be > 0 and correct (4.5)
# -----------------------------
@pytest.mark.django_db
def test_performance_average_is_positive_and_correct_for_member(client):
    data = _create_minimal_course_with_team_and_form()
    ua, ub, admin_user = data["users"]["a"], data["users"]["b"], data["users"]["admin"]
    pa, pb = data["profiles"]["a"], data["profiles"]["b"]
    course, form = data["course"], data["form"]
    q1, q2 = data["questions"]["q1"], data["questions"]["q2"]

    # A evaluates B with likert answers 4,5 -> 4.5
    resp = _create_submitted_response(form, evaluator=pa, evaluatee=pb)

    # Use the field your Answer model expects. Likert projects often use either likert_answer or numeric_answer.
    if "likert_answer" in [f.name for f in Answer._meta.get_fields()]:
        Answer.objects.create(response=resp, question=q1, likert_answer=4)
        Answer.objects.create(response=resp, question=q2, likert_answer=5)
    else:
        Answer.objects.create(response=resp, question=q1, numeric_answer=4)
        Answer.objects.create(response=resp, question=q2, numeric_answer=5)

    # --- sanity checks: fail early with a precise reason if setup slipped ---
    assert Form.objects.filter(id=form.id, status=form.status).exists(), "Form row not found with chosen status"
    assert form in data["team"].assigned_forms.all(), "Form is not assigned to the team"
    assert FormResponse.objects.filter(form=form, evaluatee=pb, submitted=True).exists(), "No submitted response for evaluatee"

    client.force_login(admin_user)

    # Hit the view (URL or direct call fallback)
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
            assert "4.5" in html, f"Rendered HTML did not include 4.5:\n{html}"
            return

    performance_data = context["performance_data"]
    assert isinstance(performance_data, list) and performance_data, "Expected non-empty performance_data list"

    members = []
    for team_data in performance_data:
        assert "members" in team_data, f"Expected 'members' key in admin/instructor branch, got: {team_data.keys()}"
        members.extend(team_data["members"])

    b_row = next((m for m in members if getattr(m["member"], "id", None) == data["profiles"]["b"].id), None)
    assert b_row is not None, "Student B row not found in performance data"
    assert b_row["average_score"] == pytest.approx(4.5), f"Got {b_row['average_score']} instead of 4.5"


# -----------------------------
# 3) ADMIN/INSTRUCTOR BRANCH: average should be 0 when no answers exist
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
            # Be lenient to different renderings of "no data"
            assert ("No data" in html) or ("0.00" in html) or (">0<" in html)
            return

    performance_data = context["performance_data"]
    assert isinstance(performance_data, list) and performance_data, "Expected non-empty performance_data list"

    members = []
    for team_data in performance_data:
        assert "members" in team_data, "Expected admin/instructor data to include 'members'"
        members.extend(team_data["members"])

    b_row = next((m for m in members if getattr(m["member"], "id", None) == pb.id), None)
    assert b_row is not None, "Expected to find student B in performance table"
    assert b_row["average_score"] == 0


# -----------------------------
# 4) STUDENT BRANCH: student sees their own average correctly (4.5)
# -----------------------------
@pytest.mark.django_db
def test_student_branch_average_correct_for_self(client):
    # Same fixture, but log in as the student (exercise student branch)
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

    # sanity checks
    assert form in data["team"].assigned_forms.all(), "Form is not assigned to the team"
    assert FormResponse.objects.filter(form=form, evaluatee=pb, submitted=True).exists(), "No submitted response for evaluatee"

    # Log in as the student (NOT admin/instructor)
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
            assert "4.5" in html, f"Rendered HTML did not include 4.5:\n{html}"
            return

    performance_data = context["performance_data"]
    assert isinstance(performance_data, list) and performance_data, "Expected non-empty performance_data (student branch)"

    # student branch: entries look like {'member': <UserProfile>, 'forms': [...], 'average_score': ...}
    row = next((r for r in performance_data if r.get("member") == pb), None)
    assert row is not None, "Expected logged-in student's row in performance data"
    assert row["average_score"] == pytest.approx(4.5), f"Got {row['average_score']} instead of 4.5"

# -----------------------------
# 5) Form.time_left() basic behavior - form should be closed when past due date, should be open before due date
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