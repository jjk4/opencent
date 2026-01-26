from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model

class FirstRunSetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setup_url = reverse('first_run_setup')
        
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
             return self.get_response(request)

        if request.path == setup_url:
            return self.get_response(request)

        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            return redirect('first_run_setup')

        return self.get_response(request)