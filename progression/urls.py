# progression/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from progression.views import ProgressionChapitreViewSet, ProgressionContenuViewSet, ProgressionMatiereViewSet

router = DefaultRouter()
router.register(r'chapitres', ProgressionChapitreViewSet, basename='progression-chapitre')
router.register(r'contenus', ProgressionContenuViewSet, basename='progression-contenu')
router.register(r'matieres', ProgressionMatiereViewSet, basename='progression-matiere')

urlpatterns = [
    path('', include(router.urls)),
    # Route directe pour les statistiques
    path('statistiques/', ProgressionChapitreViewSet.as_view({'get': 'statistiques'}), name='statistiques'),
    # Route pour les statistiques utilisateur
    path('statistiques-utilisateur/', ProgressionChapitreViewSet.as_view({'get': 'statistiques_utilisateur'}), name='statistiques_utilisateur'),
]

app_name = 'progression'
