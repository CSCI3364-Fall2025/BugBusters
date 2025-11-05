from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from pathlib import Path
import csv
import re

from ...models import (
    UserProfile, Course, Team, FormTemplate, Question, Form,
    FormResponse, Answer
)

U = get_user_model()

BATCH = 1000


def dict_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            yield row


def split_semester_year(s: str):
    """
    CSV has e.g. 'Fall 2025'. Map to (semester='Fall', year=2025).
    Fallbacks sensibly if string is unexpected.
    """
    if not s:
        return "Fall", timezone.now().year
    m = re.match(r"\s*(Fall|Spring)\s+(\d{4})\s*$", s, re.IGNORECASE)
    if m:
        sem = m.group(1).capitalize()
        year = int(m.group(2))
        return sem, year
    # last resort: try final 4 digits
    year = int(re.findall(r"(\d{4})", s)[-1]) if re.findall(r"(\d{4})", s) else timezone.now().year
    sem = "Fall" if "fall" in s.lower() else ("Spring" if "spring" in s.lower() else "Fall")
    return sem, year


class Command(BaseCommand):
    help = "Load CSV-first synthetic data into the DB (fast, FK-safe)."

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, help="Directory containing CSVs from eagleops_data_gen.py")
        parser.add_argument("--truncate", action="store_true", help="Delete existing data before load")
        parser.add_argument("--users_password", default=None, help="Password to assign to ALL users")
        parser.add_argument("--fast-hash", action="store_true",
                            help="Use MD5 hasher (dev only) to speed up password hashing")

    # Use MD5 hasher when --fast-hash is passed (dev-only).
    def handle(self, *args, **opts):
        if opts["fast_hash"]:
            with override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']):
                return self._handle_inner(opts)
        else:
            return self._handle_inner(opts)

    def _handle_inner(self, opts):
        base = Path(opts["path"])
        if not base.exists():
            raise CommandError(f"Not found: {base}")

        required = [
            "users.csv",
            "courses.csv",
            "enrollments.csv",
            "teams.csv",
            "team_members.csv",
            "eval_templates.csv",
            "eval_forms.csv",
            "eval_responses.csv",
        ]
        for name in required:
            if not (base / name).exists():
                raise CommandError(f"Missing {name}")

        if opts["truncate"]:
            self._truncate_all()
            self.stdout.write(self.style.WARNING("Truncated existing data."))

        with transaction.atomic():
            self._load_users_and_profiles(base / "users.csv", opts["users_password"])
            self._load_courses(base / "courses.csv")
            self._load_enrollments(base / "enrollments.csv")        # instructors & students M2M
            self._load_teams(base / "teams.csv")
            self._load_team_members(base / "team_members.csv")
            template_lookup = self._load_templates(base / "eval_templates.csv")
            self._load_forms(base / "eval_forms.csv", template_lookup)
            self._load_responses_and_answers(base / "eval_responses.csv")

        self.stdout.write(self.style.SUCCESS("Synthetic data load complete (csvfirst mode)."))

    # ----------------------- TRUNCATE (child → parent) -----------------------
    def _truncate_all(self):
        Answer.objects.all().delete()
        FormResponse.objects.all().delete()
        # clear M2M on forms first (teams)
        for f in Form.objects.all():
            f.teams.clear()
        Form.objects.all().delete()
        Question.objects.all().delete()
        FormTemplate.objects.all().delete()
        Team.members.through.objects.all().delete()
        Team.objects.all().delete()
        Course.instructors.through.objects.all().delete()
        Course.students.through.objects.all().delete()
        Course.objects.all().delete()
        UserProfile.objects.all().delete()
        # Keep superuser; wipe others
        U.objects.exclude(is_superuser=True).delete()

    # ----------------------- LOADERS -----------------------
    def _load_users_and_profiles(self, path: Path, pw: str | None):
        self.stdout.write("Loading users & profiles...")
        user_objs = []
        profile_objs = []

        # Pre-hash ONCE (fast). If pw None, use unusable "!".
        hashed_pw = make_password(pw) if pw else None

        count = 0
        for r in dict_rows(path):
            uid = int(r["id"])
            email = r["email"].strip().lower()
            full_name = r.get("full_name", "").strip()
            first, last = (full_name.split(" ", 1) + [""])[:2] if full_name else (email.split("@")[0], "")

            user_objs.append(U(
                id=uid,
                username=email,
                email=email,
                is_staff=False,
                is_superuser=False,
                is_active=True,
                password=(hashed_pw if hashed_pw else "!"),
            ))
            profile_objs.append(UserProfile(
                id=uid,              # keep IDs aligned so CSV user_id → profile_id
                user_id=uid,
                first_name=first or None,
                last_name=last or None,
                admin=(r.get("role", "").lower() == "instructor"),
                bio=None,
            ))
            count += 1
            if count % (BATCH * 5) == 0:
                self.stdout.write(f"  prepared {count} users...")

        U.objects.bulk_create(user_objs, ignore_conflicts=True, batch_size=BATCH)
        UserProfile.objects.bulk_create(profile_objs, ignore_conflicts=True, batch_size=BATCH)
        self.stdout.write(self.style.NOTICE(f"Users loaded: {len(user_objs)}; Profiles loaded: {len(profile_objs)}"))

    def _load_courses(self, path: Path):
        self.stdout.write("Loading courses...")
        objs = []
        for r in dict_rows(path):
            cid = int(r["id"])
            code = r["code"]
            title = r.get("title") or r.get("name") or code
            semester_raw = r.get("semester") or ""
            sem, yr = split_semester_year(semester_raw)
            objs.append(Course(
                id=cid,
                code=code,
                name=title,
                description="",
                semester=sem,
                year=yr,
            ))
        Course.objects.bulk_create(objs, ignore_conflicts=True, batch_size=BATCH)
        # ensure join codes
        for c in Course.objects.filter(course_join_code__isnull=True):
            c.save()
        self.stdout.write(self.style.NOTICE(f"Courses loaded: {Course.objects.count()}"))

    def _load_enrollments(self, path: Path):
        self.stdout.write("Linking enrollments (instructors/students)...")
        courses = {c.id: c for c in Course.objects.all()}
        profiles = {p.id: p for p in UserProfile.objects.all()}

        added_instructors = 0
        added_students = 0
        for r in dict_rows(path):
            cid = int(r["course_id"]); uid = int(r["user_id"])
            role = (r.get("role_in_course") or "").lower()
            c = courses.get(cid); p = profiles.get(uid)
            if not c or not p:
                continue
            if role == "instructor":
                c.instructors.add(p); added_instructors += 1
            else:
                c.students.add(p); added_students += 1
        self.stdout.write(self.style.NOTICE(
            f"Instructors linked: {added_instructors}; Students linked: {added_students}"
        ))

    def _load_teams(self, path: Path):
        self.stdout.write("Loading teams...")
        objs = []
        for r in dict_rows(path):
            objs.append(Team(
                id=int(r["id"]),
                course_id=int(r["course_id"]),
                name=r["name"],
            ))
        Team.objects.bulk_create(objs, ignore_conflicts=True, batch_size=BATCH)
        self.stdout.write(self.style.NOTICE(f"Teams loaded (unique): {Team.objects.count()}"))

    def _load_team_members(self, path: Path):
        self.stdout.write("Linking team members...")
        teams = {t.id: t for t in Team.objects.all()}
        count = 0
        for r in dict_rows(path):
            tid = int(r["team_id"]); uid = int(r["user_id"])
            t = teams.get(tid)
            if t:
                t.members.add(uid)
                count += 1
                if count % (BATCH * 5) == 0:
                    self.stdout.write(f"  linked {count} team_members...")
        self.stdout.write(self.style.NOTICE(f"Team-members links created: {count}"))

    def _load_templates(self, path: Path):
        """
        CSV has a single row: id, name, max_score
        We create a Question set Q1..Q5 (Likert) universally.
        Returns {template_id: (db_template_id, max_score)} for later.
        """
        self.stdout.write("Loading eval templates & questions...")
        tid_lookup = {}
        for r in dict_rows(path):
            tid_csv = int(r["id"])
            tmpl = FormTemplate.objects.create(
                id=tid_csv,
                title=r["name"],
                description=f"Max score {r['max_score']}",
                created_by=UserProfile.objects.first(),   # any valid profile; not used critically
                course=Course.objects.first(),            # any valid course; per-form we’ll point correctly
            )
            # create standard 5 Likert questions
            q_objs = []
            for i in range(1, 6):
                q_objs.append(Question(
                    template=tmpl,
                    text=f"Q{i}",
                    question_type=Question.LIKERT_SCALE,
                    order=i,
                ))
            Question.objects.bulk_create(q_objs, batch_size=BATCH)
            tid_lookup[tid_csv] = (tmpl.id, int(r["max_score"]))
        self.stdout.write(self.style.NOTICE(f"Templates loaded: {FormTemplate.objects.count()}"))
        return tid_lookup

    def _load_forms(self, path: Path, template_lookup):
        self.stdout.write("Loading forms...")
        forms_to_create = []
        for r in dict_rows(path):
            fid = int(r["id"])
            cid = int(r["course_id"])
            tmpl_csv_id = int(r["template_id"])
            tmpl_db_id, _ = template_lookup[tmpl_csv_id]
            pub = parse_datetime(r["open_at"])
            close = parse_datetime(r["close_at"])
            # pick someone valid as created_by (first instructor or fallback)
            created_by = (Course.objects.get(id=cid).instructors.first()
                          or UserProfile.objects.first())

            forms_to_create.append(Form(
                id=fid,
                title=f"Peer Eval (Course {cid})",
                template_id=tmpl_db_id,
                course_id=cid,
                created_by=created_by,
                self_assessment=False,
                publication_date=pub,
                closing_date=close,
                status=Form.SCHEDULED,  # will auto-resolve on save/lifecycle
            ))
        Form.objects.bulk_create(forms_to_create, ignore_conflicts=True, batch_size=BATCH)
        # No teams assigned here; we’ll infer teams per response later to add f.teams
        self.stdout.write(self.style.NOTICE(f"Forms loaded: {Form.objects.count()}"))

    def _load_responses_and_answers(self, path: Path):
        self.stdout.write("Loading responses & answers...")
        # Build a quick map of team -> members (profile ids)
        team_members = {}
        for t in Team.objects.all().only("id"):
            team_members[t.id] = set(t.members.values_list("id", flat=True))

        # Map form_id -> set of team_ids that appear in responses; we’ll attach forms→teams once
        form_to_teams = {}

        resp_objs = []
        ans_objs = []
        count = 0

        for r in dict_rows(path):
            rid = int(r["id"])
            fid = int(r["form_id"])
            evalr = int(r["evaluator_id"])
            evale = int(r["evaluatee_id"])
            tid = int(r["team_id"])

            # sanity: evaluator & evaluatee should be in same team
            if evalr not in team_members.get(tid, ()) or evale not in team_members.get(tid, ()):
                # skip corrupt rows quietly
                continue

            resp_objs.append(FormResponse(
                id=rid,
                form_id=fid,
                evaluator_id=evalr,
                evaluatee_id=evale,
                submitted=True,
                submission_date=timezone.now(),
            ))

            # Likert answers for Q1..Q5 (we created 5 per template, ordered 1..5)
            scores = [
                int(r.get("q1") or 0),
                int(r.get("q2") or 0),
                int(r.get("q3") or 0),
                int(r.get("q4") or 0),
                int(r.get("q5") or 0),
            ]

            # We don’t know the question ids directly; fetch by template order when needed.
            # Faster approach: assume order 1..5 are the only ones used.
            # We can resolve per-first form’s template.
            # To avoid N+1, resolve once per template:
            # Here, we will lazily map (form_id)->[qid1..qid5]
            if not hasattr(self, "_form_qids_cache"):
                self._form_qids_cache = {}
            if fid not in self._form_qids_cache:
                f = Form.objects.get(id=fid)
                qids = list(f.template.questions.order_by("order").values_list("id", flat=True))
                self._form_qids_cache[fid] = qids
            qids = self._form_qids_cache[fid]

            for i, qid in enumerate(qids[:5]):
                lik = scores[i] if scores[i] else None
                ans_objs.append(Answer(
                    response_id=rid,
                    question_id=qid,
                    likert_answer=lik,
                    text_answer=None,
                ))

            form_to_teams.setdefault(fid, set()).add(tid)

            count += 1
            if count % (BATCH * 5) == 0:
                self.stdout.write(f"  prepared {count} responses...")

        FormResponse.objects.bulk_create(resp_objs, ignore_conflicts=True, batch_size=BATCH)
        Answer.objects.bulk_create(ans_objs, ignore_conflicts=True, batch_size=BATCH)

        # Attach the teams that appeared in responses to each form
        self.stdout.write("Attaching teams to forms...")
        forms = {f.id: f for f in Form.objects.all().only("id")}
        for fid, tids in form_to_teams.items():
            f = forms.get(fid)
            if not f:
                continue
            f.teams.add(*tids)

        self.stdout.write(self.style.NOTICE(
            f"Responses loaded: {len(resp_objs)}; Answers loaded: {len(ans_objs)}"
        ))
