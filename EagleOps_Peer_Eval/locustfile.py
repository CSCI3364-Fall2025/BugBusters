from locust import HttpUser, task, between
import random

class EagleOpsUser(HttpUser):
    wait_time = between(1, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Combined list of users
        self.user_emails = [
            # Teachers
            "jordan.rivera.1@example.edu",
            "parker.kim.72@example.edu", 
            "hayden.johnson.175@example.edu",
            "micah.miller.219@example.edu",
            # Students
            "taylor.rivera.2@example.edu",
            "morgan.rivera.3@example.edu", 
            "riley.rivera.4@example.edu",
            "casey.rivera.5@example.edu",
            "alex.nguyen.20@example.edu",
            "jordan.nguyen.21@example.edu",
        ]
        self.teacher_emails = [
            "jordan.rivera.1@example.edu",
            "parker.kim.72@example.edu", 
            "hayden.johnson.175@example.edu",
            "micah.miller.219@example.edu",
        ]
        self.password = "test123"
        self.course_ids = [1, 2, 3, 4, 5]
        self.form_ids = [1, 2, 3]
        self.email = None
        self.is_teacher = False

    def on_start(self):
        """Login when a user starts - using proper Django authentication"""
        self.email = random.choice(self.user_emails)
        self.is_teacher = self.email in self.teacher_emails
        
        # First, let's check if we need to get CSRF token from login page
        with self.client.get("/signin/", name="Get Login Page", catch_response=True) as response:
            if response.status_code == 200:
                # Try to extract CSRF token if your login form uses it
                csrf_token = self._extract_csrf_token(response.text)
                
                # Prepare login data
                login_data = {
                    "username": self.email,
                    "password": self.password,
                }
                
                # Add CSRF token if found
                if csrf_token:
                    login_data["csrfmiddlewaretoken"] = csrf_token
                
                # Attempt login
                with self.client.post("/signin/", 
                                    data=login_data,
                                    headers={"Referer": f"{self.host}/signin/"},
                                    name="Login",
                                    catch_response=True) as login_response:
                    
                    if login_response.status_code in [200, 302]:
                        # Check if we're actually logged in by accessing a protected page
                        with self.client.get("/courses/", name="Verify Login", catch_response=True) as verify_response:
                            if verify_response.status_code == 200:
                                login_response.success()
                                print(f"Successfully logged in as {self.email}")
                            else:
                                login_response.failure(f"Login verification failed: {verify_response.status_code}")
                    else:
                        login_response.failure(f"Login failed with status: {login_response.status_code}")
            else:
                response.failure(f"Could not access login page: {response.status_code}")

    def _extract_csrf_token(self, html_content):
        """Extract CSRF token from HTML content"""
        import re
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html_content)
        return match.group(1) if match else None

    @task(4)
    def load_courses_page(self):
        """Load the main courses page"""
        with self.client.get("/courses/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Courses failed: {response.status_code}")

    @task(3)
    def load_home_page(self):
        """Load home page"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Home failed: {response.status_code}")

    @task(3)
    def load_course_detail(self):
        """Load specific course detail"""
        course_id = random.choice(self.course_ids)
        with self.client.get(f"/courses/{course_id}/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Course detail failed: {response.status_code}")

    @task(2)
    def load_profile(self):
        """Load user profile"""
        with self.client.get("/profile/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Profile failed: {response.status_code}")

    @task(1)
    def teacher_specific_tasks(self):
        """Tasks only for teachers"""
        if self.is_teacher:
            course_id = random.choice(self.course_ids)
            
            # Randomly choose a teacher task
            teacher_tasks = [
                (f"/forms-dashboard/", "Forms dashboard"),
                (f"/courses/{course_id}/roster/", "Roster"),
                (f"/course/{course_id}/performance/", "Performance"),
            ]
            
            url, name = random.choice(teacher_tasks)
            with self.client.get(url, name=name, catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"{name} failed: {response.status_code}")

    @task(1)
    def student_specific_tasks(self):
        """Tasks only for students"""
        if not self.is_teacher:
            course_id = random.choice(self.course_ids)
            form_id = random.choice(self.form_ids)
            
            # Randomly choose a student task
            student_tasks = [
                (f"/courses/{course_id}/forms/{form_id}/evaluations/", "Form evaluations"),
                (f"/courses/join/", "Join course"),
            ]
            
            url, name = random.choice(student_tasks)
            with self.client.get(url, name=name, catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"{name} failed: {response.status_code}")