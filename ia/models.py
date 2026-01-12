# ia/models.py
from django.db import models
from utilisateurs.models import Utilisateur
from cours.models import Chapitre
import uuid

class ConversationIA(models.Model):
    """Conversations avec l'IA par étudiant"""
    etudiant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    titre = models.CharField(max_length=200, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    derniere_activite = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-derniere_activite']
        verbose_name = "Conversation IA"
        verbose_name_plural = "Conversations IA"

    def __str__(self):
        return f"Conversation {self.etudiant.email} - {self.date_creation.strftime('%d/%m/%Y')}"


class MessageIA(models.Model):
    """Messages dans les conversations IA"""
    conversation = models.ForeignKey(ConversationIA, on_delete=models.CASCADE, related_name='messages')
    expediteur = models.CharField(max_length=20, choices=[
        ('etudiant', 'Étudiant'),
        ('ia', 'IA')
    ])
    contenu = models.TextField()
    contexte_chapitre = models.ForeignKey(Chapitre, on_delete=models.SET_NULL, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Message IA"
        verbose_name_plural = "Messages IA"

    def __str__(self):
        return f"{self.expediteur} - {self.timestamp.strftime('%H:%M')}"