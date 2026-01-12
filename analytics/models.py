# analytics/models.py
from django.db import models


class StatistiqueGlobale(models.Model):
    """Statistiques globales de la plateforme"""
    nombre_utilisateurs = models.PositiveIntegerField(default=0)
    nombre_chapitres_termines = models.PositiveIntegerField(default=0)
    temps_etude_total = models.PositiveIntegerField(default=0, help_text="Temps en minutes")
    nombre_quiz_reussis = models.PositiveIntegerField(default=0)
    moyenne_generale = models.FloatField(default=0.0)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Statistique globale"
        verbose_name_plural = "Statistiques globales"

    def __str__(self):
        return f"Stats du {self.date_mise_a_jour.strftime('%d/%m/%Y')}"