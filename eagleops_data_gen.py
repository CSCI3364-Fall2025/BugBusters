#!/usr/bin/env python3
"""
EagleOps synthetic data generator (CSV-first).

Usage:
  python eagleops_data_gen.py --level 1 --out ./eagleops_data/level1 --seed 42
  python eagleops_data_gen.py --level 2 --out ./eagleops_data/level2
  python eagleops_data_gen.py --level 3 --out ./eagleops_data/level3 --semester "Fall 2025"

Levels (as per assignment):
- Level 1: ~150 courses/semester, 30-80 students/course, team size 4-8
- Level 2: ~700 courses/semester, 30-80 students/course, team size 4-6
- Level 3: ~2000 courses/semester, 30-100 students/course, team size 4-6

Outputs: CSVs with referential integrity.
  - users.csv: id, full_name, email, role
  - courses.csv: id, code, title, semester, instructor_id
  - enrollments.csv: course_id, user_id, role_in_course
  - teams.csv: id, course_id, name
  - team_members.csv: team_id, user_id
  - eval_templates.csv: id, name, max_score
  - eval_forms.csv: id, course_id, template_id, open_at, close_at
  - eval_responses.csv: id, form_id, evaluator_id, evaluatee_id, team_id, q1..q5, comments

Design choices:
- 1 instructor per course (unique user), remaining users are students.
- Teams partition all students in a course; sizes within requested range.
- Each course gets 1 eval form referencing a common template id (or per-course if desired).
- Scores are integers 1..max_score with realistic distribution (slightly biased upward).
- Deterministic with --seed for reproducibility.
"""

import argparse, os, csv, random, math, datetime
from pathlib import Path

def name_from_id(uid:int)->str:
    # Silly but stable pseudo-names
    firsts = ["Alex","Jordan","Taylor","Morgan","Riley","Casey","Quinn","Jamie","Avery","Dakota",
              "Rowan","Skyler","Parker","Reese","Kendall","Hayden","Emerson","Finley","Logan","Micah"]
    lasts  = ["Rivera","Nguyen","Patel","Kim","Chen","Garcia","Martinez","Brown","Johnson","Davis",
              "Miller","Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White","Harris","Martin"]
    return f"{firsts[uid % len(firsts)]} {lasts[(uid//len(firsts)) % len(lasts)]}"

def email_from_name(name:str, uid:int)->str:
    base = name.lower().replace(" ",".")
    return f"{base}.{uid}@example.edu"

def partition_into_teams(num_students:int, min_team:int, max_team:int, rng:random.Random):
    """
    Partition num_students into team sizes between [min_team, max_team].
    Strategy: Start with floor(num/min_team) teams then distribute remainder
    without exceeding max_team; adjust with swaps if needed.
    """
    if num_students < min_team:
        return [num_students]  # single undersized team (rare edge case)
    # minimum number of teams
    t = max(1, num_students // max_team)  # lower bound
    # naive start: round to reasonable team count
    approx_teams = max(1, round(num_students / ((min_team+max_team)/2)))
    team_count = max(t, approx_teams)
    # build teams with min size
    sizes = [min_team]*team_count
    assigned = min_team * team_count
    while assigned < num_students:
        # randomly bump teams not yet at max
        idxs = list(range(team_count))
        rng.shuffle(idxs)
        progressed = False
        for i in idxs:
            if sizes[i] < max_team and assigned < num_students:
                sizes[i] += 1
                assigned += 1
                progressed = True
            if assigned >= num_students:
                break
        if not progressed:
            # cannot grow; add a new team (will be min_team or remainder)
            remain = num_students - assigned
            if remain <= 0:
                break
            add = min(max(remain, min_team), max_team)
            sizes.append(add)
            assigned += add
            team_count += 1
    # If we overshot, trim last team
    if assigned > num_students:
        overflow = assigned - num_students
        for i in range(team_count-1, -1, -1):
            take = min(overflow, sizes[i]-min_team)
            sizes[i] -= take
            overflow -= take
            if overflow == 0:
                break
    # final sanity
    assert sum(sizes) == num_students, f"partition failed: {sizes} vs {num_students}"
    return sizes

def biased_score(rng:random.Random, max_score:int=5):
    # Triangular bias towards higher scores
    a = rng.triangular(1, max_score, max_score)
    return max(1, min(max_score, int(round(a))))

def generate(level:int, outdir:Path, seed:int|None, semester:str):
    rng = random.Random(seed if seed is not None else 12345 + level)
    outdir.mkdir(parents=True, exist_ok=True)

    if level == 1:
        n_courses = 150
        stu_min, stu_max = 30, 80
        team_min, team_max = 4, 8
    elif level == 2:
        n_courses = 700
        stu_min, stu_max = 30, 80
        team_min, team_max = 4, 6
    elif level == 3:
        n_courses = 2000
        stu_min, stu_max = 30, 100
        team_min, team_max = 4, 6
    else:
        raise ValueError("level must be 1, 2, or 3")

    # IDs
    next_user_id = 1
    next_course_id = 1
    next_team_id = 1
    next_form_id = 1
    next_template_id = 1
    next_response_id = 1

    # Global containers
    users = []           # id, full_name, email, role
    courses = []         # id, code, title, semester, instructor_id
    enrollments = []     # course_id, user_id, role_in_course
    teams = []           # id, course_id, name
    team_members = []    # team_id, user_id
    eval_templates = []  # id, name, max_score
    eval_forms = []      # id, course_id, template_id, open_at, close_at
    eval_responses = []  # id, form_id, evaluator_id, evaluatee_id, team_id, q1..q5, comments

    # Create a single common template for simplicity (could create more)
    template_id = next_template_id; next_template_id += 1
    eval_templates.append([template_id, "Standard 5Q (1-5)", 5])

    today = datetime.date.today()
    open_at = datetime.datetime(today.year, 10, 1, 9, 0)   # Oct 1, 9:00
    close_at = datetime.datetime(today.year, 10, 31, 23, 59)

    for c in range(n_courses):
        # Create instructor
        instr_id = next_user_id; next_user_id += 1
        iname = name_from_id(instr_id)
        iemail = email_from_name(iname, instr_id)
        users.append([instr_id, iname, iemail, "instructor"])

        # Course
        course_id = next_course_id; next_course_id += 1
        code = f"CSE{1000+c:04d}"
        title = f"Course {c+1}: Systems & Testing"
        courses.append([course_id, code, title, semester, instr_id])
        enrollments.append([course_id, instr_id, "instructor"])

        # Students for this course
        num_students = rng.randint(stu_min, stu_max)
        student_ids = []
        for s in range(num_students):
            uid = next_user_id; next_user_id += 1
            sname = name_from_id(uid)
            semail = email_from_name(sname, uid)
            users.append([uid, sname, semail, "student"])
            enrollments.append([course_id, uid, "student"])
            student_ids.append(uid)

        # Create teams
        sizes = partition_into_teams(num_students, team_min, team_max, rng)
        rng.shuffle(student_ids)
        idx = 0
        course_team_ids = []
        for tsize in sizes:
            tid = next_team_id; next_team_id += 1
            tname = f"Team {len(course_team_ids)+1:02d}"
            teams.append([tid, course_id, tname])
            course_team_ids.append(tid)
            # assign members
            members = student_ids[idx:idx+tsize]
            for uid in members:
                team_members.append([tid, uid])
            idx += tsize

        # One eval form per course
        form_id = next_form_id; next_form_id += 1
        eval_forms.append([form_id, course_id, template_id, open_at.isoformat(), close_at.isoformat()])

        # Peer responses: each student evaluates all members of their own team (incl self? Usually exclude self)
        # We'll exclude self-evals by default.
        for tid in course_team_ids:
            members = [u for (t,u) in team_members if t == tid]
            for evaluator in members:
                for evaluatee in members:
                    if evaluatee == evaluator:
                        continue
                    q1 = biased_score(rng, 5)
                    q2 = biased_score(rng, 5)
                    q3 = biased_score(rng, 5)
                    q4 = biased_score(rng, 5)
                    q5 = biased_score(rng, 5)
                    rid = next_response_id; next_response_id += 1
                    comment_bits = [
                        "Strong contributor","Good communicator","Met deadlines",
                        "Needs to speak up more","Could improve documentation","Great leadership",
                        "Reliable teammate","Helped unblock issues","Attention to detail"
                    ]
                    comments = rng.choice(comment_bits)
                    eval_responses.append([rid, form_id, evaluator, evaluatee, tid, q1,q2,q3,q4,q5, comments])

    # Write CSVs
    def write_csv(path, header, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    outdir.mkdir(parents=True, exist_ok=True)
    write_csv(outdir/"users.csv", ["id","full_name","email","role"], users)
    write_csv(outdir/"courses.csv", ["id","code","title","semester","instructor_id"], courses)
    write_csv(outdir/"enrollments.csv", ["course_id","user_id","role_in_course"], enrollments)
    write_csv(outdir/"teams.csv", ["id","course_id","name"], teams)
    write_csv(outdir/"team_members.csv", ["team_id","user_id"], team_members)
    write_csv(outdir/"eval_templates.csv", ["id","name","max_score"], eval_templates)
    write_csv(outdir/"eval_forms.csv", ["id","course_id","template_id","open_at","close_at"], eval_forms)
    write_csv(outdir/"eval_responses.csv", ["id","form_id","evaluator_id","evaluatee_id","team_id","q1","q2","q3","q4","q5","comments"], eval_responses)

    # Simple validation
    # 1) Every team member must be enrolled student in that course
    enroll_set = {(c,u) for (c,u,role) in enrollments if role=="student"}
    team_course = {}
    for tid,cid,name in teams:
        team_course[tid] = cid
    for tid, uid in team_members:
        cid = team_course[tid]
        assert (cid, uid) in enroll_set, "Team member not enrolled as student"
    # 2) Response evaluator/evaluatee must be in same team
    team_membership = {}
    for tid, uid in team_members:
        team_membership.setdefault(tid, set()).add(uid)
    for (_, form_id, evaluator, evaluatee, tid, *_) in eval_responses:
        assert evaluator in team_membership[tid] and evaluatee in team_membership[tid], "Response across teams"
        assert evaluator != evaluatee, "Self-evaluation found but excluded by design"

    # Write a manifest JSON
    manifest = {
        "level": level,
        "semester": semester,
        "counts": {
            "users": len(users),
            "courses": len(courses),
            "enrollments": len(enrollments),
            "teams": len(teams),
            "team_members": len(team_members),
            "eval_templates": len(eval_templates),
            "eval_forms": len(eval_forms),
            "eval_responses": len(eval_responses)
        }
    }
    with open(outdir/"manifest.json","w",encoding="utf-8") as f:
        import json
        json.dump(manifest, f, indent=2)
    print(f"Wrote CSVs to {outdir} with summary:", manifest)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--level", type=int, required=True, choices=[1,2,3])
    p.add_argument("--out", type=str, required=True)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--semester", type=str, default="Fall 2025")
    args = p.parse_args()
    generate(args.level, Path(args.out), args.seed, args.semester)

if __name__ == "__main__":
    main()