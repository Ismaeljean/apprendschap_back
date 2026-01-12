# gamification/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.db.models import Sum
from gamification.models import Badge, BadgeEtudiant
from gamification.serializers import BadgeSerializer, BadgeEtudiantSerializer
from progression.models import ProgressionChapitre
from quiz.models import TentativeQuiz
import uuid





# Create your views here.
class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les badges
    """
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mes_badges(self, request):
        """Récupérer les badges obtenus par l'utilisateur"""
        badges_obtenus = BadgeEtudiant.objects.filter(
            etudiant=request.user
        ).order_by('-date_obtention')
        
        serializer = BadgeEtudiantSerializer(badges_obtenus, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def verifier_nouveaux_badges(self, request):
        """Vérifier si l'utilisateur a obtenu de nouveaux badges"""
        nouveaux_badges = []
        
        # Vérifier chaque type de badge
        for badge in Badge.objects.all():
            if not BadgeEtudiant.objects.filter(etudiant=request.user, badge=badge).exists():
                if self._verifier_condition_badge(request.user, badge):
                    badge_etudiant = BadgeEtudiant.objects.create(
                        etudiant=request.user,
                        badge=badge
                    )
                    nouveaux_badges.append(badge_etudiant)
        
        serializer = BadgeEtudiantSerializer(nouveaux_badges, many=True, context={'request': request})
        return Response({
            'nouveaux_badges': serializer.data,
            'nombre': len(nouveaux_badges)
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def badges_disponibles(self, request):
        """Récupérer tous les badges avec leur statut d'obtention"""
        all_badges = Badge.objects.filter(actif=True).order_by('ordre', 'nom')
        user_badges = set(BadgeEtudiant.objects.filter(
            etudiant=request.user
        ).values_list('badge_id', flat=True))
        
        badges_data = []
        for badge in all_badges:
            badges_data.append({
                'id': badge.id,
                'nom': badge.nom,
                'description': badge.description,
                'icone': badge.icone,
                'couleur': badge.couleur,
                'points': badge.points,
                'obtenu': badge.id in user_badges,
                'condition_type': badge.condition_type,
                'condition_valeur': badge.condition_valeur,
                'progression': self._calculer_progression_badge(request.user, badge) if badge.id not in user_badges else 100
            })
        
        return Response(badges_data)

    def _calculer_progression_badge(self, user, badge):
        """Calculer la progression vers un badge (0-100%)"""
        from progression.models import ProgressionMatiere
        
        if badge.condition_type == 'premier_chapitre':
            count = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut__in=['termine', 'maitrise']
            ).count()
            return min(100, (count / 1) * 100)
            
        elif badge.condition_type == 'chapitres_termines':
            count = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut__in=['termine', 'maitrise']
            ).count()
            return min(100, (count / badge.condition_valeur) * 100)
        
        elif badge.condition_type == 'quiz_reussis':
            count = TentativeQuiz.objects.filter(
                etudiant=user,
                pourcentage__gte=60,
                termine=True
            ).count()
            return min(100, (count / badge.condition_valeur) * 100)
        
        elif badge.condition_type == 'quiz_parfait':
            count = TentativeQuiz.objects.filter(
                etudiant=user,
                pourcentage=100,
                termine=True
            ).count()
            return min(100, (count / badge.condition_valeur) * 100)
        
        elif badge.condition_type == 'temps_etude':
            temps_total = ProgressionChapitre.objects.filter(
                etudiant=user
            ).aggregate(
                total=Sum('temps_etudie')
            )['total'] or 0
            
            # Le temps est stocké en secondes, mais les badges sont configurés en minutes
            # Convertir le temps total en minutes pour la comparaison
            temps_total_minutes = temps_total / 60
            return min(100, (temps_total_minutes / badge.condition_valeur) * 100)
            
        elif badge.condition_type == 'matieres_terminees':
            count = ProgressionMatiere.objects.filter(
                etudiant=user,
                pourcentage_completion=100
            ).count()
            return min(100, (count / badge.condition_valeur) * 100)
        
        return 0

    def _verifier_condition_badge(self, user, badge):
        """Vérifier si un utilisateur remplit les conditions pour un badge"""
        from progression.models import ProgressionMatiere
        
        if badge.condition_type == 'premier_chapitre':
            # Badge pour le premier chapitre terminé
            count = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut__in=['termine', 'maitrise']
            ).count()
            return count >= 1
            
        elif badge.condition_type == 'chapitres_termines':
            count = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut__in=['termine', 'maitrise']
            ).count()
            return count >= badge.condition_valeur
        
        elif badge.condition_type == 'quiz_parfait':
            count = TentativeQuiz.objects.filter(
                etudiant=user,
                pourcentage=100,
                termine=True
            ).count()
            return count >= badge.condition_valeur
            
        elif badge.condition_type == 'quiz_reussis':
            # Quiz réussis avec au moins 60%
            count = TentativeQuiz.objects.filter(
                etudiant=user,
                pourcentage__gte=60,
                termine=True
            ).count()
            return count >= badge.condition_valeur
        
        elif badge.condition_type == 'temps_etude':
            temps_total = ProgressionChapitre.objects.filter(
                etudiant=user
            ).aggregate(
                total=Sum('temps_etudie')
            )['total'] or 0
            
            # Le temps est stocké en secondes, mais les badges sont configurés en minutes
            # Convertir le temps total en minutes pour la comparaison
            temps_total_minutes = temps_total / 60
            return temps_total_minutes >= badge.condition_valeur
            
        elif badge.condition_type == 'matiere_complete':
            # Au moins une matière à 100%
            count = ProgressionMatiere.objects.filter(
                etudiant=user,
                pourcentage_completion=100
            ).count()
            return count >= 1
            
        elif badge.condition_type == 'matieres_terminees':
            # Nombre de matières terminées
            count = ProgressionMatiere.objects.filter(
                etudiant=user,
                pourcentage_completion=100
            ).count()
            return count >= badge.condition_valeur
            
        elif badge.condition_type == 'programme_complet':
            # Toutes les matières terminées
            from academic_structure.models import Matiere
            total_matieres = Matiere.objects.filter(actif=True).count()
            matieres_terminees = ProgressionMatiere.objects.filter(
                etudiant=user,
                pourcentage_completion=100
            ).count()
            return total_matieres > 0 and matieres_terminees >= total_matieres
        
        return False