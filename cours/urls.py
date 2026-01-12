# cours/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from cours.views import ChapitreViewSet, ContenuChapitreViewSet, youtube_meta

router = DefaultRouter()
router.register(r'chapitres', ChapitreViewSet, basename='chapitre')
router.register(r'contenus', ContenuChapitreViewSet, basename='contenu-chapitre')

urlpatterns = [
    path('', include(router.urls)),
    path('youtube/meta/', youtube_meta, name='youtube-meta'),
]