from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
]
