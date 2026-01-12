# quiz/urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import QuizViewSet

router = DefaultRouter()
router.register('quiz', QuizViewSet, basename='quiz')


urlpatterns = [
    path('', include(router.urls)),
]
