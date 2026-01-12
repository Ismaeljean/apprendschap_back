# examens/serializers.py
from rest_framework import serializers
from examens.models import TypeExamen, Examen

class TypeExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les types d'examen"""
    nombre_examens = serializers.SerializerMethodField()
    
    class Meta:
        model = TypeExamen
        fields = ['id', 'nom', 'description', 'nombre_examens']
    
    def get_nombre_examens(self, obj):
        return obj.examens.filter(actif=True).count()

class ExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les examens"""
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    type_examen_nom = serializers.CharField(source='type_examen.nom', read_only=True)
    
    class Meta:
        model = Examen
        fields = ['id', 'titre', 'matiere', 'matiere_nom', 'type_examen', 
                 'type_examen_nom', 'annee', 'session', 'duree_heures', 'points_total', 
                 'difficulte', 'description', 'fichier_sujet', 'fichier_correction', 
                 'nombre_telechargements', 'date_ajout', 'actif']
