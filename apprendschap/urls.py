# apprendschap/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from drf_spectacular.views import (
    SpectacularAPIView,          # Pour le JSON/YAML brut
    SpectacularSwaggerView,      # L'interface Swagger UI interactive
    SpectacularRedocView,        # Alternative plus "livre" (Redoc)
)
from utilisateurs.views import CreationOfSuperHeros
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('utilisateurs.urls')),
    path('api/', include('abonnements.urls')),
    path('api/', include('academic_structure.urls')),
    path('api/', include('cours.urls')),
    path('api/', include('examens.urls')),
    path('api/', include('gamification.urls')),
    path('api/progression/', include('progression.urls')),
    path('api/', include('quiz.urls')),
    path('api/ia/', include('ia.urls')),
    
    # Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),                # JSON brut
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    path('setup/creation-of-super-heros/', CreationOfSuperHeros.as_view(), name='creation_of_super_heros'),
    
    
    # Frontend routes - SUPPRIMÉES car frontend et backend sont séparés
# path('abonnement/', TemplateView.as_view(template_name='abonnement.html'), name='abonnement'),
# path('', TemplateView.as_view(template_name='index.html'), name='index'),
]

# Servir les fichiers média en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)