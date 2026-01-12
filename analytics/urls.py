# analytics/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StatistiqueViewSet

router = DefaultRouter()
router.register('Statistique', StatistiqueViewSet, basename='Statistique')

urlpatterns = [
    path('', include(router.urls)),
]
