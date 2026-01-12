# analytics/serializers.py
from rest_framework import serializers
from analytics.models import StatistiqueGlobale





class StatistiqueGlobaleSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques globales"""
    class Meta:
        model = StatistiqueGlobale
        fields = ['nombre_utilisateurs', 'nombre_chapitres_termines', 'temps_etude_total',
                 'nombre_quiz_reussis', 'moyenne_generale', 'date_mise_a_jour']
