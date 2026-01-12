# examens/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F
from django.http import FileResponse, Http404
from examens.models import Examen, TypeExamen
from examens.serializers import ExamenSerializer, TypeExamenSerializer
import os
import uuid

class ExamenViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les examens avec filtrage et téléchargement
    """
    queryset = Examen.objects.filter(actif=True)
    serializer_class = ExamenSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_examen', 'matiere', 'annee', 'session', 'difficulte']
    search_fields = ['titre', 'description']
    ordering_fields = ['annee', 'titre']
    ordering = ['-annee']

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def telecharger(self, request, pk=None):
        """Incrémenter le compteur de téléchargements"""
        examen = self.get_object()
        
        # Vérifier les permissions d'accès aux examens
        try:
            from abonnements.services import PermissionService
            acces_autorise, message = PermissionService.verifier_acces_examen(request.user, examen.id)
            if not acces_autorise:
                return Response({'error': message}, status=status.HTTP_403_FORBIDDEN)
        except ImportError:
            # Si le service n'est pas disponible, continuer sans restriction
            pass
        except Exception as e:
            # En cas d'erreur, continuer sans restriction pour ne pas bloquer
            pass
        
        examen.nombre_telechargements = F('nombre_telechargements') + 1
        examen.save(update_fields=['nombre_telechargements'])
        
        # Recharger l'objet pour obtenir la valeur mise à jour
        examen.refresh_from_db()
        
        serializer = self.get_serializer(examen)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def sujet(self, request, pk=None):
        """Servir le PDF du sujet en affichage inline pour iframe"""
        examen = self.get_object()
        if not examen.fichier_sujet:
            raise Http404("Aucun sujet PDF pour cet examen")
        try:
            file_handle = examen.fichier_sujet.open('rb')
        except Exception:
            raise Http404("Fichier sujet PDF introuvable")
        filename = os.path.basename(examen.fichier_sujet.name)
        response = FileResponse(file_handle, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['X-Frame-Options'] = 'ALLOWALL'  # Autoriser iframe cross-origin pour le front
        return response

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def correction(self, request, pk=None):
        """Servir le PDF de la correction en affichage inline pour iframe"""
        examen = self.get_object()
        if not examen.fichier_correction:
            raise Http404("Aucune correction PDF pour cet examen")
        try:
            file_handle = examen.fichier_correction.open('rb')
        except Exception:
            raise Http404("Fichier correction PDF introuvable")
        filename = os.path.basename(examen.fichier_correction.name)
        response = FileResponse(file_handle, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['X-Frame-Options'] = 'ALLOWALL'  # Autoriser iframe cross-origin pour le front
        return response


class TypeExamenViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les types d'examens
    """
    queryset = TypeExamen.objects.all()
    serializer_class = TypeExamenSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
