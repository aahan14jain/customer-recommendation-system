"""
URL configuration for customer_prediction_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)


def home(request):
    return JsonResponse({
        'message': 'Customer Prediction System API',
        'endpoints': {
            'admin': '/admin/',
            'api': '/api/',
            'auth_login': '/api/auth/login/',
            'auth_refresh': '/api/auth/refresh/',
            'auth_logout': '/api/auth/logout/',
            'customers': '/api/customers/',
            'transactions': '/api/transactions/',
            'recommendations_me': '/api/recommendations/me/',
        }
    })


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/', include('predictor.urls')),
]
