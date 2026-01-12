# academic_structure/models.py
from django.db import models

class NiveauScolaire(models.Model):
    """Niveaux scolaires (6ème, 5ème, etc.)"""
    nom = models.CharField(max_length=50, unique=True)
    ordre = models.PositiveIntegerField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['ordre']
        verbose_name = "Niveau scolaire"
        verbose_name_plural = "Niveaux scolaires"

    def __str__(self):
        return self.nom    

class Matiere(models.Model):
    """Matières par niveau scolaire"""
    niveau = models.ForeignKey(NiveauScolaire, on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    icone = models.CharField(max_length=50)
    couleur = models.CharField(max_length=7)
    ordre = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['niveau__ordre', 'ordre']
        unique_together = ['nom', 'niveau']

    def __str__(self):
        return f"{self.nom} - {self.niveau.nom}"