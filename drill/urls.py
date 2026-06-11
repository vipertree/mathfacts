from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='drill/login.html'),
         name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('practice/', views.practice, name='practice'),
    path('progress/', views.progress, name='progress'),
    path('report/<str:username>/', views.report, name='report'),
    path('theme/', views.set_theme, name='set_theme'),
    path('api/next/', views.api_next, name='api_next'),
    path('api/answer/', views.api_answer, name='api_answer'),
]
