# academic_structure/serializers.py
from rest_framework import serializers
from .models import NiveauScolaire, Matiere
from progression.models import ProgressionChapitre
from django.db.models import Avg

class NiveauScolaireSerializer(serializers.ModelSerializer):
    """Serializer pour les niveaux scolaires"""
    nombre_matieres = serializers.SerializerMethodField()
    
    class Meta:
        model = NiveauScolaire
        fields = ['id', 'nom', 'ordre', 'description', 'nombre_matieres']
    
    def get_nombre_matieres(self, obj):
        return obj.matiere_set.filter(active=True).count()

class MatiereSerializer(serializers.ModelSerializer):
    """Serializer pour les matières"""
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    nombre_chapitres = serializers.SerializerMethodField()
    progression_etudiant = serializers.SerializerMethodField()
    
    class Meta:
        model = Matiere
        fields = ['id', 'nom', 'slug', 'description', 'icone', 'couleur', 
                 'niveau', 'niveau_nom', 'ordre', 'active', 'nombre_chapitres', 'progression_etudiant']
    
    def get_nombre_chapitres(self, obj):
        return obj.chapitres.filter(actif=True).count()
    
    def get_progression_etudiant(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            progressions = ProgressionChapitre.objects.filter(
                etudiant=request.user,
                chapitre__matiere=obj
            )
            if progressions.exists():
                return progressions.aggregate(
                    moyenne=Avg('pourcentage_completion')
                )['moyenne']
        return 0
