from django.contrib import admin
from .models import UserProfile, Team, Course, FormTemplate, Question, Form, FormResponse, Answer
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Register the UserProfile model with the admin site
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'admin')
    list_filter = ('admin',)
    search_fields = ('user__username', 'user__email')
    
    def email(self, obj):
        return obj.user.email
    
    email.short_description = 'Email'

# Register your models here.
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Team)
admin.site.register(Course)

# Add UserProfile info to the User admin page
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'

# Add the UserProfileInline to the User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Register form related models
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1

class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'created_by', 'question_count', 'updated_at')
    search_fields = ('title', 'description')
    inlines = [QuestionInline]

class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'template', 'status', 'publication_date', 'closing_date')
    list_filter = ('status', 'course')
    search_fields = ('title',)
    filter_horizontal = ('teams',)

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question',)

class FormResponseAdmin(admin.ModelAdmin):
    list_display = ('form', 'evaluator', 'evaluatee', 'submitted', 'submission_date')
    list_filter = ('submitted', 'form')
    inlines = [AnswerInline]

admin.site.register(FormTemplate, FormTemplateAdmin)
admin.site.register(Question)
admin.site.register(Form, FormAdmin)
admin.site.register(FormResponse, FormResponseAdmin)
admin.site.register(Answer)
