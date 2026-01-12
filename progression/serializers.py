# progression/serializers.py
from rest_framework import serializers
from progression.models import ProgressionChapitre, ProgressionContenu, ProgressionMatiere
from cours.models import Chapitre, ContenuChapitre


class ProgressionContenuSerializer(serializers.ModelSerializer):
    """Serializer pour la progression des contenus"""
    contenu_titre = serializers.CharField(source='contenu.titre', read_only=True)
    contenu_ordre = serializers.IntegerField(source='contenu.ordre', read_only=True)
    chapitre_titre = serializers.CharField(source='contenu.chapitre.titre', read_only=True)
    
    class Meta:
        model = ProgressionContenu
        fields = [
            'id', 'contenu', 'contenu_titre', 'contenu_ordre', 'chapitre_titre',
            'lu', 'temps_lecture', 'date_debut', 'date_completion'
        ]
        read_only_fields = ['date_debut']

    def validate_temps_lecture(self, value):
        """Valide que le temps de lecture est positif"""
        if value < 0:
            raise serializers.ValidationError("Le temps de lecture ne peut pas être négatif.")
        return value


class ProgressionChapitreSerializer(serializers.ModelSerializer):
    """Serializer pour la progression dans les chapitres"""
    chapitre_titre = serializers.CharField(source='chapitre.titre', read_only=True)
    chapitre_numero = serializers.IntegerField(source='chapitre.numero', read_only=True)
    matiere_nom = serializers.CharField(source='chapitre.matiere.nom', read_only=True)
    matiere_couleur = serializers.CharField(source='chapitre.matiere.couleur', read_only=True)
    duree_estimee = serializers.IntegerField(source='chapitre.duree_estimee', read_only=True)
    difficulte = serializers.CharField(source='chapitre.difficulte', read_only=True)
    
    # Champs calculés
    temps_etudie_formate = serializers.SerializerMethodField()
    temps_lecture_total = serializers.SerializerMethodField()
    temps_lecture_contenu_actuel = serializers.SerializerMethodField()
    progression_contenus = serializers.SerializerMethodField()
    
    class Meta:
        model = ProgressionChapitre
        fields = [
            'id', 'chapitre', 'chapitre_titre', 'chapitre_numero', 'matiere_nom', 
            'matiere_couleur', 'duree_estimee', 'difficulte', 'statut', 
            'pourcentage_completion', 'temps_etudie', 'temps_etudie_formate',
            'temps_lecture_total', 'temps_lecture_contenu_actuel', 'date_debut', 'date_completion', 'progression_contenus'
        ]
        read_only_fields = ['date_debut', 'pourcentage_completion']

    def get_temps_etudie_formate(self, obj):
        """Formate le temps étudié en heures et minutes"""
        if obj.temps_etudie == 0:
            return "0 min"
        
        heures = obj.temps_etudie // 60
        minutes = obj.temps_etudie % 60
        
        if heures > 0:
            return f"{heures}h {minutes}min" if minutes > 0 else f"{heures}h"
        return f"{minutes}min"

    def get_temps_lecture_total(self, obj):
        """Calcule le temps de lecture total de tous les contenus du chapitre"""
        progressions_contenu = ProgressionContenu.objects.filter(
            etudiant=obj.etudiant,
            contenu__chapitre=obj.chapitre
        )
        return sum(p.temps_lecture for p in progressions_contenu)

    def get_temps_lecture_contenu_actuel(self, obj):
        """Récupère le temps de lecture du contenu actuellement consulté"""
        request = self.context.get('request')
        if not request:
            return 0
            
        # Essayer de récupérer l'ID du contenu depuis les paramètres de requête
        contenu_id = request.query_params.get('contenu_id')
        if not contenu_id:
            # Prendre le premier contenu du chapitre par défaut
            premier_contenu = obj.chapitre.contenus.first()
            if premier_contenu:
                contenu_id = premier_contenu.id
        
        if contenu_id:
            try:
                progression_contenu = ProgressionContenu.objects.get(
                    etudiant=obj.etudiant,
                    contenu_id=contenu_id
                )
                return progression_contenu.temps_lecture
            except ProgressionContenu.DoesNotExist:
                return 0
        
        return 0

    def get_progression_contenus(self, obj):
        """Retourne les détails de progression des contenus si demandé"""
        request = self.context.get('request')
        if request and request.query_params.get('include_contenus', '').lower() == 'true':
            contenus_progression = ProgressionContenu.objects.filter(
                etudiant=obj.etudiant,
                contenu__chapitre=obj.chapitre
            ).select_related('contenu')
            
            return ProgressionContenuSerializer(
                contenus_progression, 
                many=True, 
                context=self.context
            ).data
        return []

    def validate_statut(self, value):
        """Valide le statut de progression"""
        statuts_valides = ['non_commence', 'en_cours', 'termine', 'maitrise']
        if value not in statuts_valides:
            raise serializers.ValidationError(f"Statut invalide. Doit être l'un de: {statuts_valides}")
        return value

    def validate_pourcentage_completion(self, value):
        """Valide le pourcentage de completion"""
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Le pourcentage doit être entre 0 et 100.")
        return value

    def validate_temps_etudie(self, value):
        """Valide que le temps étudié est positif"""
        if value < 0:
            raise serializers.ValidationError("Le temps étudié ne peut pas être négatif.")
        return value


class ProgressionChapitreListSerializer(ProgressionChapitreSerializer):
    """Serializer simplifié pour la liste des progressions"""
    
    class Meta(ProgressionChapitreSerializer.Meta):
        fields = [
            'id', 'chapitre', 'chapitre_titre', 'chapitre_numero', 'matiere_nom', 
            'matiere_couleur', 'statut', 'pourcentage_completion', 
            'temps_etudie_formate', 'date_debut', 'date_completion'
        ]


class ProgressionStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques de progression"""
    total_chapitres = serializers.IntegerField()
    chapitres_commences = serializers.IntegerField()
    chapitres_termines = serializers.IntegerField()
    chapitres_maitrises = serializers.IntegerField()
    temps_total_etudie = serializers.IntegerField()
    quiz_reussis = serializers.IntegerField()
    matieres_terminees = serializers.IntegerField()
    pourcentage_global = serializers.FloatField()
    matiere_stats = serializers.ListField(child=serializers.DictField())
    
    def to_representation(self, instance):
        """Personnalise la représentation des statistiques"""
        data = super().to_representation(instance)
        
        # Formater le temps total (stocké en secondes)
        temps_total = data.get('temps_total_etudie', 0)
        if temps_total == 0:
            data['temps_total_formate'] = "0 min"
        else:
            # Convertir les secondes en heures et minutes
            heures = temps_total // 3600
            minutes = (temps_total % 3600) // 60
            secondes = temps_total % 60
            
            if heures > 0:
                data['temps_total_formate'] = f"{heures}h {minutes}min" if minutes > 0 else f"{heures}h"
            elif minutes > 0:
                data['temps_total_formate'] = f"{minutes}min {secondes}s" if secondes > 0 else f"{minutes}min"
            else:
                data['temps_total_formate'] = f"{secondes}s"
        
        return data


class ProgressionMatiereSerializer(serializers.ModelSerializer):
    """Serializer pour la progression par matière"""
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    matiere_icone = serializers.CharField(source='matiere.icone', read_only=True)
    niveau_nom = serializers.CharField(source='matiere.niveau.nom', read_only=True)
    temps_etudie_total_formate = serializers.SerializerMethodField()
    progression_pourcentage = serializers.FloatField(source='pourcentage_completion', read_only=True)
    
    class Meta:
        model = ProgressionMatiere
        fields = [
            'id', 'etudiant', 'matiere', 'matiere_nom', 'matiere_icone', 'niveau_nom',
            'statut', 'pourcentage_completion', 'progression_pourcentage',
            'temps_etudie_total', 'temps_etudie_total_formate',
            'nombre_chapitres_termines', 'nombre_chapitres_total',
            'date_debut', 'date_completion'
        ]
        read_only_fields = [
            'etudiant', 'pourcentage_completion', 'temps_etudie_total',
            'nombre_chapitres_termines', 'nombre_chapitres_total'
        ]

    def get_temps_etudie_total_formate(self, obj):
        """Formate le temps étudié total"""
        seconds = obj.temps_etudie_total
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s" if remaining_seconds > 0 else f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"