# academic_structure/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatiereViewSet, NiveauScolaireViewSet

router = DefaultRouter()
router.register(r'NiveauScolaire', NiveauScolaireViewSet, basename='NiveauScolaire')
router.register(r'Matiere', MatiereViewSet, basename='Matiere')

urlpatterns = [
    path('', include(router.urls)),
]
