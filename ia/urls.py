# ia/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ConversationIAViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationIAViewSet, basename='conversation-ia')

urlpatterns = [
    path('poser-question/', ConversationIAViewSet.as_view({'post': 'envoyer_message'}), name='poser-question'),
] + router.urls