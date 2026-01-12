# ia/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from ia.models import ConversationIA, MessageIA
from ia.serializers import ConversationIASerializer, MessageIASerializer, EnvoiMessageIASerializer
from ia.permissions import IsOwnerOrReadOnly
from ia.services import poser_question_a_l_ia
from cours.models import Chapitre

class ConversationIAViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les conversations avec l'IA
    """
    serializer_class = ConversationIASerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return ConversationIA.objects.filter(
            etudiant=self.request.user,
            active=True
        ).order_by('-derniere_activite')

    def perform_create(self, serializer):
        serializer.save(etudiant=self.request.user)

    @action(detail=False, methods=['post'])
    def envoyer_message(self, request):
        """Envoyer un message à l'IA"""
        # Vérifier les permissions d'accès à l'IA
        try:
            from abonnements.services import PermissionService
            acces_autorise, message = PermissionService.verifier_acces_ia(request.user, 'standard')
            if not acces_autorise:
                return Response({'error': message}, status=status.HTTP_403_FORBIDDEN)
        except ImportError:
            # Si le service n'est pas disponible, continuer sans restriction
            pass
        
        print(f"🔍 DEBUG - Message reçu: {request.data}")
        
        serializer = EnvoiMessageIASerializer(data=request.data)
        
        if not serializer.is_valid():
            print(f"❌ DEBUG - Erreurs de validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        session_id = data.get('session_id')
        
        # Récupérer ou créer la conversation
        if session_id and session_id.strip():  # Vérifier que session_id n'est pas vide
            try:
                conversation = ConversationIA.objects.get(
                    session_id=session_id,
                    etudiant=request.user
                )
            except ConversationIA.DoesNotExist:
                # Si la session n'existe pas, créer une nouvelle conversation
                conversation = ConversationIA.objects.create(
                    etudiant=request.user
                )
        else:
            # Créer une nouvelle conversation si pas de session_id
            conversation = ConversationIA.objects.create(
                etudiant=request.user
            )
        
        # Récupérer le contexte du chapitre si fourni
        contexte_chapitre = None
        if data.get('contexte_chapitre_id'):
            try:
                contexte_chapitre = Chapitre.objects.get(id=data['contexte_chapitre_id'])
            except Chapitre.DoesNotExist:
                return Response({"error": "Chapitre non trouvé"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Créer le message de l'étudiant
        message_etudiant = MessageIA.objects.create(
            conversation=conversation,
            expediteur='etudiant',
            contenu=data['contenu'],
            contexte_chapitre=contexte_chapitre
        )
        
        # Générer la réponse de l'IA
        print(f"🤖 DEBUG - Génération de la réponse IA pour: {data['contenu']}")
        reponse_ia = self._generer_reponse_ia(data['contenu'], contexte_chapitre)
        print(f"✅ DEBUG - Réponse IA générée: {reponse_ia[:100]}...")
        
        message_ia = MessageIA.objects.create(
            conversation=conversation,
            expediteur='ia',
            contenu=reponse_ia,
            contexte_chapitre=contexte_chapitre
        )
        
        # Mettre à jour le titre de la conversation si vide
        if not conversation.titre:
            conversation.titre = data['contenu'][:50]
            conversation.save()
        
        # Mettre à jour la dernière activité
        conversation.derniere_activite = timezone.now()
        conversation.save()
        
        return Response({
            'conversation_id': conversation.session_id,
            'message_etudiant': MessageIASerializer(message_etudiant).data,
            'message_ia': MessageIASerializer(message_ia).data
        })

    def _generer_reponse_ia(self, contenu, contexte_chapitre):
        """
        Générer une réponse IA en utilisant Ollama
        """
        return poser_question_a_l_ia(contenu, contexte_chapitre)