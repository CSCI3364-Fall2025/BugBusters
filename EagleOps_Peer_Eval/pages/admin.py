from django.contrib import admin
from .models import UserProfile
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

# Add UserProfile info to the User admin page
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'

# Define a new User admin that includes the UserProfile
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, )

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
