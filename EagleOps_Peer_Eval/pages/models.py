from django.contrib.auth.models import User
from django.db import models

from django.utils import timezone

class UserProfile(models.Model):
    """
    Extended user profile that links to Django's built-in User model.
    Provides additional fields for user information and permissions.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    admin = models.BooleanField(default=False)  # Determines if user has admin privileges

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
    Represents a team of users that can be assigned to courses and assessments.
    """
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(UserProfile, related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Course(models.Model):
    """
    Represents an academic course with teams, instructors and associated forms.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    teams = models.ManyToManyField(Team, related_name='courses', blank=True)
    instructors = models.ManyToManyField(UserProfile, related_name='instructor_courses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code}: {self.name}"

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
    
    def save(self, *args, **kwargs):
        """
        Override save method to automatically update status based on dates.
        Draft status is only changed if the form is not in draft mode.
        """
        # Update status based on dates
        now = timezone.now()
        
        if self.status != self.DRAFT:
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
        self.submitted = True
        self.submission_date = timezone.now()
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