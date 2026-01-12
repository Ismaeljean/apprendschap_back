# gamification/serializers.py
from rest_framework import serializers
from gamification.models import Badge, BadgeEtudiant

class BadgeSerializer(serializers.ModelSerializer):
    """Serializer pour les badges"""
    obtenu_par_etudiant = serializers.SerializerMethodField()
    
    class Meta:
        model = Badge
        fields = ['id', 'nom', 'description', 'icone', 'couleur', 'condition_type',
                 'condition_valeur', 'points', 'obtenu_par_etudiant']
    
    def get_obtenu_par_etudiant(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return BadgeEtudiant.objects.filter(
                etudiant=request.user,
                badge=obj
            ).exists()
        return False

class BadgeEtudiantSerializer(serializers.ModelSerializer):
    """Serializer pour les badges obtenus"""
    badge_details = BadgeSerializer(source='badge', read_only=True)
    
    class Meta:
        model = BadgeEtudiant
        fields = ['id', 'badge', 'badge_details', 'date_obtention']