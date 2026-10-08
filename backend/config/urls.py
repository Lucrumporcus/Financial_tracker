from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from finance.views import RegistrationView
from finance import web_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', web_views.dashboard_page, name='dashboard'),
    path('login/', web_views.login_page, name='login'),
    path('register/', web_views.register_page, name='register_page'),
    path('logout/', web_views.logout_page, name='logout'),
    path('groups/', web_views.groups_page, name='groups_page'),
    path('operations/', web_views.operations_page, name='operations_page'),
    path('statistics/', web_views.statistics_page, name='statistics_page'),

    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/register/', RegistrationView.as_view(), name='register'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/', include('finance.urls')),
]
