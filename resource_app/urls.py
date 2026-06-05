from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('apply/', views.apply_view, name='apply'),
    path('approve/', views.approve_view, name='approve'),
    path('execute/', views.execute_view, name='execute'),
    path('assets/', views.asset_management_view, name='assets'),
    path('statistics/', views.statistics_view, name='statistics'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('api/inventory/', views.inventory_api, name='inventory_api'),
    path('remind/', views.remind_view, name='remind'),
    path('mock-notification-api/', views.mock_notification_api, name='mock_notification_api'),
    path('assets/password/', views.get_asset_password, name='get_asset_password'),
    path('api/application/details/', views.get_application_details, name='get_application_details'),
    path('api/user/roles/', views.get_user_roles_api, name='get_user_roles_api'),
    
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
]
