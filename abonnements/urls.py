# abonnements/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'packs', views.PackAbonnementViewSet, basename='pack')
# router.register(r'packs-familiaux', views.PackFamilialViewSet, basename='pack-familial')  # Désactivé car conflit avec endpoint personnalisé
router.register(r'abonnements', views.AbonnementViewSet, basename='abonnement')
router.register(r'parrainage', views.ParrainageViewSet, basename='parrainage')

urlpatterns = [
    # Paiement Wave - AVANT le router pour éviter les conflits
    path('paiement-wave/', views.initier_paiement_wave, name='paiement-wave'),
    path('paiement-wave-enfant/', views.initier_paiement_wave_enfant, name='paiement-wave-enfant'),
    path('paiement-wave-familial/', views.initier_paiement_wave_famille, name='paiement-wave-familial'),
    # Packs spéciaux
    path('packs-speciaux/', views.get_packs_speciaux, name='packs-speciaux'),
    # Packs standards
    path('packs-standards/', views.get_packs_standards, name='packs-standards'),
    # Tous les packs
    path('packs-tous/', views.get_all_packs, name='packs-tous'),
    # Packs familiaux uniquement - AVANT le router pour éviter les conflits
    path('packs-familiaux/', views.get_packs_familiaux, name='packs-familiaux'),
    # Callback Wave (doit rester séparé car pas d'authentification)
    path('abonnements/wave-callback/', views.wave_callback, name='wave-callback'),
    # Router Django REST Framework
    path('', include(router.urls)),
    # Endpoints spécifiques
    path('souscrire-pack-famille/', views.PackFamilialViewSet.as_view({'post': 'souscrire_pack_famille'}), name='souscrire-pack-famille'),
]
