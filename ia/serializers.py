# ia/serializers.py
from rest_framework import serializers
from ia.models import ConversationIA, MessageIA

class MessageIASerializer(serializers.ModelSerializer):
    """Serializer pour les messages IA"""
    contexte_chapitre_titre = serializers.CharField(source='contexte_chapitre.titre', read_only=True, allow_null=True)
    
    class Meta:
        model = MessageIA
        fields = ['id', 'expediteur', 'contenu', 'contexte_chapitre', 'contexte_chapitre_titre', 'timestamp', 'lu']

class ConversationIASerializer(serializers.ModelSerializer):
    """Serializer pour les conversations IA"""
    messages = MessageIASerializer(many=True, read_only=True)
    dernier_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ConversationIA
        fields = ['id', 'session_id', 'titre', 'date_creation', 'derniere_activite', 
                 'active', 'messages', 'dernier_message']
    
    def get_dernier_message(self, obj):
        dernier = obj.messages.last()
        if dernier:
            return {
                'contenu': dernier.contenu[:100] + "..." if len(dernier.contenu) > 100 else dernier.contenu,
                'expediteur': dernier.expediteur,
                'timestamp': dernier.timestamp
            }
        return None

class EnvoiMessageIASerializer(serializers.Serializer):
    """Serializer pour envoyer un message à l'IA"""
    contenu = serializers.CharField(max_length=2000)
    contexte_chapitre_id = serializers.IntegerField(required=False, allow_null=True)
    session_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)