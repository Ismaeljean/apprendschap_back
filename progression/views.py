# progression/views.py
from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone

from progression.models import ProgressionChapitre, ProgressionContenu, ProgressionMatiere
from progression.serializers import (
    ProgressionChapitreSerializer, 
    ProgressionChapitreListSerializer,
    ProgressionContenuSerializer,
    ProgressionStatsSerializer,
    ProgressionMatiereSerializer
)
from cours.models import Chapitre
from academic_structure.models import Matiere
from quiz.models import TentativeQuiz
from utilisateurs.models import Utilisateur


class ProgressionChapitreViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion de la progression des chapitres
    """
    serializer_class = ProgressionChapitreSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'chapitre__matiere', 'chapitre__difficulte']
    search_fields = ['chapitre__titre', 'chapitre__matiere__nom']
    ordering_fields = ['date_debut', 'date_completion', 'pourcentage_completion']
    ordering = ['-date_debut']

    def get_queryset(self):
        """Filtre les progressions pour l'utilisateur connecté"""
        return ProgressionChapitre.objects.filter(
            etudiant=self.request.user
        ).select_related(
            'chapitre__matiere',
            'etudiant'
        ).prefetch_related(
            'chapitre__contenus'
        )

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action"""
        if self.action == 'list':
            return ProgressionChapitreListSerializer
        return ProgressionChapitreSerializer

    def perform_create(self, serializer):
        """Assigne automatiquement l'étudiant connecté"""
        serializer.save(etudiant=self.request.user)

    def create(self, request, *args, **kwargs):
        """Création avec gestion d'erreurs améliorée"""
        try:
            # Vérifier si une progression existe déjà
            chapitre_id = request.data.get('chapitre')
            if chapitre_id:
                existing = ProgressionChapitre.objects.filter(
                    etudiant=request.user,
                    chapitre_id=chapitre_id
                ).exists()
                
                if existing:
                    return Response(
                        {"detail": "Une progression existe déjà pour ce chapitre."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            return Response(
                {"detail": f"Erreur lors de la création de la progression: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Mise à jour avec validation"""
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"Erreur lors de la mise à jour: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="mes-progressions")
    def mes_progressions(self, request):
        """Récupère toutes les progressions de l'utilisateur connecté"""
        progressions = self.get_queryset()
        
        # Filtres optionnels
        statut = request.query_params.get('statut')
        if statut:
            progressions = progressions.filter(statut=statut)
        
        matiere_id = request.query_params.get('matiere')
        if matiere_id:
            progressions = progressions.filter(chapitre__matiere_id=matiere_id)
        
        serializer = self.get_serializer(progressions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="statistiques")
    def statistiques(self, request):
        """Récupère les statistiques globales de progression"""
        user = request.user
        
        # Statistiques générales
        total_chapitres = Chapitre.objects.filter(actif=True).count()
        progressions = ProgressionChapitre.objects.filter(etudiant=user)
        
        # Statistiques des quiz
        tentatives_quiz = TentativeQuiz.objects.filter(etudiant=user)
        quiz_reussis = tentatives_quiz.filter(
            pourcentage__gte=F('quiz__note_passage')
        ).count()
        
        # Calculer les matières terminées
        matieres_terminees = 0
        matieres_stats = []
        matieres = Matiere.objects.annotate(
            total_chapitres=Count('chapitres', filter=Q(chapitres__actif=True))
        ).filter(total_chapitres__gt=0)
        
        for matiere in matieres:
            progressions_matiere = progressions.filter(chapitre__matiere=matiere)
            termines = progressions_matiere.filter(
                statut__in=['termine', 'maitrise']
            ).count()
            
            # Vérifier si la matière est terminée (tous les chapitres terminés)
            if termines == matiere.total_chapitres and matiere.total_chapitres > 0:
                matieres_terminees += 1
            
            matieres_stats.append({
                'matiere_id': matiere.id,
                'matiere_nom': matiere.nom,
                'matiere_couleur': getattr(matiere, 'couleur', '#6366f1'),
                'total_chapitres': matiere.total_chapitres,
                'chapitres_termines': termines,
                'pourcentage': round(
                    (termines / matiere.total_chapitres) * 100, 2
                ) if matiere.total_chapitres > 0 else 0.0
            })
        
        stats = {
            'total_chapitres': total_chapitres,
            'chapitres_commences': progressions.filter(
                statut__in=['en_cours', 'termine', 'maitrise']
            ).count(),
            'chapitres_termines': progressions.filter(statut='termine').count(),
            'chapitres_maitrises': progressions.filter(statut='maitrise').count(),
            'temps_total_etudie': progressions.aggregate(
                total=Sum('temps_etudie')
            )['total'] or 0,
            'quiz_reussis': quiz_reussis,
            'matieres_terminees': matieres_terminees,
            'pourcentage_global': 0.0,
            'matiere_stats': matieres_stats
        }
        
        # Calcul du pourcentage global
        if stats['total_chapitres'] > 0:
            chapitres_finis = stats['chapitres_termines'] + stats['chapitres_maitrises']
            stats['pourcentage_global'] = round(
                (chapitres_finis / stats['total_chapitres']) * 100, 2
            )
        
        serializer = ProgressionStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="statistiques-utilisateur")
    def statistiques_utilisateur(self, request):
        """Récupère les statistiques spécifiques à l'utilisateur (jours consécutifs, classement, etc.)"""
        user = request.user
        
        # Calculer les jours consécutifs (simulation pour l'instant)
        jours_consecutifs = 7  # À remplacer par un vrai calcul
        
        # Calculer les points totaux (simulation pour l'instant)
        progressions = ProgressionChapitre.objects.filter(etudiant=user)
        points_totaux = progressions.filter(statut='termine').count() * 100  # 100 points par chapitre terminé
        
        # Calculer le temps total d'étude
        temps_total_etudie = progressions.aggregate(
            total=Sum('temps_etudie')
        )['total'] or 0
        
        # Calculer le classement (simulation pour l'instant)
        total_utilisateurs = Utilisateur.objects.filter(role='eleve').count()
        classement = 12  # À remplacer par un vrai calcul de classement
        
        stats = {
            'jours_consecutifs': jours_consecutifs,
            'points_totaux': points_totaux,
            'temps_total_etudie': temps_total_etudie,
            'classement': classement
        }
        
        return Response(stats)

    @action(detail=True, methods=["post"], url_path="reinitialiser")
    def reinitialiser(self, request, pk=None):
        """Remet à zéro la progression d'un chapitre"""
        progression = self.get_object()
        
        # Supprimer les progressions de contenu associées
        ProgressionContenu.objects.filter(
            etudiant=request.user,
            contenu__chapitre=progression.chapitre
        ).delete()
        
        # Réinitialiser la progression du chapitre
        progression.statut = 'non_commence'
        progression.pourcentage_completion = 0.0
        progression.temps_etudie = 0
        progression.date_completion = None
        progression.save()
        
        serializer = self.get_serializer(progression)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="en-cours")
    def en_cours(self, request):
        """Récupère les chapitres en cours d'étude"""
        progressions = self.get_queryset().filter(statut='en_cours')
        serializer = self.get_serializer(progressions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="termines")
    def termines(self, request):
        """Récupère les chapitres terminés"""
        progressions = self.get_queryset().filter(
            statut__in=['termine', 'maitrise']
        )
        serializer = self.get_serializer(progressions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="par-chapitre/(?P<chapitre_id>[^/.]+)")
    def par_chapitre(self, request, chapitre_id=None):
        """Récupère la progression pour un chapitre spécifique"""
        try:
            progression = ProgressionChapitre.objects.get(
                etudiant=request.user,
                chapitre_id=chapitre_id
            )
            serializer = self.get_serializer(progression)
            return Response(serializer.data)
        except ProgressionChapitre.DoesNotExist:
            # Créer une progression par défaut
            from cours.models import Chapitre
            try:
                chapitre = Chapitre.objects.get(id=chapitre_id, actif=True)
                progression = ProgressionChapitre.objects.create(
                    etudiant=request.user,
                    chapitre=chapitre,
                    statut='non_commence'
                )
                serializer = self.get_serializer(progression)
                return Response(serializer.data)
            except Chapitre.DoesNotExist:
                return Response(
                    {'error': 'Chapitre introuvable'}, 
                    status=status.HTTP_404_NOT_FOUND
                )


class ProgressionContenuViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion de la progression des contenus
    """
    serializer_class = ProgressionContenuSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['lu', 'contenu', 'contenu__chapitre', 'contenu__obligatoire']
    ordering_fields = ['date_debut', 'date_completion', 'temps_lecture']
    ordering = ['contenu__chapitre', 'contenu__ordre']

    def get_queryset(self):
        """Filtre les progressions de contenu pour l'utilisateur connecté"""
        return ProgressionContenu.objects.filter(
            etudiant=self.request.user
        ).select_related(
            'contenu__chapitre__matiere',
            'etudiant'
        )

    def perform_create(self, serializer):
        """Assigne automatiquement l'étudiant connecté"""
        serializer.save(etudiant=self.request.user)

    @action(detail=False, methods=["get"], url_path="par-chapitre/(?P<chapitre_id>[^/.]+)")
    def par_chapitre(self, request, chapitre_id=None):
        """Récupère les progressions de contenu pour un chapitre donné"""
        progressions = self.get_queryset().filter(
            contenu__chapitre_id=chapitre_id
        )
        serializer = self.get_serializer(progressions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="marquer-plusieurs-lus")
    def marquer_plusieurs_lus(self, request):
        """Marque plusieurs contenus comme lus d'un coup"""
        contenu_ids = request.data.get('contenu_ids', [])
        temps_lecture = request.data.get('temps_lecture', 0)
        
        if not contenu_ids:
            return Response(
                {'error': 'contenu_ids est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = 0
        progressions_updated = []
        
        for contenu_id in contenu_ids:
            try:
                progression, created = ProgressionContenu.objects.get_or_create(
                    etudiant=request.user,
                    contenu_id=contenu_id,
                    defaults={
                        'lu': True,
                        'temps_lecture': temps_lecture,
                        'date_completion': timezone.now()
                    }
                )
                
                if not created and not progression.lu:
                    progression.lu = True
                    progression.temps_lecture += temps_lecture
                    progression.date_completion = timezone.now()
                    progression.save()
                
                progressions_updated.append(progression)
                updated_count += 1
                
            except Exception:
                continue
        
        return Response({
            'success': True,
            'updated_count': updated_count,
            'progressions': ProgressionContenuSerializer(
                progressions_updated, many=True
            ).data
        })

    @action(detail=False, methods=["post"], url_path="update-temps-lecture")
    def update_temps_lecture(self, request):
        """Met à jour le temps de lecture pour un contenu"""
        contenu_id = request.data.get('contenu_id')
        temps_lecture = request.data.get('temps_lecture', 0)
        
        if not contenu_id:
            return Response(
                {'error': 'contenu_id est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            progression, created = ProgressionContenu.objects.get_or_create(
                etudiant=request.user,
                contenu_id=contenu_id,
                defaults={'temps_lecture': temps_lecture}
            )
            
            if not created:
                # Remplacer le temps au lieu de l'additionner
                progression.temps_lecture = temps_lecture
                progression.save()
            
            # Mettre à jour aussi la progression du chapitre ET de la matière
            self._update_chapitre_progression(progression.contenu.chapitre)
            self._update_matiere_progression(progression.contenu.chapitre.matiere)
            
            return Response({
                'success': True,
                'progression': ProgressionContenuSerializer(progression).data
            })
            
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la mise à jour: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _update_chapitre_progression(self, chapitre):
        """Met à jour la progression du chapitre basée sur les contenus"""
        from cours.models import ContenuChapitre
        
        # Créer ou récupérer la progression du chapitre
        progression_chapitre, created = ProgressionChapitre.objects.get_or_create(
            etudiant=self.request.user,
            chapitre=chapitre,
            defaults={'statut': 'en_cours'}
        )
        
        # Calculer le temps total étudié (somme des temps de lecture des contenus)
        progressions_contenu = ProgressionContenu.objects.filter(
            etudiant=self.request.user,
            contenu__chapitre=chapitre
        )
        
        temps_total = sum(p.temps_lecture for p in progressions_contenu)
        progression_chapitre.temps_etudie = temps_total
        
        # Calculer le pourcentage basé sur les contenus lus
        total_contenus = ContenuChapitre.objects.filter(chapitre=chapitre).count()
        contenus_lus = progressions_contenu.filter(lu=True).count()
        
        if total_contenus > 0:
            progression_chapitre.pourcentage_completion = (contenus_lus / total_contenus) * 100
            
            # Mettre à jour le statut
            if contenus_lus == total_contenus:
                progression_chapitre.statut = 'termine'
                progression_chapitre.date_completion = timezone.now()
            elif contenus_lus > 0:
                progression_chapitre.statut = 'en_cours'
        
        progression_chapitre.save()
        return progression_chapitre

    def _update_matiere_progression(self, matiere):
        """Met à jour la progression globale d'une matière"""
        progression_matiere, created = ProgressionMatiere.objects.get_or_create(
            etudiant=self.request.user,
            matiere=matiere,
            defaults={'statut': 'non_commence'}
        )
        
        # Recalculer automatiquement la progression
        progression_matiere.calculer_progression()
        progression_matiere.save()
        
        return progression_matiere


class ProgressionMatiereViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion de la progression par matière
    """
    serializer_class = ProgressionMatiereSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['statut', 'matiere', 'matiere__niveau']
    ordering_fields = ['date_debut', 'date_completion', 'pourcentage_completion', 'temps_etudie_total']
    ordering = ['-date_debut']

    def get_queryset(self):
        """Filtre les progressions de matière pour l'utilisateur connecté"""
        return ProgressionMatiere.objects.filter(
            etudiant=self.request.user
        ).select_related(
            'matiere__niveau',
            'etudiant'
        )

    def perform_create(self, serializer):
        """Assigne automatiquement l'utilisateur connecté"""
        progression = serializer.save(etudiant=self.request.user)
        progression.calculer_progression()

    @action(detail=False, methods=["get"], url_path="par-matiere")
    def par_matiere(self, request):
        """Récupère ou crée la progression pour une matière spécifique"""
        matiere_id = request.query_params.get('matiere_id')
        
        if not matiere_id:
            return Response(
                {'error': 'matiere_id est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            matiere = Matiere.objects.get(id=matiere_id)
        except Matiere.DoesNotExist:
            return Response(
                {'error': 'Matière introuvable'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtenir ou créer la progression
        progression, created = ProgressionMatiere.objects.get_or_create(
            etudiant=request.user,
            matiere=matiere,
            defaults={'statut': 'non_commence'}
        )
        
        # Recalculer la progression à partir des contenus
        progression.calculer_progression()
        progression.save()
        
        serializer = self.get_serializer(progression)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="recalculer")
    def recalculer_progression(self, request, pk=None):
        """Recalcule manuellement la progression d'une matière"""
        progression = self.get_object()
        progression.calculer_progression()
        progression.save()
        
        serializer = self.get_serializer(progression)
        return Response({
            'success': True,
            'progression': serializer.data
        })

    @action(detail=False, methods=["get"], url_path="propres")
    def progressions_propres(self, request):
        """
        NOUVEL endpoint qui retourne seulement les progressions propres 
        (sans doublons, seulement matières avec vraie progression)
        """
        try:
            # Récupérer seulement les matières qui ont des progressions de chapitre
            from cours.models import Chapitre
            matieres_avec_progression = ProgressionChapitre.objects.filter(
                etudiant=request.user
            ).values_list('chapitre__matiere', flat=True).distinct()
            
            progressions_propres = []
            
            for matiere_id in matieres_avec_progression:
                try:
                    matiere = Matiere.objects.get(id=matiere_id, active=True)
                    
                    # Calculer les vraies données à la volée
                    chapitres_matiere = Chapitre.objects.filter(matiere=matiere, actif=True)
                    total_chapitres = chapitres_matiere.count()
                    
                    if total_chapitres == 0:
                        continue
                    
                    progressions_chapitre = ProgressionChapitre.objects.filter(
                        etudiant=request.user,
                        chapitre__matiere=matiere
                    )
                    
                    chapitres_termines = progressions_chapitre.filter(statut='termine').count()
                    temps_total = progressions_chapitre.aggregate(
                        total=Sum('temps_etudie')
                    )['total'] or 0
                    
                    pourcentage = round((chapitres_termines / total_chapitres) * 100, 1) if total_chapitres > 0 else 0
                    
                    if chapitres_termines == total_chapitres:
                        statut = 'termine'
                    elif chapitres_termines > 0:
                        statut = 'en_cours'
                    else:
                        statut = 'non_commence'
                    
                    # Créer des données propres pour la réponse
                    progression_data = {
                        'id': f'calc_{matiere.id}',
                        'matiere': {
                            'id': matiere.id,
                            'nom': matiere.nom,
                            'niveau': {
                                'id': matiere.niveau.id,
                                'nom': matiere.niveau.nom
                            } if matiere.niveau else None
                        },
                        'statut': statut,
                        'pourcentage_completion': pourcentage,
                        'temps_etudie_total': temps_total,
                        'nombre_chapitres_termines': chapitres_termines,
                        'nombre_chapitres_total': total_chapitres,
                        'date_debut': progressions_chapitre.first().date_debut if progressions_chapitre.exists() else timezone.now(),
                        'date_completion': None
                    }
                    
                    progressions_propres.append(progression_data)
                    
                except Matiere.DoesNotExist:
                    continue
            
            return Response(progressions_propres)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)


# Alias pour compatibilité avec l'ancien nom
ProgressionViewSet = ProgressionChapitreViewSet