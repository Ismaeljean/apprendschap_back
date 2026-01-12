# examens/models.py
from django.db import models
from academic_structure.models import Matiere


class TypeExamen(models.Model):
    """Types d'examens (BAC, BEPC, CEPE, etc.)"""
    nom = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.nom


class Examen(models.Model):
    """Archive des examens par année et session"""
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    type_examen = models.ForeignKey(
        TypeExamen,
        on_delete=models.CASCADE,
        related_name='examens'  # ✅ Relation inverse claire
    )
    titre = models.CharField(max_length=200)
    annee = models.PositiveIntegerField()
    session = models.CharField(max_length=20, choices=[
        ('juin', 'Juin'),
        ('septembre', 'Septembre'),
        ('rattrapage', 'Rattrapage')
    ])
    duree_heures = models.FloatField()
    points_total = models.PositiveIntegerField()
    difficulte = models.CharField(max_length=20, choices=[
        ('facile', 'Facile'),
        ('moyen', 'Moyen'),
        ('difficile', 'Difficile')
    ])
    description = models.TextField(blank=True)
    fichier_sujet = models.FileField(upload_to='examens/sujets/')
    fichier_correction = models.FileField(upload_to='examens/corrections/', blank=True, null=True)
    nombre_telechargements = models.PositiveIntegerField(default=0)
    date_ajout = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['-annee', 'matiere__nom']
        unique_together = ['matiere', 'type_examen', 'annee', 'session']

    def __str__(self):
        return f"{self.type_examen.nom} {self.matiere.nom} {self.annee}"
