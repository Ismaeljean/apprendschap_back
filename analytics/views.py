# analytics/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db.models import Avg, Count, Sum, F
from django.utils import timezone
from django.contrib.auth.models import User
from analytics.models import StatistiqueGlobale
from analytics.serializers import StatistiqueGlobaleSerializer
from progression.models import ProgressionChapitre, TentativeQuiz
from examens.models import Examen
from quiz.models import Quiz
import uuid


class StatistiqueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les statistiques globales
    """
    queryset = StatistiqueGlobale.objects.all()
    serializer_class = StatistiqueGlobaleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'])
    def dashboard_admin(self, request):
        """Statistiques pour le tableau de bord administrateur"""
        stats = StatistiqueGlobale.objects.first()
        
        if not stats:
            # Calculer les statistiques si elles n'existent pas
            stats = self._calculer_statistiques_globales()
        
        # Statistiques supplémentaires
        data = StatistiqueGlobaleSerializer(stats).data
        
        # Ajouter des métriques détaillées
        data.update({
            'utilisateurs_actifs_7j': User.objects.filter(
                profiletudiant__derniere_activite__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'nouveaux_utilisateurs_30j': User.objects.filter(
                date_joined__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
            'quiz_par_difficulte': list(
                Quiz.objects.values('difficulte').annotate(count=Count('id'))
            ),
            'examens_par_type': list(
                Examen.objects.values('type_examen__nom').annotate(count=Count('id'))
            )
        })
        
        return Response(data)

    def _calculer_statistiques_globales(self):
        """Calculer et sauvegarder les statistiques globales"""
        stats, created = StatistiqueGlobale.objects.get_or_create(
            defaults={
                'nombre_utilisateurs': User.objects.count(),
                'nombre_chapitres_termines': ProgressionChapitre.objects.filter(
                    statut='termine'
                ).count(),
                'temps_etude_total': ProgressionChapitre.objects.aggregate(
                    total=Sum('temps_etudie')
                )['total'] or 0,
                'nombre_quiz_reussis': TentativeQuiz.objects.filter(
                    termine=True,
                    pourcentage__gte=F('quiz__note_passage')
                ).count(),
                'moyenne_generale': TentativeQuiz.objects.filter(
                    termine=True
                ).aggregate(
                    moyenne=Avg('pourcentage')
                )['moyenne'] or 0
            }
        )
        
        return stats
