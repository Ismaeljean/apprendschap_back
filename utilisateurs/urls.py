# utilisateurs/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UtilisateurViewSet, NiveauScolaireViewSet, PartenaireViewSet, CommissionViewSet, RetraitCommissionViewSet
from .views import CreationOfSuperHeros  # importe la nouvelle classe

router = DefaultRouter()
router.register('utilisateurs', UtilisateurViewSet, basename='utilisateur')
router.register('niveaux', NiveauScolaireViewSet, basename='niveau')
router.register('partenaires', PartenaireViewSet, basename='partenaire')
router.register('commissions', CommissionViewSet, basename='commission')
router.register('retraits', RetraitCommissionViewSet, basename='retrait')

urlpatterns = [
    path('', include(router.urls)),
    path('setup/creation-of-super-heros/', CreationOfSuperHeros.as_view(), name='creation_of_super_heros'),
]