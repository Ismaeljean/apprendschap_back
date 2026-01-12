# academic_structure/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Sum
from .models import NiveauScolaire, Matiere
from .serializers import NiveauScolaireSerializer, MatiereSerializer
from cours.serializers import ChapitreSerializer
from progression.models import ProgressionChapitre

class NiveauScolaireViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les niveaux scolaires (lecture seule)
    """
    queryset = NiveauScolaire.objects.all()
    serializer_class = NiveauScolaireSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class MatiereViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les matières avec filtrage par niveau
    """
    queryset = Matiere.objects.filter(active=True)
    serializer_class = MatiereSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['niveau', 'niveau__nom']
    search_fields = ['nom', 'description']
    ordering_fields = ['ordre', 'nom']
    ordering = ['niveau__ordre', 'ordre']

    @action(detail=True, methods=['get'])
    def chapitres(self, request, pk=None):
        """Récupérer tous les chapitres d'une matière"""
        matiere = self.get_object()
        chapitres = matiere.chapitres.filter(actif=True).order_by('numero')
        serializer = ChapitreSerializer(chapitres, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def progression(self, request, pk=None):
        """Progression de l'étudiant dans une matière"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentification requise'}, status=status.HTTP_401_UNAUTHORIZED)
        
        matiere = self.get_object()
        progressions = ProgressionChapitre.objects.filter(
            etudiant=request.user,
            chapitre__matiere=matiere
        )
        
        stats = {
            'chapitres_total': matiere.chapitres.filter(actif=True).count(),
            'chapitres_commences': progressions.exclude(statut='non_commence').count(),
            'chapitres_termines': progressions.filter(statut='termine').count(),
            'progression_moyenne': progressions.aggregate(
                moyenne=Avg('pourcentage_completion')
            )['moyenne'] or 0,
            'temps_total': progressions.aggregate(
                total=Sum('temps_etudie')
            )['total'] or 0
        }
        
        return Response(stats)


