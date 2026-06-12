from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='drill/login.html'),
         name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password/', auth_views.PasswordChangeView.as_view(
        template_name='drill/password_change.html',
        success_url=reverse_lazy('password_change_done')), name='password_change'),
    path('password/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='drill/password_change_done.html'), name='password_change_done'),
    path('practice/', views.practice, name='practice'),
    path('practice/custom/', views.practice_custom, name='practice_custom'),
    path('select/', views.select_facts, name='select_facts'),
    path('progress/', views.progress, name='progress'),
    path('manage/', views.manage, name='manage'),
    path('report/<str:username>/', views.report, name='report'),
    path('theme/', views.set_theme, name='set_theme'),
    path('api/next/', views.api_next, name='api_next'),
    path('api/answer/', views.api_answer, name='api_answer'),
]
