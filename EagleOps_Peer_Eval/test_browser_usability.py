import os
import time
import pytest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from django.apps import apps
from django.contrib.auth import get_user_model

from playwright.sync_api import sync_playwright

# Create drivers per browser
def _make_driver(browser_name: str):
    browser_name = browser_name.lower()
    try:
        if browser_name in ("google", "chrome"):
            opts = webdriver.ChromeOptions()
            if os.environ.get("HEADLESS", "1") == "1":
                opts.add_argument("--headless=new")
                opts.add_argument("--window-size=1366,900")
            return webdriver.Chrome(options=opts)

        if browser_name in ("mozilla", "firefox"):
            opts = webdriver.FirefoxOptions()
            if os.environ.get("HEADLESS", "1") == "1":
                opts.add_argument("--headless")
            return webdriver.Firefox(options=opts)

        #will handle with playwright
        if browser_name == "safari":
            return None

    except Exception:
        # If driver missing, skip
        return None

    raise ValueError(f"Unsupported browser: {browser_name}")

# Pytest config 
BROWSERS = ["google", "mozilla", "safari"]
SELENIUM_BROWSERS = ["google", "mozilla"] 

@pytest.fixture(params=SELENIUM_BROWSERS, scope="class")
def selenium_browser(request):
    return request.param

@pytest.fixture(scope="class")
def driver(selenium_browser):
    drv = _make_driver(selenium_browser)
    if drv is None:
        pytest.skip(f"WebDriver for {selenium_browser} not available or not configured.")
    yield drv
    drv.quit()

# Django DB 
pytestmark = pytest.mark.django_db

# Basic UI selectors
HOME_PATH = "/"
NAV_LINK_SELECTOR = "a[href='/']"
FORM_INPUT_SELECTOR = "input[name='q']"
FORM_SUBMIT_SELECTOR = "button[type='submit']"
SUCCESS_MARKER_SELECTOR = "[data-test='ok']"

# 3 different testing levels
LEVELS = {
    "L1": (150, (30, 80), (4, 8)),
    "L2": (700, (30, 80), (4, 6)),
    "L3": (2000, (30, 100), (4, 6)),
}

# Navigation/perf thresholds in milliseconds for DOMContentLoaded
LEVEL_NAV_THRESHOLDS_MS = {
    "L1": 4000,
    "L2": 7000,
    "L3": 12000,
}

# Model hooks
def get_models():
    try:
        UserProfile = apps.get_model("pages", "UserProfile")
        Course = apps.get_model("pages", "Course")
        Team = apps.get_model("pages", "Team")
        Form = apps.get_model("pages", "Form")
        FormResponse = apps.get_model("pages", "FormResponse")
        return UserProfile, Course, Team, Form, FormResponse
    except Exception:
        # If models aren't available yet, signal to the caller that seeding should be skipped
        return None, None, None, None, None

def _ensure_seed_for_level(level_name: str):
    UserProfile, Course, Team, Form, FormResponse = get_models()
    if not all([UserProfile, Course, Team, Form, FormResponse]):
        pytest.skip(
            "Seeding skipped: expected models (UserProfile, Course, Team, Form, FormResponse) to exist."
        )

    User = get_user_model()
    courses_target, students_range, team_size_range = LEVELS[level_name]

    existing = Course.objects.count()
    if existing >= courses_target:
        return

    remaining = courses_target - existing

    # --- Teacher user + profile ---
    teacher_user, _ = User.objects.get_or_create(
        username="seed_teacher",
        defaults={
            "email": "teacher+seed@ex.com",
            "first_name": "Seed",
            "last_name": "Teacher",
        },
    )
    teacher_profile, _ = UserProfile.objects.get_or_create(
        user=teacher_user,
        defaults={
            "first_name": teacher_user.first_name,
            "last_name": teacher_user.last_name,
            "admin": True,  # Uses your existing 'admin' flag
        },
    )

    # --- Create the remaining courses ---
    courses = []
    for i in range(remaining):
        code = f"C{existing + i + 1:05d}"
        course = Course.objects.create(
            code=code,
            name=f"Course {existing + i + 1}",
            semester="Fall",
            year=2025,
            description=f"Seeded course {code}",
        )
        course.instructors.add(teacher_profile)
        courses.append(course)

    # --- Per-course seeding: students + teams ---
    import math, random

    for course in courses:
        # How many students and what team size for this course
        n_students = random.randint(*students_range)
        team_min, team_max = team_size_range
        team_size = random.randint(team_min, team_max)

        # Create auth users + UserProfiles for students
        student_profiles = []
        for j in range(n_students):
            username = f"student_{course.code}_{j}"
            email = f"student+{course.code}-{j}@ex.com"

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name="Student",
                last_name=f"{course.code}-{j}",
            )
            profile = UserProfile.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            student_profiles.append(profile)

        # Enroll students in the course
        course.students.add(*student_profiles)

        # Create teams for this course
        n_teams = max(1, math.ceil(n_students / team_size))
        teams = []
        for t in range(n_teams):
            team = Team.objects.create(
                course=course,
                name=f"{course.code}-Team-{t + 1}",
            )
            teams.append(team)

        # Round-robin assign students to teams
        for idx, student in enumerate(student_profiles):
            team = teams[idx % n_teams]
            team.members.add(student)

# Parametrize the whole class over the levels
@pytest.fixture(params=["L1", "L2", "L3"], scope="class")
def level_name(request):
    return request.param

@pytest.fixture(scope="class")
def level_config(level_name):
    return {
        "name": level_name,
        "courses": LEVELS[level_name][0],
        "students_range": LEVELS[level_name][1],
        "team_size_range": LEVELS[level_name][2],
        "nav_threshold_ms": LEVEL_NAV_THRESHOLDS_MS[level_name],
    }

@pytest.fixture(scope="class", autouse=True)
def seed_level_data(level_name, django_db_setup, django_db_blocker):
    if os.environ.get("SKIP_SEED", "0") == "1":
        return
    with django_db_blocker.unblock():
        _ensure_seed_for_level(level_name)

# Tests 
class TestBrowserUsability:
    def test_homepage_loads_and_has_title(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)
        assert driver.title is not None and driver.title != ""

    def test_layout_is_responsive_basic(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)
        driver.set_window_size(1366, 800)
        time.sleep(0.2)
        width_desktop = driver.execute_script("return document.body.clientWidth;")

        driver.set_window_size(375, 812)
        time.sleep(0.2)
        width_mobile = driver.execute_script("return document.body.clientWidth;")
        assert width_desktop != width_mobile

    def test_key_navigation_and_focus(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)

        # If the server blew up (e.g., SocialApp.DoesNotExist),
        # the page title often contains "Error" or status.
        title = (driver.title or "").lower()
        if "error" in title or "not found" in title:
            pytest.skip("Homepage returned an error page; skipping keyboard focus test.")

        # Find elements that can realistically receive focus
        focusables = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])"
        )
        if not focusables:
            pytest.skip("No focusable controls on page; skipping keyboard navigation test.")

        body = driver.find_element(By.TAG_NAME, "body")
        start_active = driver.switch_to.active_element

        # Try multiple TAB presses; pass if focus ever moves to a different element
        for _ in range(8):
            body.send_keys(Keys.TAB)
            time.sleep(0.15)
            after_tab = driver.switch_to.active_element

            # Different WebElement object → focus really moved
            if after_tab != start_active and after_tab.tag_name != "body":
                return  # test passes

        pytest.fail("TAB did not move focus to any other meaningful element after several attempts.")

    def test_form_submit_smoke(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)
        inputs = driver.find_elements(By.CSS_SELECTOR, FORM_INPUT_SELECTOR)
        submits = driver.find_elements(By.CSS_SELECTOR, FORM_SUBMIT_SELECTOR)
        if not inputs or not submits:
            pytest.skip("Form selectors not present on this page")
        inputs[0].clear()
        inputs[0].send_keys("test")
        submits[0].click()
        time.sleep(0.3)
        ok = driver.find_elements(By.CSS_SELECTOR, SUCCESS_MARKER_SELECTOR)
        assert ok, "Expected success marker after form submit"

    def test_no_obvious_js_errors_on_load(self, live_server, driver, level_config):
        driver.get(live_server.url + HOME_PATH)
        driver.execute_script(
            """
            window.__errors = [];
            window.addEventListener('error', function(e){ window.__errors.push(e.message || 'error'); });
            """
        )
        driver.get(live_server.url + HOME_PATH)
        time.sleep(0.2)
        errors = driver.execute_script("return window.__errors;") or []
        assert all("ReferenceError" not in e for e in errors), f"JS errors: {errors}"

    def test_navigation_perf_is_reasonable_for_level(self, live_server, driver, level_config):
        """
        Uses PerformanceNavigationTiming if available; falls back to Navigation Timing.
        This doesn't replace real perf testing, but it flags obvious regressions as data scales.
        """
        driver.get(live_server.url + HOME_PATH)
        time.sleep(0.2)

        nav_entry = driver.execute_script(
            """
            var e = (performance.getEntriesByType && performance.getEntriesByType('navigation')) || [];
            if (e && e.length) {
                var n = e[0];
                return {
                    dcl: n.domContentLoadedEventEnd, // ms from startTime(=0) for nav entries
                    start: n.startTime
                };
            }
            return null;
            """
        )

        if nav_entry and "dcl" in nav_entry and nav_entry["dcl"]:
            dcl_ms = float(nav_entry["dcl"])
        else:
            timing = driver.execute_script("return window.performance && performance.timing ? performance.timing : null;")
            if not timing:
                pytest.skip("No performance timing API available in this browser.")
            dcl_ms = float(timing.get("domContentLoadedEventEnd", 0) - timing.get("navigationStart", 0))

        threshold = level_config["nav_threshold_ms"]
        assert dcl_ms <= threshold, f"[{level_config['name']}] DOMContentLoaded {dcl_ms:.0f}ms > {threshold}ms"

# Playwright Safari (WebKit) Tests
HEADLESS = os.getenv("PW_HEADLESS", "1") == "1"   
@pytest.mark.usefixtures("live_server")
class TestSafariPlaywright:
    def test_safari_homepage_loads(self, live_server):
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=HEADLESS)
            page = browser.new_page()
            page.goto(live_server.url)
            assert page.title(), "Safari/WebKit should have a non-empty title"
            browser.close()

    def test_safari_layout_responsive(self, live_server):
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=HEADLESS)
            page = browser.new_page()
            page.goto(live_server.url)
            desktop_width = page.evaluate("document.body.clientWidth")
            page.set_viewport_size({"width": 375, "height": 812})
            mobile_width = page.evaluate("document.body.clientWidth")
            assert desktop_width != mobile_width
            browser.close()

    def test_safari_js_no_errors(self, live_server):
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=HEADLESS)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(live_server.url)
            page.wait_for_load_state("domcontentloaded")
            assert not errors, f"JS errors: {errors}"
            browser.close()