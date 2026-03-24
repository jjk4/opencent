from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import translation

class FirstRunSetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setup_url = reverse('first_run_setup')
        
        allowed_prefixes = ('/static/', '/media/', '/i18n/')
        
        if request.path.startswith(allowed_prefixes):
             return self.get_response(request)

        if request.path == setup_url:
            return self.get_response(request)

        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            return redirect('first_run_setup')

        return self.get_response(request)


class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'settings'):
            user_language = request.user.settings.language
            
            translation.activate(user_language)
            request.LANGUAGE_CODE = translation.get_language()
            
        response = self.get_response(request)
        
        return response