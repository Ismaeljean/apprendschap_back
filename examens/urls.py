# examens/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExamenViewSet, TypeExamenViewSet

router = DefaultRouter()
router.register('examens', ExamenViewSet, basename='examen')
router.register('types-examens', TypeExamenViewSet, basename='type-examen')

urlpatterns = [
    path('', include(router.urls)),
]
