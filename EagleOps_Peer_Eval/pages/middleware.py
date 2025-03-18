from django.shortcuts import redirect
from django.conf import settings

class NoSignupMiddleware:
    """
    Middleware to prevent redirects to the signup page and 
    instead redirect directly to the home page.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Check if response is a redirect to the signup page
        if hasattr(response, 'url') and '/accounts/3rdparty/signup/' in response.url:
            # Redirect to home instead
            return redirect(settings.LOGIN_REDIRECT_URL)
            
        return response 