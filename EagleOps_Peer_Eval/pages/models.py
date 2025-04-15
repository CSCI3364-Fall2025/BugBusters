from django.contrib.auth.models import User
from django.db import models
from django.core.exceptions import ValidationError

from django.utils import timezone
from datetime import timedelta

class UserProfile(models.Model):
    """
    Extended user profile that links to Django's built-in User model.
    Provides additional fields for user information and permissions.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # link default user model to custom UserProfile model
    first_name = models.CharField(max_length=100, blank=True, null=True)  # Store first name
    last_name = models.CharField(max_length=100, blank=True, null=True)  # Store last name
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)  # Store user avatar
    bio = models.TextField(blank=True, null=True)  # New field for user bio
    admin = models.BooleanField(default=False)  # Admin field to denote if user is admin or not

    def __str__(self):
        return self.user.username
    
    @property
    def full_name(self):
        """
        Returns the user's full name if both first and last name are provided,
        otherwise returns the username.
        """
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else self.user.username
    
class Team(models.Model):
    """
    Represents a team of users within a specific course.
    Teams belong to exactly one course and cannot exist independently.
    """
    name = models.CharField(max_length=100)
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='teams')
    members = models.ManyToManyField(UserProfile, related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.course.code}"
    
    class Meta:
        unique_together = ['name', 'course']  # Prevent duplicate team names within the same course

class Course(models.Model):
    """
    Represents an academic course with teams, instructors and associated forms.
    Teams are now a child entity of courses rather than a many-to-many relationship.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    course_join_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    instructors = models.ManyToManyField(UserProfile, related_name='instructor_courses')
    students = models.ManyToManyField(UserProfile, related_name='enrolled_courses', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code}: {self.name}"
        
    def save(self, *args, **kwargs):
        # Generate a unique join code if one doesn't exist
        if not self.course_join_code:
            self.course_join_code = self.generate_unique_join_code()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_unique_join_code():
        """Generate a unique 8-character alphanumeric code"""
        import random
        import string
        
        while True:
            # Generate a random 8-character code
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Check if this code already exists
            if not Course.objects.filter(course_join_code=code).exists():
                return code

class FormTemplate(models.Model):
    """
    Template for peer evaluation forms that can be reused multiple times.
    Contains questions and can be duplicated.
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='created_templates')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='form_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    @property
    def question_count(self):
        """Returns the total number of questions in this template"""
        return self.questions.count()
    
    def duplicate(self):
        """
        Creates a copy of this template with '(Copy)' appended to the title.
        Also duplicates all associated questions.
        """
        new_template = FormTemplate.objects.create(
            title=f"{self.title} (Copy)",
            description=self.description,
            created_by=self.created_by,
            course=self.course
        )
        
        # Duplicate all questions
        for question in self.questions.all():
            Question.objects.create(
                template=new_template,
                text=question.text,
                question_type=question.question_type,
                order=question.order
            )
            
        return new_template

class Question(models.Model):
    """
    Represents a question within a form template.
    Can be either Likert scale (1-5) or open-ended.
    """
    LIKERT_SCALE = 'likert'
    OPEN_ENDED = 'open'
    
    QUESTION_TYPES = [
        (LIKERT_SCALE, 'Likert Scale (1-5)'),
        (OPEN_ENDED, 'Open-ended'),
    ]
    
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default=LIKERT_SCALE)
    order = models.IntegerField(default=0)  # For controlling the display order
    
    class Meta:
        ordering = ['order']  # Questions are always ordered by their order field
    
    def __str__(self):
        return f"{self.text[:50]}..." if len(self.text) > 50 else self.text

class Form(models.Model):
    """
    An actual peer evaluation form assigned to teams with a specific template.
    Has status that changes based on publication and closing dates.
    """
    # Form status constants
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    ACTIVE = 'active'
    CLOSED = 'closed'
    
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (SCHEDULED, 'Scheduled'),
        (ACTIVE, 'Active'),
        (CLOSED, 'Closed'),
    ]
    
    title = models.CharField(max_length=200)
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='forms')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='forms')
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='created_forms')
    teams = models.ManyToManyField(Team, related_name='assigned_forms')
    self_assessment = models.BooleanField(default=False)  # Whether users can evaluate themselves
    publication_date = models.DateTimeField()  # When the form becomes visible to users
    closing_date = models.DateTimeField()  # When the form stops accepting responses
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

    def clean(self):
        """
        Validate form before saving.
        """
        from django.utils import timezone

        super().clean()
        now = timezone.now()

        # Only validate if the form has an ID (meaning it already exists)
        if self.pk is not None:
            # Ensure all assigned teams belong to the course
            for team in self.teams.all():
                if team.course.id != self.course.id:
                    raise ValidationError(
                        f"Team '{team.name}' does not belong to course '{self.course.name}'. Teams must belong to the same course as the form."
                    )

            # Custom validation: for self-assessment, check teams
            if self.self_assessment:
                for team in self.teams.all():
                    if team.members.count() < 2:
                        raise ValidationError(
                            f"Team '{team.name}' does not have enough members for self-assessment."
                        )

            # Prevent changing publication_date if it's already passed and the form is active or closed
            try:
                existing = Form.objects.get(pk=self.pk)
                if existing.publication_date < now and self.publication_date != existing.publication_date:
                    # Ensure that publication date cannot be changed if form is already published
                    if existing.status in [Form.ACTIVE, Form.CLOSED]:
                        raise ValidationError("You cannot change the publication date after it has passed.")
            except Form.DoesNotExist:
                pass  # No existing record found, likely during initial creation

        # Ensure publish date is before closing date
        if self.publication_date and self.closing_date:
            if self.publication_date >= self.closing_date:
                raise ValidationError("Publication date must be before closing date.")
        
    def save(self, *args, **kwargs):
        """
        Override save method to automatically update status based on dates.
        Draft status is only changed if the form is not in draft mode.
        """

        self.full_clean()  # Validate the model before saving

        # Update status based on dates if status isn't being explicitly set
        now = timezone.now()
        
        # Only auto-update status if it's not in draft mode
        # and the status isn't being explicitly changed
        force_status = kwargs.pop('force_status', False)
        if not force_status and self.status != self.DRAFT:
            if now < self.publication_date:
                self.status = self.SCHEDULED
            elif now >= self.publication_date and now < self.closing_date:
                self.status = self.ACTIVE
            elif now >= self.closing_date:
                self.status = self.CLOSED
                
        super().save(*args, **kwargs)

    @property
    def completion_rate(self):
        """
        Returns the completion rate as a string (e.g., '15/20 completed')
        Calculates based on team members and whether self-assessment is enabled.
        """
        total_expected = 0
        for team in self.teams.all():
            member_count = team.members.count()
            if self.self_assessment:
                # Each member evaluates themselves and all team members
                total_expected += member_count * member_count
            else:
                # Each member evaluates all team members except themselves
                total_expected += member_count * (member_count - 1)
        
        completed = self.responses.filter(submitted=True).count()
        return f"{completed}/{total_expected} completed"
    
    def time_left(self):
        """
        Returns the time left until the closing date in a human-readable format.
        """
        now = timezone.now()
        time_left = self.closing_date - now
        
        if time_left <= timedelta(0):  # If the time left is 0 or negative (already closed)
            return "Closed"
        
        days_left = time_left.days
        hours_left = time_left.seconds // 3600
        minutes_left = (time_left.seconds // 60) % 60
        
        # Format the remaining time as "X days, Y hours, Z minutes"
        return f"{days_left} days, {hours_left} hours, and {minutes_left} minutes."
    
    def unpublish(self):
        """
        Reverts form to draft state and makes it unavailable to users.
        """
        self.status = self.DRAFT
        self.save(force_status=True)

class FormResponse(models.Model):
    """
    Represents a single evaluation response from one user about another.
    Contains the relationship between evaluator and evaluatee and their answers.
    """
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='responses')
    evaluator = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='evaluations_given')
    evaluatee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='evaluations_received')
    submitted = models.BooleanField(default=False)  # Whether the evaluation is complete
    submission_date = models.DateTimeField(null=True, blank=True)  # When it was submitted
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['form', 'evaluator', 'evaluatee']  # Each person can only evaluate another once per form
    
    def __str__(self):
        return f"{self.evaluator} evaluating {self.evaluatee} for {self.form}"
    
    def submit(self):
        """Marks the response as submitted and records the submission date"""
        # Only set the submission date if this is the first submission
        if not self.submitted:
            self.submitted = True
            self.submission_date = timezone.now()
            self.save()
        else:
            # If already submitted, just save the updated answers
            self.save()

class Answer(models.Model):
    """
    Individual answer to a specific question within a form response.
    Can store either a Likert scale rating (1-5) or text response.
    """
    response = models.ForeignKey(FormResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    likert_answer = models.IntegerField(null=True, blank=True)  # For Likert scale questions
    text_answer = models.TextField(null=True, blank=True)  # For open-ended questions
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['response', 'question']  # Only one answer per question per response
    
    def __str__(self):
        if self.question.question_type == Question.LIKERT_SCALE:
            return f"Rating: {self.likert_answer}"
        else:
            return f"Text: {self.text_answer[:50]}..." if self.text_answer and len(self.text_answer) > 50 else f"Text: {self.text_answer}"