# apprendschap/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView


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
    
    # Frontend routes - SUPPRIMÉES car frontend et backend sont séparés
# path('abonnement/', TemplateView.as_view(template_name='abonnement.html'), name='abonnement'),
# path('', TemplateView.as_view(template_name='index.html'), name='index'),
]

# Servir les fichiers média en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)