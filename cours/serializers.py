# cours/serializers.py
from rest_framework import serializers
from cours.models import Chapitre, ContenuChapitre
from progression.models import ProgressionChapitre, ProgressionContenu


class ContenuChapitreSerializer(serializers.ModelSerializer):
    """Serializer pour les contenus de chapitre"""
    progression_etudiant = serializers.SerializerMethodField()
    
    class Meta:
        model = ContenuChapitre
        fields = [
            'id', 'titre', 'description', 'fichier_pdf', 'url_video', 
            'contenu_html', 'ordre', 'obligatoire', 'progression_etudiant'
        ]
    
    def get_progression_etudiant(self, obj):
        """Récupère la progression de l'étudiant pour ce contenu"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            try:
                progression = ProgressionContenu.objects.get(
                    etudiant=request.user,
                    contenu=obj
                )
                return {
                    'lu': progression.lu,
                    'temps_lecture': progression.temps_lecture,
                    'date_debut': progression.date_debut,
                    'date_completion': progression.date_completion
                }
            except ProgressionContenu.DoesNotExist:
                return {
                    'lu': False,
                    'temps_lecture': 0,
                    'date_debut': None,
                    'date_completion': None
                }
        return {
            'lu': False,
            'temps_lecture': 0,
            'date_debut': None,
            'date_completion': None
        }


class ChapitreListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des chapitres"""
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    matiere_couleur = serializers.CharField(source='matiere.couleur', read_only=True)
    progression_etudiant = serializers.SerializerMethodField()
    nombre_contenus = serializers.SerializerMethodField()
    prerequis_titres = serializers.StringRelatedField(source='prerequis', many=True, read_only=True)
    
    class Meta:
        model = Chapitre
        fields = [
            'id', 'titre', 'numero', 'description', 'matiere', 'matiere_nom', 
            'matiere_couleur', 'duree_estimee', 'difficulte', 'nombre_contenus', 
            'prerequis_titres', 'progression_etudiant', 'date_creation', 'actif'
        ]
    
    def get_nombre_contenus(self, obj):
        """Retourne le nombre de contenus du chapitre"""
        return obj.contenus.count()
    
    def get_progression_etudiant(self, obj):
        """Récupère la progression de l'étudiant pour ce chapitre"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            try:
                progression = ProgressionChapitre.objects.get(
                    etudiant=request.user,
                    chapitre=obj
                )
                return {
                    'statut': progression.statut,
                    'pourcentage_completion': progression.pourcentage_completion,
                    'temps_etudie': progression.temps_etudie,
                    'date_debut': progression.date_debut,
                    'date_completion': progression.date_completion
                }
            except ProgressionChapitre.DoesNotExist:
                return {
                    'statut': 'non_commence',
                    'pourcentage_completion': 0.0,
                    'temps_etudie': 0,
                    'date_debut': None,
                    'date_completion': None
                }
        return {
            'statut': 'non_commence',
            'pourcentage_completion': 0.0,
            'temps_etudie': 0,
            'date_debut': None,
            'date_completion': None
        }


class ChapitreDetailSerializer(ChapitreListSerializer):
    """Serializer détaillé pour un chapitre avec ses contenus"""
    contenus = ContenuChapitreSerializer(many=True, read_only=True)
    prerequis = ChapitreListSerializer(many=True, read_only=True)
    
    class Meta(ChapitreListSerializer.Meta):
        fields = ChapitreListSerializer.Meta.fields + ['contenus', 'prerequis', 'date_modification']


# Alias pour la compatibilité
ChapitreSerializer = ChapitreDetailSerializer