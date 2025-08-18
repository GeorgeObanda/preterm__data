from django.urls import path
from . import views

app_name = 'tracking'

urlpatterns = [
    # Home & Blog
    path('', views.index, name='index'),  # root URL
    path('blog/', views.blog, name='blog'),

    # Authentication
    path('signup/', views.signup, name='signup'),
    path('login/ra/', views.RAloginView.as_view(), name='ra_login'),
    path('login/ro/', views.ROloginView.as_view(), name='ro_login'),
    path('logout/', views.custom_logout_view, name='custom_logout_view'),
    path('auto-logout/', views.auto_logout_view, name='auto_logout'),

    # Dashboards
    path('choose-dashboard/', views.choose_dashboard, name='choose_dashboard'),
    path('choose-dashboard/download-pdf/', views.download_completed_pdf, name='download_completed_pdf'),
    path('dashboard/ra/', views.ra_dashboard, name='ra_dashboard'),
    path('dashboard/ro/', views.ro_dashboard, name='ro_dashboard'),

    # Participant management
    path('participant/register/', views.register_participant, name='register_participant'),
    path('participant/<int:pk>/', views.participant_detail, name='participant_detail'),
    path('participant/<int:pk>/update/', views.update_participant, name='update_participant'),
    path('participant/<int:pk>/monitor/', views.mark_monitor_downloaded, name='mark_monitor_downloaded'),
    path('participant/<int:pk>/ultrasound/', views.mark_ultrasound_downloaded, name='mark_ultrasound_downloaded'),

    # Admin user approval/rejection
    path('user/<int:user_id>/approve/', views.approve_user, name='approve_user'),
    path('user/<int:user_id>/reject/', views.reject_user, name='reject_user'),
]
