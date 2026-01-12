# cours/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.conf import settings
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import urlopen, Request
import json

from cours.models import Chapitre, ContenuChapitre
from cours.serializers import ChapitreListSerializer, ChapitreDetailSerializer, ContenuChapitreSerializer
from progression.models import ProgressionChapitre, ProgressionContenu
from progression.serializers import ProgressionChapitreSerializer
from django.http import FileResponse, Http404
import os



class ChapitreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les chapitres avec gestion de la progression
    """
    queryset = Chapitre.objects.filter(actif=True).select_related('matiere').prefetch_related(
        'contenus', 'prerequis'
    )
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['matiere', 'difficulte', 'matiere__niveau']
    search_fields = ['titre', 'description', 'matiere__nom']
    ordering_fields = ['numero', 'date_creation', 'duree_estimee']
    ordering = ['matiere', 'numero']

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action"""
        if self.action == 'retrieve':
            return ChapitreDetailSerializer
        return ChapitreListSerializer

    def get_queryset(self):
        """Filtre les chapitres selon les paramètres"""
        queryset = super().get_queryset()
        
        # Filtrer par matière si spécifié
        matiere_id = self.request.query_params.get('matiere', None)
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)
        
        # Filtrer par niveau de difficulté
        difficulte = self.request.query_params.get('difficulte', None)
        if difficulte:
            queryset = queryset.filter(difficulte=difficulte)
        
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def commencer(self, request, pk=None):
        """Commencer l'étude d'un chapitre"""
        # Vérifier les permissions d'accès aux cours
        try:
            from abonnements.services import PermissionService
            acces_autorise, message = PermissionService.verifier_acces_cours(request.user)
            if not acces_autorise:
                return Response({'error': message}, status=status.HTTP_403_FORBIDDEN)
        except ImportError:
            # Si le service n'est pas disponible, continuer sans restriction
            pass
        
        chapitre = self.get_object()
        
        with transaction.atomic():
            progression, created = ProgressionChapitre.objects.get_or_create(
                etudiant=request.user,
                chapitre=chapitre,
                defaults={
                    'statut': 'en_cours',
                    'date_debut': timezone.now()
                }
            )
            
            if not created and progression.statut == 'non_commence':
                progression.statut = 'en_cours'
                if not progression.date_debut:
                    progression.date_debut = timezone.now()
                progression.save()
        
        serializer = ProgressionChapitreSerializer(progression)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def marquer_contenu_lu(self, request, pk=None):
        """Marquer un contenu comme lu et mettre à jour la progression"""
        # Vérifier les permissions d'accès aux cours
        try:
            from abonnements.services import PermissionService
            acces_autorise, message = PermissionService.verifier_acces_cours(request.user)
            if not acces_autorise:
                return Response({'error': message}, status=status.HTTP_403_FORBIDDEN)
        except ImportError:
            # Si le service n'est pas disponible, continuer sans restriction
            pass
        
        chapitre = self.get_object()
        contenu_id = request.data.get('contenu_id')
        temps_lecture = request.data.get('temps_lecture', 0)
        
        if not contenu_id:
            return Response(
                {'error': 'contenu_id est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            contenu = get_object_or_404(ContenuChapitre, id=contenu_id, chapitre=chapitre)
            
            with transaction.atomic():
                # Créer ou mettre à jour la progression du contenu
                progression_contenu, created = ProgressionContenu.objects.get_or_create(
                    etudiant=request.user,
                    contenu=contenu,
                    defaults={
                        'lu': True,
                        'temps_lecture': temps_lecture,
                        'date_completion': timezone.now()
                    }
                )
                
                if not created:
                    progression_contenu.lu = True
                    progression_contenu.temps_lecture += temps_lecture
                    progression_contenu.date_completion = timezone.now()
                    progression_contenu.save()
                
                # Mettre à jour la progression du chapitre
                progression_chapitre = self._mettre_a_jour_progression_chapitre(
                    request.user, chapitre
                )
            
            return Response({
                'success': True,
                'progression_chapitre': {
                    'pourcentage_completion': progression_chapitre.pourcentage_completion,
                    'statut': progression_chapitre.statut
                }
            }, status=status.HTTP_200_OK)
            
        except ContenuChapitre.DoesNotExist:
            return Response(
                {'error': 'Contenu introuvable'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la mise à jour: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def marquer_temps_etudie(self, request, pk=None):
        """Ajouter du temps d'étude à un chapitre"""
        chapitre = self.get_object()
        temps_supplementaire = request.data.get('temps', 0)
        
        if not isinstance(temps_supplementaire, int) or temps_supplementaire <= 0:
            return Response(
                {'error': 'Le temps doit être un entier positif'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        progression, created = ProgressionChapitre.objects.get_or_create(
            etudiant=request.user,
            chapitre=chapitre,
            defaults={'statut': 'en_cours', 'date_debut': timezone.now()}
        )
        
        progression.temps_etudie += temps_supplementaire
        progression.save()
        
        serializer = ProgressionChapitreSerializer(progression)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def progression(self, request, pk=None):
        """Récupérer la progression détaillée d'un chapitre"""
        chapitre = self.get_object()
        
        try:
            progression = ProgressionChapitre.objects.get(
                etudiant=request.user,
                chapitre=chapitre
            )
            serializer = ProgressionChapitreSerializer(progression)
        except ProgressionChapitre.DoesNotExist:
            # Retourner une progression vide
            serializer = ProgressionChapitreSerializer({
                'chapitre': chapitre,
                'statut': 'non_commence',
                'pourcentage_completion': 0.0,
                'temps_etudie': 0,
                'date_debut': None,
                'date_completion': None
            })
        
        return Response(serializer.data)

    def _mettre_a_jour_progression_chapitre(self, etudiant, chapitre):
        """Met à jour la progression globale du chapitre"""
        progression_chapitre, created = ProgressionChapitre.objects.get_or_create(
            etudiant=etudiant,
            chapitre=chapitre,
            defaults={
                'statut': 'en_cours',
                'date_debut': timezone.now()
            }
        )
        
        # Calculer le pourcentage de completion
        contenus_total = chapitre.contenus.count()
        
        if contenus_total > 0:
            contenus_lus = ProgressionContenu.objects.filter(
                etudiant=etudiant,
                contenu__chapitre=chapitre,
                lu=True
            ).count()
            
            pourcentage = (contenus_lus / contenus_total) * 100
            progression_chapitre.pourcentage_completion = round(pourcentage, 2)
            
            # Mettre à jour le statut selon le pourcentage
            if pourcentage >= 100:
                progression_chapitre.statut = 'termine'
                if not progression_chapitre.date_completion:
                    progression_chapitre.date_completion = timezone.now()
            elif pourcentage > 0:
                progression_chapitre.statut = 'en_cours'
                if not progression_chapitre.date_debut:
                    progression_chapitre.date_debut = timezone.now()
            
            progression_chapitre.save()
        
        return progression_chapitre


class ContenuChapitreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les contenus de chapitre (lecture seule)
    """
    queryset = ContenuChapitre.objects.all().select_related('chapitre__matiere')
    serializer_class = ContenuChapitreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['chapitre', 'obligatoire']
    ordering = ['chapitre', 'ordre']

    def get_queryset(self):
        """Filtre les contenus selon les paramètres"""
        queryset = super().get_queryset()
        
        # Filtrer par chapitre si spécifié
        chapitre_id = self.request.query_params.get('chapitre', None)
        if chapitre_id:
            queryset = queryset.filter(chapitre_id=chapitre_id)
        
        return queryset

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def pdf(self, request, pk=None):
        """Servez le PDF en affichage inline, autorisé en iframe (X-Frame-Options)."""
        contenu = self.get_object()
        if not contenu.fichier_pdf:
            raise Http404("Aucun PDF pour ce contenu")
        try:
            file_handle = contenu.fichier_pdf.open('rb')
        except Exception:
            raise Http404("Fichier PDF introuvable")
        filename = os.path.basename(contenu.fichier_pdf.name)
        response = FileResponse(file_handle, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        # Autoriser l'embed cross-origin pour l'iframe front
        response['X-Frame-Options'] = 'ALLOWALL'
        return response


# Utilitaire interne pour extraire l'ID YouTube
def _extract_youtube_id(url: str) -> str:
    try:
        if not url:
            return ''
        parsed = urlparse(url)
        # Cas youtu.be/<id>
        if parsed.netloc in ('youtu.be', 'www.youtu.be'):
            return parsed.path.strip('/')
        # Cas youtube.com/watch?v=<id>
        if 'youtube' in parsed.netloc and parsed.path == '/watch':
            return parse_qs(parsed.query).get('v', [''])[0]
        # Cas youtube.com/embed/<id>
        if 'youtube' in parsed.netloc and parsed.path.startswith('/embed/'):
            return parsed.path.split('/embed/')[1].split('/')[0]
    except Exception:
        return ''
    return ''




@api_view(['GET'])
@permission_classes([AllowAny])
def youtube_meta(request):
    """Retourne les métadonnées publiques d'une vidéo YouTube.
    Si YOUTUBE_API_KEY est défini, utilise l'API v3 (snippet, contentDetails, statistics).
    Sinon, fallback minimal via oEmbed (titre, auteur, miniature).
    Query params: url=<youtube_url>
    """
    video_url = request.query_params.get('url', '')
    video_id = _extract_youtube_id(video_url)
    if not video_id:
        return Response({'error': 'URL YouTube invalide'}, status=status.HTTP_400_BAD_REQUEST)

    api_key = getattr(settings, 'YOUTUBE_API_KEY', None)
    try:
        if api_key:
            # API YouTube Data v3
            base = 'https://www.googleapis.com/youtube/v3/videos'
            query = urlencode({
                'id': video_id,
                'key': api_key,
                'part': 'snippet,contentDetails,statistics'
            })
            req = Request(f"{base}?{query}", headers={'User-Agent': 'ApprendsChap/1.0'})
            with urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            items = data.get('items', [])
            if not items:
                return Response({'error': 'Vidéo introuvable'}, status=status.HTTP_404_NOT_FOUND)
            item = items[0]
            snippet = item.get('snippet', {})
            stats = item.get('statistics', {})
            details = item.get('contentDetails', {})

            # Conversion ISO8601 PT#M#S en secondes
            def parse_iso8601_duration(d):
                import re
                m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
                if not m:
                    return 0
                h = int(m.group(1) or 0)
                mn = int(m.group(2) or 0)
                s = int(m.group(3) or 0)
                return h * 3600 + mn * 60 + s

            duration_seconds = parse_iso8601_duration(details.get('duration'))
            like_count = int(stats.get('likeCount', 0)) if stats.get('likeCount') is not None else None
            view_count = int(stats.get('viewCount', 0)) if stats.get('viewCount') is not None else None

            payload = {
                'id': video_id,
                'title': snippet.get('title'),
                'channel': snippet.get('channelTitle'),
                'thumbnail': (snippet.get('thumbnails', {}).get('medium', {}) or {}).get('url'),
                'duration_seconds': duration_seconds,
                'view_count': view_count,
                'like_count': like_count,
            }
            return Response(payload)
        else:
            # Fallback oEmbed (sans vues/likes)
            oembed = f"https://www.youtube.com/oembed?{urlencode({'url': video_url, 'format': 'json'})}"
            req = Request(oembed, headers={'User-Agent': 'ApprendsChap/1.0'})
            with urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            payload = {
                'id': video_id,
                'title': data.get('title'),
                'channel': data.get('author_name'),
                'thumbnail': data.get('thumbnail_url'),
                'duration_seconds': None,
                'view_count': None,
                'like_count': None,
            }
            return Response(payload)
    except Exception as e:
        return Response({'error': f'Impossible de récupérer les métadonnées: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)