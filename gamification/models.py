# gamification/models.py
from django.db import models
from utilisateurs.models import Utilisateur

class Badge(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    condition_type = models.CharField(max_length=30, choices=[
        ('chapitres_termines', 'Chapitres terminés'),
        ('quiz_parfait', 'Quiz parfait'),
        ('quiz_reussis', 'Quiz réussis'),
        ('temps_etude', 'Temps d\'étude'),
        ('progression_matiere', 'Progression matière'),
        ('matiere_complete', 'Matière complète'),
        ('matieres_terminees', 'Matières terminées'),
        ('programme_complet', 'Programme complet'),
        ('premier_chapitre', 'Premier chapitre')
    ])
    condition_valeur = models.PositiveIntegerField()
    points = models.PositiveIntegerField(default=10)
    icone = models.CharField(max_length=50, default='fa-trophy', help_text="Icône FontAwesome (ex: fa-star)")
    couleur = models.CharField(max_length=20, default='warning', help_text="Couleur Bootstrap (primary, success, warning, etc.)")
    ordre = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage")
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom

class BadgeEtudiant(models.Model):
    etudiant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='etudiants')
    date_obtention = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['etudiant', 'badge']
        verbose_name = "Badge étudiant"
        verbose_name_plural = "Badges étudiants"

    def __str__(self):
        return f"{self.etudiant.email} - {self.badge.nom}"