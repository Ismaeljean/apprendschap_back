# cours/models.py
from django.db import models
from academic_structure.models import Matiere


class Chapitre(models.Model):
    """Chapitres de cours par matière"""
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='chapitres')    
    titre = models.CharField(max_length=200)
    numero = models.PositiveIntegerField()
    description = models.TextField()
    duree_estimee = models.PositiveIntegerField()
    difficulte = models.CharField(max_length=20, choices=[
        ('facile', 'Facile'),
        ('moyen', 'Moyen'),
        ('difficile', 'Difficile')
    ])
    prerequis = models.ManyToManyField('self', blank=True, symmetrical=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['matiere', 'numero']
        unique_together = ['matiere', 'numero']

    def __str__(self):
        return f"Ch.{self.numero} - {self.titre}"



class ContenuChapitre(models.Model):
    """Contenu spécifique de chaque chapitre"""
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name='contenus')
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    fichier_pdf = models.FileField(upload_to='cours/pdf/', blank=True, null=True)
    url_video = models.URLField(blank=True)
    contenu_html = models.TextField(blank=True)
    ordre = models.PositiveIntegerField(default=0)
    obligatoire = models.BooleanField(default=True)

    class Meta:
        ordering = ['chapitre', 'ordre']
        unique_together = ['chapitre', 'ordre']

    def __str__(self):
        return f"{self.chapitre.titre} - {self.titre}"

