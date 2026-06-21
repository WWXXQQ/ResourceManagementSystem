from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import CustomUser


class CustomLoginView(LoginView):
    template_name = 'login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        login_role = self.request.POST.get('login_role')
        roles = [role.strip() for role in (self.request.user.roles or '').split(',') if role.strip()]
        if login_role and login_role in roles:
            self.request.session['active_role'] = login_role
        return response


@login_required
def dashboard(request):
    return render(request, 'dashboard.html')


def get_user_roles_api(request):
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({'roles': []})
    try:
        user = CustomUser.objects.get(username=username)
    except CustomUser.DoesNotExist:
        return JsonResponse({'roles': []})
    roles = [role.strip() for role in (user.roles or '').split(',') if role.strip()]
    return JsonResponse({'roles': roles})
