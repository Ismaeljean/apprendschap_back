# quiz/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from quiz.models import Quiz, QuestionQuiz, ReponseQuestion, TentativeQuiz, ReponseEtudiant
from quiz.serializers import (
    QuizSerializer, QuestionQuizAvecExplicationSerializer,
    TentativeQuizSerializer, SoumissionQuizSerializer
)
import uuid

class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les quiz avec tentatives
    """
    queryset = Quiz.objects.filter(actif=True)
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['chapitre__matiere', 'chapitre', 'difficulte']
    search_fields = ['titre', 'description']

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='tentatives-recentes')
    def tentatives_recentes(self, request):
        """Récupérer les tentatives récentes de l'utilisateur"""
        tentatives = TentativeQuiz.objects.filter(
            etudiant=request.user
        ).select_related('quiz', 'quiz__chapitre').order_by('-date_tentative')[:10]
        
        # Sérialiser les tentatives avec infos du quiz
        data = []
        for tentative in tentatives:
            data.append({
                'id': tentative.id,
                'quiz_titre': tentative.quiz.titre,
                'quiz_id': tentative.quiz.id,
                'chapitre_titre': tentative.quiz.chapitre.titre if tentative.quiz.chapitre else '',
                'date_tentative': tentative.date_tentative,
                'termine': tentative.termine,
                'score': tentative.score,
                'pourcentage': tentative.pourcentage,
                'temps_ecoule': tentative.temps_ecoule
            })
        
        return Response(data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def commencer_tentative(self, request, pk=None):
        """Commencer une nouvelle tentative de quiz"""
        # Vérifier les permissions d'accès aux quiz
        try:
            from abonnements.services import PermissionService
            acces_autorise, message = PermissionService.verifier_acces_quiz(request.user)
            if not acces_autorise:
                return Response({'error': message}, status=status.HTTP_403_FORBIDDEN)
        except ImportError:
            # Si le service n'est pas disponible, continuer sans restriction
            pass
        
        quiz = self.get_object()
        
        # Vérifier le nombre de tentatives autorisées
        tentatives_existantes = TentativeQuiz.objects.filter(
            etudiant=request.user,
            quiz=quiz
        ).count()
        
        if tentatives_existantes >= quiz.tentatives_autorisees:
            return Response(
                {'error': 'Nombre maximum de tentatives atteint'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Créer nouvelle tentative
        tentative = TentativeQuiz.objects.create(
            etudiant=request.user,
            quiz=quiz,
            numero_tentative=tentatives_existantes + 1
        )
        
        # Retourner le quiz avec les questions (sans les bonnes réponses)
        serializer = QuizSerializer(quiz, context={'request': request})
        data = serializer.data
        data['tentative_id'] = tentative.id
        
        return Response(data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def sauvegarder_reponse(self, request, pk=None):
        """Sauvegarder une réponse individuelle pendant le quiz"""
        quiz = self.get_object()
        tentative_id = request.data.get('tentative_id')
        question_id = request.data.get('question_id')
        reponses_choisies_ids = request.data.get('reponses_choisies', [])
        reponse_libre = request.data.get('reponse_libre', '')
        temps_reponse = request.data.get('temps_reponse', 0)

        try:
            tentative = TentativeQuiz.objects.get(
                id=tentative_id,
                etudiant=request.user,
                quiz=quiz,
                termine=False
            )
            question = quiz.questions.get(id=question_id)
        except (TentativeQuiz.DoesNotExist, QuestionQuiz.DoesNotExist):
            return Response(
                {'error': 'Tentative ou question introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Créer ou mettre à jour la réponse de l'étudiant
        reponse_etudiant, created = ReponseEtudiant.objects.get_or_create(
            tentative=tentative,
            question=question,
            defaults={
                'reponse_libre': reponse_libre,
                'temps_reponse': temps_reponse
            }
        )

        if not created:
            # Mettre à jour si elle existe déjà
            reponse_etudiant.reponse_libre = reponse_libre
            reponse_etudiant.temps_reponse = temps_reponse

        # Ajouter les réponses choisies
        if reponses_choisies_ids:
            reponses_choisies = ReponseQuestion.objects.filter(
                id__in=reponses_choisies_ids,
                question=question
            )
            reponse_etudiant.reponses_choisies.set(reponses_choisies)

        # Calculer si c'est correct
        if question.type_question in ['choix_unique', 'choix_multiple']:
            bonnes_reponses = set(question.reponses.filter(est_correcte=True).values_list('id', flat=True))
            reponses_donnees = set(reponses_choisies_ids)
            
            if bonnes_reponses == reponses_donnees:
                reponse_etudiant.correcte = True
                reponse_etudiant.points_obtenus = question.points
            else:
                reponse_etudiant.correcte = False
                reponse_etudiant.points_obtenus = 0

        reponse_etudiant.save()

        return Response({
            'success': True,
            'correcte': reponse_etudiant.correcte,
            'points_obtenus': reponse_etudiant.points_obtenus
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def soumettre(self, request, pk=None):
        """Soumettre les réponses d'un quiz"""
        quiz = self.get_object()
        serializer = SoumissionQuizSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        tentative_id = request.data.get('tentative_id')
        
        try:
            tentative = TentativeQuiz.objects.get(
                id=tentative_id,
                etudiant=request.user,
                quiz=quiz,
                termine=False
            )
        except TentativeQuiz.DoesNotExist:
            return Response(
                {'error': 'Tentative introuvable ou déjà terminée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculer le score basé sur les réponses déjà enregistrées
        reponses_existantes = ReponseEtudiant.objects.filter(tentative=tentative)
        score_total = sum(r.points_obtenus for r in reponses_existantes)
        points_total = sum(q.points for q in quiz.questions.all())
        
        # Si des réponses sont encore envoyées dans la soumission finale, les traiter
        if 'reponses' in data and data['reponses']:
            for reponse_data in data['reponses']:
                question_id = reponse_data.get('question_id')
                reponses_choisies_ids = reponse_data.get('reponses_choisies', [])
                reponse_libre = reponse_data.get('reponse_libre', '')
                temps_reponse = reponse_data.get('temps_reponse', 0)
                
                try:
                    question = quiz.questions.get(id=question_id)
                    
                    # Créer ou mettre à jour la réponse de l'étudiant
                    reponse_etudiant, created = ReponseEtudiant.objects.get_or_create(
                        tentative=tentative,
                        question=question,
                        defaults={
                            'reponse_libre': reponse_libre,
                            'temps_reponse': temps_reponse
                        }
                    )
                    
                    if not created:
                        # Mettre à jour si elle existe déjà
                        reponse_etudiant.reponse_libre = reponse_libre
                        if reponse_etudiant.temps_reponse is None or reponse_etudiant.temps_reponse == 0:
                            reponse_etudiant.temps_reponse = temps_reponse
                    
                    # Ajouter les réponses choisies
                    if reponses_choisies_ids:
                        reponses_choisies = ReponseQuestion.objects.filter(
                            id__in=reponses_choisies_ids,
                            question=question
                        )
                        reponse_etudiant.reponses_choisies.set(reponses_choisies)
                    
                    # Calculer si c'est correct
                    if question.type_question in ['choix_unique', 'choix_multiple']:
                        bonnes_reponses = set(question.reponses.filter(est_correcte=True).values_list('id', flat=True))
                        reponses_donnees = set(reponses_choisies_ids)
                        
                        if bonnes_reponses == reponses_donnees:
                            reponse_etudiant.correcte = True
                            reponse_etudiant.points_obtenus = question.points
                        else:
                            reponse_etudiant.correcte = False
                            reponse_etudiant.points_obtenus = 0
                    
                    reponse_etudiant.save()
                    
                except QuestionQuiz.DoesNotExist:
                    continue
            
            # Recalculer le score après traitement des nouvelles réponses
            reponses_existantes = ReponseEtudiant.objects.filter(tentative=tentative)
            score_total = sum(r.points_obtenus for r in reponses_existantes)
        
        # Finaliser la tentative
        tentative.score = score_total
        tentative.pourcentage = (score_total / points_total * 100) if points_total > 0 else 0
        tentative.temps_ecoule = data.get('temps_ecoule', 0)
        tentative.date_fin = timezone.now()
        tentative.termine = True
        tentative.save()
        
        # Retourner les résultats avec explications
        questions_avec_corrections = QuestionQuizAvecExplicationSerializer(
            quiz.questions.all(),
            many=True,
            context={'request': request}
        ).data
        
        return Response({
            'tentative': TentativeQuizSerializer(tentative).data,
            'questions_corrections': questions_avec_corrections,
            'reussi': tentative.pourcentage >= quiz.note_passage
        })

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def mes_tentatives(self, request, pk=None):
        """Récupérer les tentatives de l'utilisateur pour ce quiz"""
        quiz = self.get_object()
        tentatives = TentativeQuiz.objects.filter(
            etudiant=request.user,
            quiz=quiz,
            termine=True
        ).order_by('-date_debut')
        
        serializer = TentativeQuizSerializer(tentatives, many=True)
        return Response(serializer.data)
