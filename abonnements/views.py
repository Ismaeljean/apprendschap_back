# abonnements/views.py
import requests
import json
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction, models
from rest_framework import viewsets, status, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from .models import (
    Abonnement, PackAbonnement, PaiementWave, 
    PackFamilial, BonusParrainage, Parrainage
)
from .serializers import (
    AbonnementSerializer, AbonnementDetailSerializer, PackAbonnementSerializer,
    PaiementWaveSerializer, PackFamilialSerializer, DemandePaiementSerializer,
    CallbackWaveSerializer, StatistiquesAbonnementSerializer,
    BonusParrainageSerializer, ParrainageSerializer
)
from .services import (
    WaveService, AbonnementService, StatistiquesService, PackService,
    ParrainageService
)
from utilisateurs.models import Utilisateur





class PackAbonnementViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les packs d'abonnement"""
    queryset = PackAbonnement.objects.filter(actif=True)
    serializer_class = PackAbonnementSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def packs_speciaux(self, request):
        """Récupère les packs spéciaux"""
        packs = PackAbonnement.objects.filter(
            pack_special=True,
            actif=True
        ).exclude(
            nom="Pack de Bienvenue Parrainage"
        )
        serializer = self.get_serializer(packs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='avec-essai-gratuit')
    def avec_essai_gratuit(self, request):
        """Récupère les packs avec essai gratuit"""
        packs = PackAbonnement.objects.filter(
            actif=True, 
            offre_semaine_gratuite=True
        )
        serializer = self.get_serializer(packs, many=True)
        return Response(serializer.data)


class PackFamilialViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les packs familiaux"""
    queryset = PackFamilial.objects.filter(actif=True)
    serializer_class = PackFamilialSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Récupérer les packs familiaux avec real_id"""
        try:
            packs_famille = PackFamilial.objects.filter(actif=True).order_by('nombre_enfants')
            
            packs_data = []
            for pack in packs_famille:
                packs_data.append({
                    'id': f'pack-famille-{pack.nombre_enfants}',
                    'real_id': pack.id,  # 🔧 AJOUT : ID réel de la base de données
                    'nom': pack.nom,
                    'prix': float(pack.prix),
                    'prix_reduit': float(pack.prix_reduit) if pack.prix_reduit else None,  # 🔧 AJOUT : Prix réduit
                    'nombre_enfants': pack.nombre_enfants,
                    'type_pack': 'famille',
                    'description': pack.description,
                    'popular': pack.nombre_enfants == 3,  # Pack 3 enfants populaire
                    'actif': pack.actif,
                    'duree_jours': pack.duree_jours,
                    'periode': pack.periode,
                    'reduction_pourcentage': pack.reduction_pourcentage
                })
            
            return Response(packs_data)
            
        except Exception as e:
            return Response({
                'detail': f'Erreur lors de la récupération des packs familiaux: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='souscrire-pack-famille')
    def souscrire_pack_famille(self, request):
        """Souscrire à un pack familial"""
        try:
            pack_id = request.data.get('pack_id')
            if not pack_id:
                return Response({'error': 'Pack ID requis'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Récupérer le pack
            pack = get_object_or_404(PackFamilial, id=pack_id, actif=True)
            
            # Vérifier que l'utilisateur est un parent
            if request.user.role != 'parent':
                return Response({'error': 'Seuls les parents peuvent souscrire à un pack familial'}, 
                              status=status.HTTP_403_FORBIDDEN)
            
            # Simuler la souscription (à adapter selon votre logique métier)
            return Response({
                'message': f'Pack {pack.nom} souscrit avec succès',
                'pack': {
                    'id': pack.id,
                    'nom': pack.nom,
                    'prix': pack.prix,
                    'devise': pack.devise
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AbonnementViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les abonnements"""
    serializer_class = AbonnementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Abonnement.objects.filter(utilisateur=self.request.user)
    
    def _get_nb_enfants_from_code(self, code):
        """Déterminer le nombre d'enfants max basé sur le code du pack"""
        if not code:
            return 2
        if 'pack-1' in code or 'gratuit' in code.lower():
            return 1
        elif 'pack-2' in code:
            return 2
        elif 'pack-3' in code:
            return 3
        elif 'pack-4' in code:
            return 4
        else:
            return 2  # Par défaut
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AbonnementDetailSerializer
        return AbonnementSerializer

    def perform_create(self, serializer):
        """Assigne automatiquement l'utilisateur connecté"""
        serializer.save(utilisateur=self.request.user)

    @action(detail=True, methods=['post'])
    def suspendre(self, request, pk=None):
        """Suspendre un abonnement"""
        try:
            abonnement = Abonnement.objects.get(id=pk, utilisateur=request.user)
            abonnement.statut = 'suspendu'
            abonnement.actif = False
            abonnement.save()
            return Response({'detail': 'Abonnement suspendu avec succès'})
        except Abonnement.DoesNotExist:
            return Response({'detail': 'Abonnement non trouvé'}, status=404)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=True, methods=['post'])
    def reactiver(self, request, pk=None):
        """Réactiver un abonnement"""
        try:
            abonnement = Abonnement.objects.get(id=pk, utilisateur=request.user)
            abonnement.statut = 'actif'
            abonnement.actif = True
            abonnement.save()
            return Response({'detail': 'Abonnement réactivé avec succès'})
        except Abonnement.DoesNotExist:
            return Response({'detail': 'Abonnement non trouvé'}, status=404)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['get'], url_path='mon-abonnement')
    def mon_abonnement(self, request):
        """Récupérer l'abonnement actuel de l'utilisateur connecté"""
        try:
            # Récupérer l'abonnement actif de l'utilisateur
            abonnement = Abonnement.objects.filter(
                utilisateur=request.user,
                actif=True
            ).select_related('pack').first()
            
            if not abonnement:
                # Si aucun abonnement actif, retourner des valeurs par défaut
                return Response({
                    'abonnement_actif': False,
                    'type_abonnement': 'pack-2',  # Plan par défaut
                    'message': 'Aucun abonnement actif'
                }, status=status.HTTP_200_OK)
            
            return Response({
                'abonnement_actif': True,
                'id': abonnement.id,
                'type_abonnement': abonnement.pack.code_auto if abonnement.pack else 'pack-2',
                'nom_pack': abonnement.pack.nom if abonnement.pack else 'Pack 2 Enfants',
                'statut': abonnement.statut,
                'date_debut': abonnement.date_debut,
                'date_fin': abonnement.date_fin,
                'prix': float(abonnement.pack.prix) if abonnement.pack and abonnement.pack.prix else 15.0,
                'nb_enfants_max': self._get_nb_enfants_from_code(abonnement.pack.code_auto if abonnement.pack else 'pack-2'),
                'actif': abonnement.actif
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'detail': f'Erreur lors de la récupération de l\'abonnement: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='packs-famille')
    def packs_famille(self, request):
        """Récupérer les packs famille disponibles"""
        try:
            # Récupérer tous les packs famille depuis le modèle PackFamilial
            packs_famille = PackFamilial.objects.filter(
                actif=True
            ).order_by('nombre_enfants')
            
            packs_data = []
            for pack in packs_famille:
                packs_data.append({
                    'id': f'pack-famille-{pack.nombre_enfants}',
                    'real_id': pack.id,  # 🔧 AJOUT : ID réel de la base de données
                    'nom': pack.nom,
                    'prix': float(pack.prix),
                    'prix_reduit': float(pack.prix_reduit) if pack.prix_reduit else None,  # 🔧 AJOUT : Prix réduit
                    'nombre_enfants': pack.nombre_enfants,
                    'type_pack': 'famille',
                    'description': pack.description,
                    'popular': pack.nombre_enfants == 3,  # Pack 3 enfants populaire
                    'actif': pack.actif,
                    'duree_jours': pack.duree_jours,
                    'periode': pack.periode,
                    'reduction_pourcentage': pack.reduction_pourcentage
                })
            
            # Si aucun pack famille en base, retourner des packs par défaut
            if not packs_data:
                # Récupérer les packs familiaux depuis la base de données
                packs_familiaux_db = PackAbonnement.objects.filter(
                    type_pack='famille',
                    actif=True
                ).order_by('prix')
                
                packs_data = []
                for i, pack in enumerate(packs_familiaux_db):
                    packs_data.append({
                        'id': f'pack-famille-{pack.id}',
                        'real_id': pack.id,  # ID réel de la base de données
                        'nom': pack.nom,
                        'prix': float(pack.prix),
                        'nombre_enfants': 2 + i,  # 2, 3, 4 enfants
                        'type_pack': 'famille',
                        'description': pack.description,
                        'popular': i == 1,  # Le deuxième pack est populaire
                        'actif': pack.actif,
                        'duree_jours': pack.duree_jours,
                        'periode': pack.periode,
                        'reduction_pourcentage': pack.reduction_pourcentage
                    })
            
            return Response({
                'packs': packs_data,
                'total': len(packs_data),
                'message': f'{len(packs_data)} packs famille disponibles'
            })
            
        except Exception as e:
            return Response({
                'detail': f'Erreur lors de la récupération des packs famille: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def renouveler(self, request, pk=None):
        """Renouveler un abonnement"""
        try:
            resultat = AbonnementService.renouveler_abonnement(pk, request.user)
            if resultat['success']:
                return Response(resultat)
            else:
                return Response({'detail': resultat['error']}, status=400)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'])
    def verifier_expiration(self, request):
        """Vérifie si l'abonnement de l'utilisateur a expiré et le traite si nécessaire"""
        try:
            from .services import ExpirationService
            
            # Vérifier si l'utilisateur a un abonnement expiré
            abonnement_expire = Abonnement.objects.filter(
                utilisateur=request.user,
                actif=True,
                date_fin__lt=timezone.now(),
                statut__in=['actif', 'essai']
            ).exclude(
                pack__type_pack='gratuit'
            ).first()
            
            if abonnement_expire:
                # Traiter l'expiration automatiquement
                resultat = ExpirationService.traiter_expiration_abonnement(abonnement_expire)
                
                return Response({
                    'expiration_traitee': True,
                    'message': 'Votre abonnement a expiré et vous avez été transféré vers le pack gratuit',
                    'details': resultat
                })
            else:
                return Response({
                    'expiration_traitee': False,
                    'message': 'Aucune expiration à traiter'
                })
                
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=500)

    @action(detail=False, methods=['get'])
    def actuel(self, request):
        """Récupère l'abonnement actuel de l'utilisateur"""
        try:
            from .services import PermissionService
            
            # Utiliser la logique centralisée pour récupérer l'abonnement actuel
            abonnement = PermissionService.get_abonnement_actuel(request.user)
            
            if abonnement:
                serializer = AbonnementDetailSerializer(abonnement)
                return Response(serializer.data)
            else:
                return Response({'detail': 'Aucun abonnement actif'}, status=404)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Récupère les statistiques d'utilisation de l'abonnement"""
        try:
            # Récupérer l'abonnement actuel
            abonnement = Abonnement.objects.filter(
                utilisateur=request.user,
                actif=True
            ).first()
            
            if abonnement:
                # Utiliser le service existant
                from .services import StatistiquesService
                stats = StatistiquesService.get_utilisation_mensuelle(abonnement)
                return Response(stats)
            else:
                # Retourner des statistiques vides si pas d'abonnement
                return Response({
                    'cours_suivis': 0,
                    'quiz_realises': 0,
                    'temps_etude_secondes': 0,
                    'mois_reference': timezone.now().month,
                    'annee_reference': timezone.now().year
                })
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['get'])
    def restrictions(self, request):
        """Récupère le statut des restrictions pour l'utilisateur"""
        try:
            # Récupérer l'abonnement actuel
            abonnement = Abonnement.objects.filter(
                utilisateur=request.user,
                actif=True
            ).first()
            
            if abonnement:
                # Utiliser le service existant
                from .services import PermissionService
                statut = PermissionService.get_statut_restrictions(request.user)
                return Response(statut)
            else:
                # Retourner des restrictions par défaut si pas d'abonnement
                return Response({
                    'pack_nom': 'Aucun abonnement',
                    'jours_restants': 0,
                    'restriction_temps': False,
                    'restriction_contenu': False,
                    'restriction_examens': False,
                    'cours': {'utilises': 0, 'max': 0, 'pourcentage': 0, 'limite_atteinte': False},
                    'quiz': {'utilises': 0, 'max': 0, 'pourcentage': 0, 'limite_atteinte': False},
                    'examens': {'utilises': 0, 'max': 0, 'pourcentage': 0, 'limite_atteinte': False},
                    'permissions': {
                        'cours_premium': False,
                        'ia_standard': False,
                        'ia_prioritaire': False,
                        'certificats': False,
                        'contenu_hors_ligne': False,
                        'communautaire': False,
                        'support_prioritaire': False
                    },
                    'incitations': {
                        'upgrade_reminder': True,
                        'teaser_content': True
                    }
                })
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'])
    def forcer_expiration(self, request):
        """Force l'expiration d'un abonnement (pour tests)"""
        try:
            from .services import ExpirationService
            from django.utils import timezone
            
            # Récupérer l'abonnement actuel de l'utilisateur
            abonnement_actuel = Abonnement.objects.filter(
                utilisateur=request.user,
                actif=True
            ).first()
            
            if not abonnement_actuel:
                return Response({
                    'success': False,
                    'error': 'Aucun abonnement actif trouvé'
                }, status=400)
            
            if abonnement_actuel.pack.type_pack == 'gratuit':
                return Response({
                    'success': False,
                    'error': 'Impossible de faire expirer un pack gratuit'
                }, status=400)
            
            # Forcer l'expiration en modifiant la date de fin
            abonnement_actuel.date_fin = timezone.now() - timezone.timedelta(days=1)
            abonnement_actuel.save()
            
            # Traiter l'expiration
            resultat = ExpirationService.traiter_expiration_abonnement(abonnement_actuel)
            
            return Response({
                'success': True,
                'message': 'Expiration forcée et traitée',
                'details': resultat
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @action(detail=False, methods=['post'])
    def verifier_acces(self, request):
        """Vérifie l'accès à une fonctionnalité spécifique"""
        try:
            from .services import PermissionService
            
            fonctionnalite = request.data.get('fonctionnalite')
            ressource_id = request.data.get('ressource_id')
            
            if fonctionnalite == 'cours':
                acces, message = PermissionService.verifier_acces_cours(
                    request.user, ressource_id
                )
            elif fonctionnalite == 'quiz':
                acces, message = PermissionService.verifier_acces_quiz(
                    request.user, ressource_id
                )
            elif fonctionnalite == 'examen':
                acces, message = PermissionService.verifier_acces_examen(
                    request.user, ressource_id
                )
            elif fonctionnalite == 'ia':
                type_ia = request.data.get('type_ia', 'standard')
                acces, message = PermissionService.verifier_acces_ia(
                    request.user, type_ia
                )
            elif fonctionnalite == 'certificats':
                acces, message = PermissionService.verifier_acces_certificats(request.user)
            elif fonctionnalite == 'contenu_hors_ligne':
                acces, message = PermissionService.verifier_acces_contenu_hors_ligne(request.user)
            else:
                return Response(
                    {'detail': 'Fonctionnalité non reconnue'}, 
                    status=400
                )
            
            return Response({
                'acces': acces,
                'message': message,
                'fonctionnalite': fonctionnalite,
                'ressource_id': ressource_id
            })
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'], url_path='verifier-examen-limitations')
    def verifier_acces_examen_limitations(self, request):
        """
        NOUVEL endpoint pour vérifier l'accès aux examens avec limitations
        N'AFFECTE PAS l'endpoint verifier_acces_examen existant
        """
        try:
            from .services import PermissionService
            
            examen_id = request.data.get('examen_id')
            
            if not examen_id:
                return Response(
                    {'detail': 'examen_id requis'}, 
                    status=400
                )
            
            # Utiliser la NOUVELLE fonction
            acces, message = PermissionService.verifier_acces_examen_avec_limitations(
                request.user, examen_id
            )
            
            response_data = {
                'acces': acces,
                'message': message,
                'examen_id': examen_id,
                'deja_consulte': False
            }
            
            if acces:
                # Vérifier s'il était déjà consulté (NOUVELLE fonction cache simple)
                deja_consulte = PermissionService.examen_deja_consulte_cache_simple(
                    request.user, examen_id
                )
                response_data['deja_consulte'] = deja_consulte
                
                # Si pas déjà consulté, marquer comme consulté
                if not deja_consulte:
                    PermissionService.marquer_examen_consulte_cache_simple(request.user, examen_id)
                    nouveau_compteur = PermissionService.incrementer_compteur_examens(request.user)
                    response_data['marque_comme_consulte'] = True
                    response_data['nouveau_compteur'] = nouveau_compteur
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='verifier-contenu')
    def verifier_acces_contenu(self, request):
        """Vérifie l'accès à un contenu spécifique et marque comme consulté si autorisé"""
        try:
            from .services import PermissionService
            
            contenu_id = request.data.get('contenu_id')
            
            if not contenu_id:
                return Response(
                    {'detail': 'contenu_id requis'}, 
                    status=400
                )
            
            # Vérifier l'accès
            acces, message = PermissionService.verifier_acces_cours(
                request.user, contenu_id
            )
            
            response_data = {
                'acces': acces,
                'message': message,
                'contenu_id': contenu_id,
                'deja_consulte': False
            }
            
            if acces:
                # Vérifier s'il était déjà consulté
                deja_consulte = PermissionService.contenu_deja_consulte(
                    request.user, contenu_id
                )
                response_data['deja_consulte'] = deja_consulte
                
                # Si pas déjà consulté, initier la progression (accès sans marquer comme terminé)
                if not deja_consulte:
                    success, message_marquage = PermissionService.initier_progression_contenu(
                        request.user, contenu_id
                    )
                    response_data['marque_comme_consulte'] = success
                    response_data['message_marquage'] = message_marquage
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='marquer-contenu-termine')
    def marquer_contenu_termine(self, request):
        """
        NOUVEL endpoint pour marquer un contenu comme terminé (via bouton)
        N'AFFECTE PAS les endpoints existants
        """
        try:
            from .services import PermissionService
            
            contenu_id = request.data.get('contenu_id')
            
            if not contenu_id:
                return Response(
                    {'detail': 'contenu_id requis'}, 
                    status=400
                )
            
            # Utiliser la fonction qui marque vraiment comme terminé
            success, message = PermissionService.marquer_contenu_consulte_correctement(
                request.user, contenu_id
            )
            
            response_data = {
                'success': success,
                'message': message,
                'contenu_id': contenu_id,
                'action': 'marque_comme_termine'
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='nettoyer-progressions-matieres')
    def nettoyer_progressions_matieres(self, request):
        """
        NOUVEL endpoint pour nettoyer et corriger les progressions par matière
        N'AFFECTE PAS les endpoints existants
        """
        try:
            from .services import PermissionService
            
            # Nettoyer et recalculer les progressions matières
            progressions_propres = PermissionService.nettoyer_et_recalculer_progressions_matieres(request.user)
            
            # Formater la réponse
            response_data = {
                'success': True,
                'message': f'Nettoyage terminé: {len(progressions_propres)} progressions propres',
                'progressions': []
            }
            
            for progression in progressions_propres:
                response_data['progressions'].append({
                    'matiere': progression.matiere.nom,
                    'chapitres_termines': progression.nombre_chapitres_termines,
                    'chapitres_total': progression.nombre_chapitres_total,
                    'pourcentage': progression.pourcentage_completion,
                    'statut': progression.statut,
                    'temps_total': progression.temps_etudie_total
                })
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='recalculer-progressions-matieres')
    def recalculer_progressions_matieres(self, request):
        """
        NOUVEL endpoint pour recalculer les progressions par matière
        N'AFFECTE PAS les endpoints existants
        """
        try:
            from .services import PermissionService
            
            # Recalculer toutes les progressions matières de l'utilisateur
            progressions_mises_a_jour = PermissionService.recalculer_toutes_progressions_matieres(request.user)
            
            # Formater la réponse
            response_data = {
                'success': True,
                'message': f'{len(progressions_mises_a_jour)} progressions matières mises à jour',
                'progressions': []
            }
            
            for progression in progressions_mises_a_jour:
                response_data['progressions'].append({
                    'matiere': progression.matiere.nom,
                    'chapitres_termines': progression.nombre_chapitres_termines,
                    'chapitres_total': progression.nombre_chapitres_total,
                    'pourcentage': progression.pourcentage_completion,
                    'statut': progression.statut,
                    'temps_total': progression.temps_etudie_total
                })
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'], url_path='verifier-examen')
    def verifier_acces_examen(self, request):
        """Vérifie l'accès à un examen spécifique et marque comme consulté si autorisé"""
        try:
            from .services import PermissionService
            
            examen_id = request.data.get('examen_id')
            
            if not examen_id:
                return Response(
                    {'detail': 'examen_id requis'}, 
                    status=400
                )
            
            # Vérifier l'accès
            acces, message = PermissionService.verifier_acces_examen(
                request.user, examen_id
            )
            
            response_data = {
                'acces': acces,
                'message': message,
                'examen_id': examen_id,
                'deja_consulte': False
            }
            
            if acces:
                # Vérifier s'il était déjà consulté
                deja_consulte = PermissionService.examen_deja_consulte(
                    request.user, examen_id
                )
                response_data['deja_consulte'] = deja_consulte
                
                # Si pas déjà consulté, marquer comme consulté
                if not deja_consulte:
                    success, message_marquage = PermissionService.marquer_examen_consulte(
                        request.user, examen_id
                    )
                    response_data['marque_comme_consulte'] = success
                    response_data['message_marquage'] = message_marquage
                    
                    # Mettre à jour le compteur dans la réponse
                    nouveau_compteur = PermissionService.compter_examens_mois_courant(request.user)
                    response_data['examens_ce_mois'] = nouveau_compteur
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'], url_path='paiement-wave')
    def paiement_wave(self, request):
        """Initie un paiement Wave"""
        try:
            pack_id = request.data.get('pack_id')
            telephone = request.data.get('telephone')
            email = request.data.get('email', '')
            renouvellement_auto = request.data.get('renouvellement_auto', False)
            
            resultat = AbonnementService.initier_paiement_abonnement(
                request.user, pack_id, telephone, email, renouvellement_auto
            )
            
            if resultat['success']:
                return Response(resultat)
            else:
                return Response({'detail': resultat['error']}, status=400)
                
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'], url_path='essai-gratuit')
    def essai_gratuit(self, request):
        """Active un essai gratuit"""
        try:
            pack_id = request.data.get('pack_id')
            resultat = AbonnementService.creer_essai_gratuit(request.user, pack_id)
            
            if resultat['success']:
                return Response({'detail': 'Essai gratuit activé avec succès'})
            else:
                return Response({'detail': resultat['error']}, status=400)
                
        except Exception as e:
            return Response({'detail': str(e)}, status=500)


class WaveCallbackView(APIView):
    """Vue pour traiter les callbacks Wave (pas d'authentification requise)"""
    permission_classes = []
    
    def post(self, request):
        """Traite un callback Wave"""
        try:
            # Traiter le callback
            resultat = WaveService().traiter_callback(request.data)
            
            if resultat['success']:
                return Response({'status': 'success'})
            else:
                return Response({'status': 'error', 'message': resultat['error']})
                
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)})


class ParrainageViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer le système de parrainage"""
    serializer_class = ParrainageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Parrainage.objects.filter(parrain=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Récupère les statistiques de parrainage"""
        try:
            from .services import ParrainageService
            stats = ParrainageService.get_statistiques_parrainage(request.user)
            return Response(stats)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['get'])
    def code_parrainage(self, request):
        """Récupère le code de parrainage de l'utilisateur"""
        try:
            from .services import ParrainageService
            code = ParrainageService.get_code_parrainage(request.user)
            return Response(code)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['post'])
    def utiliser_bonus(self, request):
        """Utilise un bonus de parrainage"""
        try:
            nombre_semaines = request.data.get('nombre_semaines', 1)
            from .services import ParrainageService
            resultat = ParrainageService.utiliser_bonus_parrainage(
                request.user, nombre_semaines
            )
            return Response(resultat)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)
    
    @action(detail=False, methods=['get'])
    def filleuls(self, request):
        """Récupère la liste des filleuls de l'utilisateur"""
        try:
            from .services import ParrainageService
            filleuls = ParrainageService.get_filleuls(request.user)
            return Response(filleuls)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)


class BonusParrainageViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les bonus de parrainage"""
    serializer_class = BonusParrainageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BonusParrainage.objects.filter(utilisateur=self.request.user)


class PaiementWaveViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les paiements Wave"""
    serializer_class = PaiementWaveSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PaiementWave.objects.filter(abonnement__utilisateur=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initier_paiement_wave(request):
    """
    Initie un paiement Wave pour un abonnement
    """
    try:
        pack_id = request.data.get('pack_id')
        telephone = request.data.get('telephone', '')
        email = request.data.get('email', '')
        renouvellement_auto = request.data.get('renouvellement_auto', False)
        
        if not pack_id:
            return Response({
                'success': False,
                'error': 'Pack ID requis'
            }, status=400)
        
        # Utiliser le service d'abonnement pour initier le paiement
        resultat = AbonnementService.initier_paiement_abonnement(
            utilisateur=request.user,
            pack_id=pack_id,
            telephone=telephone,
            email=email,
            renouvellement_auto=renouvellement_auto
        )
        
        if resultat['success']:
            return Response(resultat)
        else:
            return Response(resultat, status=400)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packs_speciaux(request):
    """Récupère les packs spéciaux pour les paiements d'enfants - EXCLUT les packs familiaux"""
    try:
        packs = PackAbonnement.objects.filter(
            pack_special=True,
            actif=True
        ).exclude(
            nom="Pack de Bienvenue Parrainage"
        ).exclude(
            type_pack='famille'  # 🔧 EXCLUSION : Les packs familiaux ne doivent pas apparaître dans les paiements d'enfants individuels
        )
        serializer = PackAbonnementSerializer(packs, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packs_standards(request):
    """Récupère les packs standards pour les paiements d'enfants - EXCLUT les packs familiaux"""
    try:
        packs = PackAbonnement.objects.filter(
            pack_special=False,
            actif=True
        ).exclude(
            nom="Pack de Bienvenue Parrainage"
        ).exclude(
            type_pack='famille'  # 🔧 EXCLUSION : Les packs familiaux ne doivent pas apparaître dans les paiements d'enfants individuels
        )
        serializer = PackAbonnementSerializer(packs, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_packs(request):
    """Récupère tous les packs (standards + spéciaux) pour les paiements d'enfants - EXCLUT les packs familiaux"""
    try:
        packs = PackAbonnement.objects.filter(
            actif=True
        ).exclude(
            nom="Pack de Bienvenue Parrainage"
        ).exclude(
            type_pack='famille'  # 🔧 EXCLUSION : Les packs familiaux ne doivent pas apparaître dans les paiements d'enfants individuels
        )
        serializer = PackAbonnementSerializer(packs, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packs_familiaux(request):
    """Récupère UNIQUEMENT les packs familiaux pour les paiements familiaux"""
    try:
        packs = PackAbonnement.objects.filter(
            type_pack='famille',
            actif=True
        ).order_by('prix')
        
        # Formater les données comme attendu par le frontend
        packs_data = []
        for i, pack in enumerate(packs):
            # Calculer le prix réduit
            prix_original = float(pack.prix)
            prix_reduit = float(pack.prix_reduit) if pack.reduction_pourcentage > 0 else prix_original
            
            packs_data.append({
                'id': f'pack-famille-{pack.id}',
                'real_id': pack.id,  # ID réel de la base de données
                'nom': pack.nom,
                'prix': prix_original,  # Prix original (barré)
                'prix_reduit': prix_reduit,  # Prix avec réduction (affiché)
                'nombre_enfants': 2 + i,  # 2, 3, 4 enfants
                'type_pack': 'famille',
                'description': pack.description,
                'popular': i == 1,  # Le deuxième pack est populaire
                'actif': pack.actif,
                'duree_jours': pack.duree_jours,
                'periode': pack.periode,
                'reduction_pourcentage': pack.reduction_pourcentage,
                'economie': prix_original - prix_reduit  # Montant économisé
            })
        
        return Response(packs_data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initier_paiement_wave_enfant(request):
    """
    Initie un paiement Wave pour un abonnement enfant
    Le parent paie et l'enfant reçoit l'abonnement
    """
    try:
        pack_id = request.data.get('pack_id')
        enfant_id = request.data.get('enfant_id')
        email = request.data.get('email', '')
        renouvellement_auto = request.data.get('renouvellement_auto', False)
        
        if not pack_id or not enfant_id:
            return Response({
                'success': False,
                'error': 'Pack ID et Enfant ID requis'
            }, status=400)
        
        # Vérifier que l'enfant appartient au parent
        try:
            from utilisateurs.models import Utilisateur, LienParentEnfant
            enfant = Utilisateur.objects.get(id=enfant_id, role='eleve')
            
            # Vérifier le lien parent-enfant
            lien_existe = LienParentEnfant.objects.filter(
                parent=request.user,
                enfant=enfant,
                actif=True
            ).exists()
            
            if not lien_existe:
                return Response({
                    'success': False,
                    'error': 'Enfant non trouvé ou non autorisé'
                }, status=403)
                
        except Utilisateur.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Enfant non trouvé ou non autorisé'
            }, status=403)
        
        # Utiliser le service d'abonnement pour initier le paiement enfant
        resultat = AbonnementService.initier_paiement_abonnement_enfant(
            parent=request.user,
            enfant=enfant,
            pack_id=pack_id,
            email=email,
            renouvellement_auto=renouvellement_auto
        )
        
        if resultat['success']:
            return Response(resultat)
        else:
            return Response(resultat, status=400)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
def wave_callback(request):
    """
    Callback Wave pour confirmer les paiements
    Cette vue sera appelée par Wave quand un paiement est confirmé
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        # Récupérer les données du callback Wave
        data = json.loads(request.body)
        
        # Extraire les informations importantes
        transaction_id = data.get('transaction_id')
        montant_paye = data.get('amount')
        reference_wave = data.get('reference')
        statut = data.get('status')
        
        if statut != 'success':
            return JsonResponse({'error': 'Paiement non réussi'}, status=400)
        
        # Traiter le paiement réussi
        from .services import WaveCallbackService
        resultat = WaveCallbackService.traiter_paiement_reussi(
            transaction_id, montant_paye, reference_wave
        )
        
        if resultat['success']:
            return JsonResponse({
                'success': True,
                'message': 'Paiement confirmé et abonnement activé'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultat['error']
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initier_paiement_wave_famille(request):
    """Initie un paiement Wave pour un pack familial"""
    try:
        if request.user.role != 'parent':
            return JsonResponse({'error': 'Accès non autorisé'}, status=403)
        
        data = json.loads(request.body)
        pack_id = data.get('pack_id')
        email = data.get('email', '')
        renouvellement_auto = data.get('renouvellement_auto', False)
        
        if not pack_id:
            return JsonResponse({'error': 'ID du pack requis'}, status=400)
        
        # Vérifier que le pack existe et est un pack familial
        try:
            pack = PackAbonnement.objects.get(id=pack_id, actif=True)
        except PackAbonnement.DoesNotExist:
            return JsonResponse({'error': 'Pack non trouvé'}, status=404)
        
        # Vérifier que c'est bien un pack familial
        if pack.type_pack != 'famille':
            return JsonResponse({'error': 'Ce pack n\'est pas un pack familial'}, status=400)
        
        # Utiliser le service pour initier le paiement familial
        from .services import AbonnementService
        resultat = AbonnementService.initier_paiement_abonnement_famille(
            utilisateur=request.user,
            pack_id=pack_id,
            email=email,
            renouvellement_auto=renouvellement_auto
        )
        
        if resultat['success']:
            return JsonResponse({
                'success': True,
                'transaction_id': resultat['transaction_id'],
                'wave_url': resultat['wave_url'],
                'message': resultat['message'],
                'simulation': resultat.get('simulation', False),
                'pack_nom': resultat['pack_nom'],
                'montant': resultat['montant']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultat['error']
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)