# utilisateurs/views.py
"""
ViewSets pour la gestion des utilisateurs, authentification et fonctionnalités associées.
Organisé par sections : Authentification, Gestion des profils, Parents/Enfants, Partenaires, Statistiques.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
from django.db import models, transaction
from django.db.models import Avg, Sum, F
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
import logging

# Imports des modèles
from .models import Utilisateur, InscriptionEnAttente, Commission, RetraitCommission, LienParentEnfant
from academic_structure.models import NiveauScolaire
from progression.models import ProgressionChapitre, ProgressionMatiere
from cours.models import Chapitre
from quiz.models import Quiz, TentativeQuiz
from gamification.models import BadgeEtudiant

# Imports des serializers
from .serializers import (
    UtilisateurSerializer, InscriptionEnAttenteSerializer, NiveauScolaireSerializer,
    UtilisateurPartenaireSerializer, CommissionSerializer, RetraitCommissionSerializer, 
    DemandeRetraitSerializer, FilleulSerializer, ConfigurationSerializer
)
from cours.serializers import ChapitreSerializer
from quiz.serializers import QuizSerializer
from gamification.serializers import BadgeEtudiantSerializer

# Imports des services
from .services import generer_otp, envoyer_otp_email, envoyer_otp_reinitialisation

logger = logging.getLogger(__name__)


class UtilisateurViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des utilisateurs"""
    queryset = Utilisateur.objects.all()
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retourne les utilisateurs selon le rôle"""
        if self.request.user.role == 'parent':
            return Utilisateur.objects.filter(liens_enfant__parent=self.request.user).distinct()
        return Utilisateur.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def inscription(self, request):
        """Inscription d'un nouvel utilisateur (étape 1 - sans mot de passe)"""
        try:
            data = request.data.copy()
            
            # Vérifier que l'email n'existe pas déjà
            if Utilisateur.objects.filter(email=data.get('email')).exists():
                return Response(
                    {'email': ['Cette adresse email est déjà utilisée']}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Créer une inscription en attente
            inscription = InscriptionEnAttente.objects.create(
                email=data.get('email'),
                prenom=data.get('prenom'),
                nom=data.get('nom'),
                role=data.get('role'),
                niveau_id=data.get('niveau') if data.get('niveau') else None,
                code_parrain_utilise=data.get('code_parrain_utilise') if data.get('code_parrain_utilise') else None,
                otp=generer_otp(),
                otp_expires_at=timezone.now() + timedelta(minutes=15)
            )
            
            # Envoyer l'OTP par email
            envoyer_otp_email(inscription.email, inscription.otp)
            
            return Response({
                'message': 'Code OTP envoyé avec succès. Vérifiez votre email.',
                'inscription_id': inscription.id,
                'otp': inscription.otp  # Affichage de l'OTP pour debug
            }, status=status.HTTP_201_CREATED)
                    
        except Exception as e:
            logger.error(f"Erreur lors de l'inscription: {str(e)}")
            return Response(
                {'error': 'Erreur lors de l\'inscription'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verifier_otp(self, request):
        """Vérification de l'OTP d'inscription et création du compte final"""
        try:
            email = request.data.get('email')
            otp = request.data.get('otp')
            mot_de_passe = request.data.get('mot_de_passe')
            
            if not email or not otp or not mot_de_passe:
                return Response(
                    {'error': 'Email, OTP et mot de passe requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Vérifier l'OTP
            inscription = InscriptionEnAttente.objects.filter(
                email=email, 
                otp=otp,
                otp_expires_at__gt=timezone.now()
            ).first()
            
            if inscription:
                # Créer l'utilisateur final avec le mot de passe
                utilisateur = Utilisateur.objects.create_user(
                    email=inscription.email,
                    password=mot_de_passe,
                    first_name=inscription.prenom,
                    last_name=inscription.nom,
                    role=inscription.role,
                    niveau=inscription.niveau,
                    email_verifie=True,
                    is_active=True,
                    matricule=self.generer_matricule_unique()
                )
                
                # Gérer le code de parrainage si fourni
                if inscription.code_parrain_utilise:
                    # Trouver le parrain
                    parrain = Utilisateur.objects.filter(
                        code_parrainage=inscription.code_parrain_utilise
                    ).first()
                    
                    if parrain:
                        # Créer le lien de parrainage
                        LienParentEnfant.objects.create(
                            parent=parrain,
                            enfant=utilisateur,
                            statut='actif'
                        )
                
                # Supprimer l'inscription en attente
                inscription.delete()
                
                return Response({
                    'message': 'Inscription réussie ! Votre compte a été créé.',
                    'utilisateur': UtilisateurSerializer(utilisateur).data
                })
            else:
                return Response(
                    {'error': 'OTP invalide ou expiré'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification OTP: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la vérification'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def generer_matricule_unique(self):
        """Génère un matricule unique"""
        while True:
            matricule = f"APP{get_random_string(6, '0123456789')}"
            if not Utilisateur.objects.filter(matricule=matricule).exists():
                return matricule

    @action(detail=False, methods=['get'], url_path='mes-enfants')
    def mes_enfants(self, request):
        """Récupère les enfants d'un parent"""
        try:
            print("DEBUG: Début de mes_enfants")
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'parent':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            print("DEBUG: Authentification OK")
            enfants = Utilisateur.objects.filter(liens_enfant__parent=request.user).distinct()
            print(f"DEBUG: {enfants.count()} enfants trouvés")
            
            # Récupérer les vraies données des enfants depuis la base
            from progression.models import ProgressionChapitre, ProgressionMatiere
            from abonnements.models import Abonnement
            from academic_structure.models import NiveauScolaire
            
            enfants_data = []
            for enfant in enfants:
                # Récupérer les statistiques réelles
                chapitres_termines = ProgressionChapitre.objects.filter(etudiant=enfant, statut='termine').count()
                matieres_terminees = ProgressionMatiere.objects.filter(etudiant=enfant, statut='termine').count()
                
                # Calculer le temps d'étude total réel (en secondes)
                temps_total_secondes = ProgressionMatiere.objects.filter(etudiant=enfant).aggregate(
                    total=models.Sum('temps_etudie_total')
                )['total'] or 0
                
                # Calculer la moyenne des pourcentages de completion
                scores_chapitres = ProgressionChapitre.objects.filter(etudiant=enfant).aggregate(
                    avg=models.Avg('pourcentage_completion')
                )['avg'] or 0
                moyenne = scores_chapitres
                
                # Récupérer l'abonnement actuel
                abonnement_actuel = Abonnement.objects.filter(
                    utilisateur=enfant, 
                    actif=True
                ).first()
                
                # Récupérer le niveau scolaire de l'enfant
                # On va chercher le niveau le plus fréquent parmi les matières étudiées
                matieres_enfant = ProgressionMatiere.objects.filter(etudiant=enfant).select_related('matiere__niveau')
                if matieres_enfant.exists():
                    niveau = matieres_enfant.first().matiere.niveau
                else:
                    # Si pas de progression, essayer de trouver le niveau depuis les abonnements ou autres sources
                    niveau = None
                
                # Récupérer la dernière activité
                derniere_chapitre = ProgressionChapitre.objects.filter(etudiant=enfant).order_by('-date_completion', '-date_debut').first()
                
                derniere_activite = "Aucune activité"
                if derniere_chapitre:
                    derniere_activite = f"Chapitre: {derniere_chapitre.chapitre.titre if derniere_chapitre.chapitre else 'Chapitre terminé'}"
                
                # Déterminer la matière actuelle (en cours)
                matiere_actuelle = "Non définie"
                if niveau:
                    # Chercher une matière en cours
                    matiere_en_cours = ProgressionMatiere.objects.filter(
                        etudiant=enfant,
                        statut='en_cours'
                    ).select_related('matiere').first()
                    
                    if matiere_en_cours:
                        matiere_actuelle = matiere_en_cours.matiere.nom
                    else:
                        # Si aucune matière en cours, prendre la dernière matière avec progression
                        derniere_matiere = ProgressionMatiere.objects.filter(
                            etudiant=enfant
                        ).select_related('matiere').order_by('-date_completion', '-date_debut').first()
                        
                        if derniere_matiere:
                            matiere_actuelle = derniere_matiere.matiere.nom
                
                # Récupérer toutes les matières du niveau de l'enfant
                progression_matieres = {}
                
                if niveau:
                    # Récupérer toutes les matières du niveau scolaire
                    from academic_structure.models import Matiere
                    matieres_niveau = Matiere.objects.filter(niveau=niveau, active=True).order_by('ordre')
                    
                    # Récupérer les progressions existantes pour cet enfant
                    progressions_existantes = ProgressionMatiere.objects.filter(
                        etudiant=enfant
                    ).select_related('matiere')
                    
                    # Créer un dictionnaire des progressions existantes
                    progressions_dict = {}
                    for prog in progressions_existantes:
                        progressions_dict[prog.matiere.id] = {
                            'completed': round(prog.pourcentage_completion, 1),
                            'score': round(prog.pourcentage_completion, 1),
                            'statut': prog.statut,
                            'temps_etudie': prog.temps_etudie_total,
                            'chapitres_termines': prog.nombre_chapitres_termines,
                            'chapitres_total': prog.nombre_chapitres_total
                        }
                    
                    # Pour chaque matière du niveau, créer l'entrée de progression
                    for matiere in matieres_niveau:
                        matiere_key = matiere.slug or matiere.nom.lower().replace(' ', '_')
                        
                        if matiere.id in progressions_dict:
                            # Utiliser les données de progression existantes
                            progression_matieres[matiere_key] = {
                                'nom': matiere.nom,
                                'icone': matiere.icone,
                                'couleur': matiere.couleur,
                                'completed': progressions_dict[matiere.id]['completed'],
                                'score': progressions_dict[matiere.id]['score'],
                                'statut': progressions_dict[matiere.id]['statut'],
                                'temps_etudie': progressions_dict[matiere.id]['temps_etudie'],
                                'chapitres_termines': progressions_dict[matiere.id]['chapitres_termines'],
                                'chapitres_total': progressions_dict[matiere.id]['chapitres_total']
                            }
                        else:
                            # Aucune progression pour cette matière
                            progression_matieres[matiere_key] = {
                                'nom': matiere.nom,
                                'icone': matiere.icone,
                                'couleur': matiere.couleur,
                                'completed': 0,
                                'score': 0,
                                'statut': 'non_commence',
                                'temps_etudie': 0,
                                'chapitres_termines': 0,
                                'chapitres_total': 0
                            }
                else:
                    # Si pas de niveau défini, utiliser les matières par défaut
                    matieres_standard = ['mathematiques', 'francais', 'anglais', 'sciences']
                    for matiere in matieres_standard:
                        progression_matieres[matiere] = {
                            'nom': matiere.title(),
                            'icone': 'fas fa-book',
                            'couleur': '#007bff',
                            'completed': 0,
                            'score': 0,
                            'statut': 'non_commence',
                            'temps_etudie': 0,
                            'chapitres_termines': 0,
                            'chapitres_total': 0
                        }
                
                # Récupérer le statut du lien parent-enfant
                lien_parent_enfant = enfant.liens_enfant.filter(parent=request.user).first()
                statut_lien = lien_parent_enfant.actif if lien_parent_enfant else False
                
                enfants_data.append({
                    'id': enfant.id,
                    'first_name': enfant.first_name,
                    'last_name': enfant.last_name,
                    'email': enfant.email,
                    'matricule': enfant.matricule or f'APP{enfant.id:06d}',
                    'lien_actif': statut_lien,  # Statut du lien parent-enfant
                    'niveau': {
                        'nom': niveau.nom if niveau else 'Non défini',
                        'id': niveau.id if niveau else None,
                        'ordre': niveau.ordre if niveau else 0
                    },
                    'abonnement': {
                        'status': 'active' if abonnement_actuel else 'inactive',
                        'endDate': abonnement_actuel.date_fin.isoformat() if abonnement_actuel and abonnement_actuel.date_fin else None,
                        'plan': abonnement_actuel.pack.nom if abonnement_actuel and abonnement_actuel.pack else None
                    },
                    'statistiques': {
                        'coursesCompleted': chapitres_termines,
                        'totalCourses': 20,  # Approximation
                        'quizzesCompleted': matieres_terminees,
                        'examsCompleted': 0,  # À implémenter selon vos modèles d'examens
                        'studyTimeMinutes': temps_total_secondes,  # En secondes comme attendu par le frontend
                        'averageScore': round(moyenne, 1),
                        'overallProgress': min(100, round(sum([
                            matiere_data.get('completed', 0) for matiere_data in progression_matieres.values()
                        ]) / len(progression_matieres) if progression_matieres else 0, 1))
                    },
                    'progression_matieres': progression_matieres,
                    'derniere_activite': derniere_activite,
                    'matiere_actuelle': matiere_actuelle,
                    'planning': [],  # À implémenter selon votre système de planning
                })
            
            print(f"DEBUG: {len(enfants_data)} enfants traités avec succès")
            return Response({'enfants': enfants_data})
            
        except Exception as e:
            print(f"DEBUG: ERREUR dans mes_enfants: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': 'Erreur interne du serveur'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='parrainage')
    def parrainage(self, request):
        """Récupère les informations de parrainage"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Permettre aux parents et partenaires d'accéder au parrainage
        if request.user.role not in ['parent', 'partenaire']:
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer les vraies données de parrainage depuis la base
        from django.db.models import Count, Sum
        
        # Compter les parrainages réussis
        parrainages_reussis = Utilisateur.objects.filter(
            code_parrain_utilise=request.user.code_parrainage
        ).count()
        
        # Calculer les bonus (logique métier)
        bonus_accumules = parrainages_reussis * 100  # 100 points par parrainage
        bonus_utilises = 0  # À implémenter selon votre logique
        bonus_disponibles = bonus_accumules - bonus_utilises
        
        return Response({
            'code_parrainage': request.user.code_parrainage or f'PARENT{request.user.id}',
            'bonus_disponibles': bonus_disponibles,
            'total_parrainages': parrainages_reussis,
            'bonus_accumules': bonus_accumules,
            'bonus_utilises': bonus_utilises,
            'parrainages_reussis': parrainages_reussis,
            'peut_utiliser_bonus': bonus_disponibles > 0
        })

    @action(detail=False, methods=['get'], url_path='activite-enfants')
    def activite_enfants(self, request):
        """Récupère l'activité des enfants"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        if request.user.role != 'parent':
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer les vraies activités des enfants depuis la base
        enfants = Utilisateur.objects.filter(liens_enfant__parent=request.user).distinct()
        
        # Récupérer les activités récentes depuis les modèles de progression
        from progression.models import ProgressionChapitre, ProgressionMatiere
        from cours.models import Chapitre
        from academic_structure.models import Matiere
        
        activites = []
        
        for enfant in enfants:
            # Activités de chapitres
            progressions_chapitres = ProgressionChapitre.objects.filter(
                etudiant=enfant
            ).select_related('chapitre').order_by('-date_completion', '-date_debut')[:5]
            
            for prog in progressions_chapitres:
                chapitre_titre = prog.chapitre.titre if prog.chapitre else 'Chapitre terminé'
                matiere_nom = prog.chapitre.matiere.nom if prog.chapitre and prog.chapitre.matiere else 'Matière inconnue'
                
                # Vérifier que le chapitre et la matière existent et sont actifs
                if not prog.chapitre or not prog.chapitre.actif:
                    continue
                    
                if not prog.chapitre.matiere or not prog.chapitre.matiere.active:
                    continue
                
                # Vérifier que l'activité a un temps d'étude significatif (> 0)
                temps_etude_minutes = prog.temps_etudie // 60 if prog.temps_etudie else 0
                if temps_etude_minutes == 0:
                    continue
                
                activites.append({
                    'id': f"chapitre_{prog.id}",
                    'enfant_nom': f"{enfant.first_name or 'Enfant'} {enfant.last_name or ''}".strip(),
                    'action': 'a terminé le chapitre',
                    'sujet': chapitre_titre,
                    'temps_affiche': f"{temps_etude_minutes} min",
                    'color': 'primary',
                    'icon': 'book',
                    'date': (prog.date_completion or prog.date_debut).isoformat(),
                    'score': round(prog.pourcentage_completion, 1),
                    'statut': prog.statut
                })
            
            # Activités de matières
            progressions_matieres = ProgressionMatiere.objects.filter(
                etudiant=enfant
            ).select_related('matiere').order_by('-date_completion', '-date_debut')[:3]
            
            for prog in progressions_matieres:
                matiere_nom = prog.matiere.nom if prog.matiere else 'Matière'
                
                # Vérifier que la matière existe et est active
                if not prog.matiere or not prog.matiere.active:
                    continue
                
                # Vérifier que l'activité a un temps d'étude significatif (> 0)
                temps_etude_minutes = prog.temps_etudie_total // 60 if prog.temps_etudie_total else 0
                if temps_etude_minutes == 0:
                    continue
                
                activites.append({
                    'id': f"matiere_{prog.id}",
                    'enfant_nom': f"{enfant.first_name or 'Enfant'} {enfant.last_name or ''}".strip(),
                    'action': 'a progressé en',
                    'sujet': matiere_nom,
                    'temps_affiche': f"{temps_etude_minutes} min",
                    'color': 'success',
                    'icon': 'graduation-cap',
                    'date': (prog.date_completion or prog.date_debut).isoformat(),
                    'score': round(prog.pourcentage_completion, 1),
                    'statut': prog.statut
                })
        
        # Trier par date décroissante
        activites.sort(key=lambda x: x['date'], reverse=True)
        
        return Response({
            'enfants_actifs': [{'id': e.id, 'nom': f"{e.first_name or 'Enfant'} {e.last_name or ''}".strip()} for e in enfants],
            'activites': activites[:10]  # Limiter à 10 activités récentes
        })

    @action(detail=False, methods=['get'], url_path='enfant-details/(?P<enfant_id>[^/.]+)')
    def enfant_details(self, request, enfant_id=None):
        """Récupère les détails d'un enfant spécifique"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        if request.user.role != 'parent':
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Vérifier que l'enfant appartient au parent
            enfant = Utilisateur.objects.get(
                id=enfant_id,
                liens_enfant__parent=request.user
            )
            
            # Récupérer les détails de l'enfant
            from progression.models import ProgressionChapitre, ProgressionMatiere
            from academic_structure.models import NiveauScolaire, Matiere
            from abonnements.models import Abonnement
            
            # Récupérer l'abonnement actuel de l'enfant
            abonnement_actuel = Abonnement.objects.filter(
                utilisateur=enfant,
                statut='actif'
            ).select_related('pack').first()
            
            # Statistiques de base
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=enfant, statut='termine'
            ).count()
            
            matieres_terminees = ProgressionMatiere.objects.filter(
                etudiant=enfant, statut='termine'
            ).count()
            
            temps_total = ProgressionMatiere.objects.filter(
                etudiant=enfant
            ).aggregate(total=models.Sum('temps_etudie_total'))['total'] or 0
            
            # Progression par matière
            progression_matieres = {}
            niveau = None
            
            # Récupérer le niveau de l'enfant
            matieres_niveau = Matiere.objects.filter(
                progressionmatiere__etudiant=enfant
            ).select_related('niveau').first()
            
            if matieres_niveau:
                niveau = matieres_niveau.niveau
                matieres = Matiere.objects.filter(niveau=niveau, active=True)
                
                for matiere in matieres:
                    prog = ProgressionMatiere.objects.filter(
                        etudiant=enfant, matiere=matiere
                    ).first()
                    
                    progression_matieres[matiere.slug or matiere.nom.lower()] = {
                        'nom': matiere.nom,
                        'completed': round(prog.pourcentage_completion, 1) if prog else 0,
                        'score': round(prog.pourcentage_completion, 1) if prog else 0,
                        'statut': prog.statut if prog else 'non_commence',
                        'temps_etudie': prog.temps_etudie_total if prog else 0,
                        'chapitres_termines': prog.nombre_chapitres_termines if prog else 0,
                        'chapitres_total': prog.nombre_chapitres_total if prog else 0
                    }
            
            return Response({
                'enfant': {
                    'id': enfant.id,
                    'first_name': enfant.first_name or 'Enfant',
                    'last_name': enfant.last_name or '',
                    'nom': f"{enfant.first_name or ''} {enfant.last_name or ''}".strip(),
                    'email': enfant.email,
                    'matricule': enfant.matricule or f'APP{enfant.id:06d}',
                    'niveau': {
                        'nom': niveau.nom if niveau else 'Non défini',
                        'id': niveau.id if niveau else None
                    },
                    'abonnement': {
                        'status': 'actif' if abonnement_actuel else 'inactif',
                        'nom': abonnement_actuel.pack.nom if abonnement_actuel and abonnement_actuel.pack else None,
                        'date_debut': abonnement_actuel.date_debut.isoformat() if abonnement_actuel else None,
                        'date_fin': abonnement_actuel.date_fin.isoformat() if abonnement_actuel else None,
                        'prix': abonnement_actuel.pack.prix if abonnement_actuel and abonnement_actuel.pack else None,
                        'devise': getattr(abonnement_actuel.pack, 'devise', 'FCFA') if abonnement_actuel and abonnement_actuel.pack else 'FCFA'
                    },
                    'statistiques': {
                        'coursesCompleted': chapitres_termines,
                        'quizzesCompleted': matieres_terminees,
                        'studyTimeMinutes': temps_total,
                        'overallProgress': round(sum([
                            matiere.get('completed', 0) for matiere in progression_matieres.values()
                        ]) / len(progression_matieres) if progression_matieres else 0, 1)
                    },
                    'progression_matieres': progression_matieres
                }
            })
            
        except Utilisateur.DoesNotExist:
            return Response({'error': 'Enfant non trouvé'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='packs-speciaux')
    def packs_speciaux(self, request):
        """Récupère les packs individuels disponibles pour le renouvellement"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            from abonnements.models import PackAbonnement
            
            # Récupérer tous les packs individuels (non spéciaux familiaux)
            packs_queryset = PackAbonnement.objects.filter(
                actif=True
            ).exclude(
                nom__in=[
                    "Pack de Bienvenue Parrainage",
                    "Pack Découverte",
                    "Pack Famille 3 Enfants",
                    "Pack Famille 5+ Enfants"
                ]
            ).exclude(
                description__icontains="Pack gratuit d'une semaine offert grâce au parrainage"
            ).exclude(
                description__icontains="Pack de découverte gratuit"
            ).exclude(
                description__icontains="famille"
            )
            
            # Convertir en format API
            packs_data = []
            for pack in packs_queryset:
                packs_data.append({
                    'id': pack.id,
                    'nom': pack.nom,
                    'prix': float(pack.prix),
                    'prix_reduit': float(pack.prix_reduit) if pack.prix_reduit else float(pack.prix),
                    'devise': 'FCFA',
                    'type_pack': 'standard',
                    'description': pack.description or f"Pack {pack.nom}",
                    'duree_jours': pack.duree_jours or 30,
                    'periode': pack.periode or 'mois',
                    'reduction_pourcentage': 0,
                    'offre_semaine_gratuite': False,
                    'conditions_speciales': None
                })
            
            # Si aucun pack trouvé, retourner des packs par défaut
            if not packs_data:
                packs_data = [
                    {
                        'id': 'pack-gratuit',
                        'nom': 'Gratuit',
                        'prix': 0,
                        'prix_reduit': 0,
                        'devise': 'FCFA',
                        'type_pack': 'standard',
                        'description': 'Accès limité aux fonctionnalités de base',
                        'duree_jours': 30,
                        'periode': 'mois',
                        'reduction_pourcentage': 0,
                        'offre_semaine_gratuite': False,
                        'conditions_speciales': None
                    },
                    {
                        'id': 'pack-standard',
                        'nom': 'Standard',
                        'prix': 500,
                        'prix_reduit': 500,
                        'devise': 'FCFA',
                        'type_pack': 'standard',
                        'description': 'Pack standard avec accès aux cours et quiz',
                        'duree_jours': 7,
                        'periode': 'semaine',
                        'reduction_pourcentage': 0,
                        'offre_semaine_gratuite': False,
                        'conditions_speciales': None
                    },
                    {
                        'id': 'pack-premium',
                        'nom': 'Premium',
                        'prix': 1500,
                        'prix_reduit': 1500,
                        'devise': 'FCFA',
                        'type_pack': 'standard',
                        'description': 'Pack premium avec toutes les fonctionnalités',
                        'duree_jours': 30,
                        'periode': 'mois',
                        'reduction_pourcentage': 0,
                        'offre_semaine_gratuite': False,
                        'conditions_speciales': None
                    }
                ]
            
            return Response({'packs': packs_data})
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des packs: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération des packs'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='demandes-en-attente')
    def demandes_en_attente(self, request):
        """Récupère les demandes en attente"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        if request.user.role != 'parent':
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer les vraies demandes en attente depuis la base
        from .models import InscriptionEnAttente
        
        # Filtrer par code de parrainage du parent
        demandes = InscriptionEnAttente.objects.filter(
            code_parrain_utilise=request.user.code_parrainage
        ).order_by('-date_creation')
        
        demandes_data = []
        for demande in demandes:
            demandes_data.append({
                'id': demande.id,
                'enfant_nom': f"{demande.prenom} {demande.nom}",
                'email': demande.email,
                'date_demande': demande.date_creation.isoformat(),
                'statut': 'en_attente',
                'message': 'Demande d\'ajout d\'enfant en attente de validation'
            })
        
        return Response({
            'demandes_en_attente': demandes_data
        })

    

    # ===============================
    # GESTION DU PROFIL UTILISATEUR
    # ===============================
    
    @action(detail=False, methods=['get'], url_path='moi')
    def moi(self, request):
        """Récupère les informations de l'utilisateur connecté"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = UtilisateurSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def profil(self, request):
        """Récupère le profil complet de l'utilisateur connecté"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Récupérer les statistiques de l'utilisateur
        from progression.models import ProgressionChapitre, ProgressionMatiere
        
        chapitres_termines = ProgressionChapitre.objects.filter(
            etudiant=request.user, statut='termine'
        ).count()
        
        temps_etude_total = ProgressionMatiere.objects.filter(
            etudiant=request.user
        ).aggregate(total=models.Sum('temps_etudie_total'))['total'] or 0
        
        profil_data = UtilisateurSerializer(request.user).data
        profil_data.update({
            'statistiques': {
                'chapitres_termines': chapitres_termines,
                'temps_etude_minutes': temps_etude_total,
                'derniere_activite': request.user.derniere_activite
            }
        })
        
        return Response(profil_data)

    # ===============================
    # GESTION DES MOTS DE PASSE
    # ===============================
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def demander_reinitialisation(self, request):
        """Demande de réinitialisation de mot de passe"""
        try:
            email = request.data.get('email')
            if not email:
                return Response(
                    {'error': 'Email requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                utilisateur = Utilisateur.objects.get(email=email)
                otp = generer_otp()
                envoyer_otp_reinitialisation(email, otp)
                
                # Sauvegarder l'OTP temporairement
                utilisateur.otp_reinitialisation = otp
                utilisateur.otp_expires_at = timezone.now() + timedelta(minutes=15)
                utilisateur.save()
                
                return Response({'message': 'Code de réinitialisation envoyé par email'})
            except Utilisateur.DoesNotExist:
                return Response(
                    {'error': 'Aucun compte trouvé avec cet email'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la demande de réinitialisation: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la demande de réinitialisation'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verifier_otp_reinitialisation(self, request):
        """Vérification de l'OTP de réinitialisation"""
        try:
            email = request.data.get('email')
            otp = request.data.get('otp')
            
            if not email or not otp:
                return Response(
                    {'error': 'Email et OTP requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                utilisateur = Utilisateur.objects.get(email=email)
                if (utilisateur.otp_reinitialisation == otp and 
                    utilisateur.otp_expires_at and 
                    utilisateur.otp_expires_at > timezone.now()):
                    return Response({'message': 'OTP valide'})
                else:
                    return Response(
                        {'error': 'OTP invalide ou expiré'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Utilisateur.DoesNotExist:
                return Response(
                    {'error': 'Utilisateur non trouvé'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification OTP: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la vérification'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def changer_mot_de_passe(self, request):
        """Changement de mot de passe avec OTP"""
        try:
            email = request.data.get('email')
            otp = request.data.get('otp')
            nouveau_mot_de_passe = request.data.get('nouveau_mot_de_passe')
            
            if not all([email, otp, nouveau_mot_de_passe]):
                return Response(
                    {'error': 'Email, OTP et nouveau mot de passe requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                utilisateur = Utilisateur.objects.get(email=email)
                if (utilisateur.otp_reinitialisation == otp and 
                    utilisateur.otp_expires_at and 
                    utilisateur.otp_expires_at > timezone.now()):
                    
                    utilisateur.set_password(nouveau_mot_de_passe)
                    utilisateur.otp_reinitialisation = None
                    utilisateur.otp_expires_at = None
                    utilisateur.save()
                    
                    return Response({'message': 'Mot de passe modifié avec succès'})
                else:
                    return Response(
                        {'error': 'OTP invalide ou expiré'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Utilisateur.DoesNotExist:
                return Response(
                    {'error': 'Utilisateur non trouvé'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Erreur lors du changement de mot de passe: {str(e)}")
            return Response(
                {'error': 'Erreur lors du changement de mot de passe'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def changer_mot_de_passe_connecte(self, request):
        """Changement de mot de passe pour utilisateur connecté"""
        try:
            logger.info(f"Données reçues pour changement de mot de passe: {request.data}")
            ancien_mot_de_passe = request.data.get('ancien_mot_de_passe')
            nouveau_mot_de_passe = request.data.get('nouveau_mot_de_passe')
            
            if not ancien_mot_de_passe:
                return Response(
                    {'error': 'Ancien mot de passe requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not nouveau_mot_de_passe:
                return Response(
                    {'error': 'Nouveau mot de passe requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(nouveau_mot_de_passe) < 8:
                return Response(
                    {'error': 'Le nouveau mot de passe doit contenir au moins 8 caractères'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not request.user.check_password(ancien_mot_de_passe):
                return Response(
                    {'error': 'Ancien mot de passe incorrect'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            request.user.set_password(nouveau_mot_de_passe)
            request.user.save()
            
            return Response({'message': 'Mot de passe modifié avec succès'})
            
        except Exception as e:
            logger.error(f"Erreur lors du changement de mot de passe: {str(e)}")
            return Response(
                {'error': 'Erreur lors du changement de mot de passe'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def connexion(self, request):
        """Connexion d'un utilisateur"""
        try:
            email = request.data.get('email')
            mot_de_passe = request.data.get('mot_de_passe')
            
            if not email or not mot_de_passe:
                return Response(
                    {'error': 'Email et mot de passe requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Authentifier l'utilisateur
            utilisateur = authenticate(email=email, password=mot_de_passe)
            
            if utilisateur and utilisateur.is_active:
                # Créer ou récupérer un token
                from rest_framework.authtoken.models import Token
                token, created = Token.objects.get_or_create(user=utilisateur)
                
                return Response({
                    'token': token.key,
                    'utilisateur': UtilisateurSerializer(utilisateur).data
                })
            else:
                return Response(
                    {'error': 'Identifiants invalides'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la connexion'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def deconnexion(self, request):
        """Déconnexion d'un utilisateur"""
        try:
            # Supprimer le token
            request.user.auth_token.delete()
            return Response({'message': 'Déconnexion réussie'})
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la déconnexion'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='statistiques-globales', permission_classes=[AllowAny])
    def statistiques_globales(self, request):
        """Récupérer les statistiques globales de la plateforme"""
        try:
            # Statistiques des matières
            from academic_structure.models import Matiere
            total_matieres = Matiere.objects.filter(active=True).count()
            
            # Statistiques des chapitres
            from cours.models import Chapitre
            total_chapitres = Chapitre.objects.filter(actif=True).count()
            
            # Statistiques des quiz
            from quiz.models import Quiz
            total_quiz = Quiz.objects.filter(actif=True).count()
            
            # Statistiques des utilisateurs
            total_utilisateurs = Utilisateur.objects.filter(is_active=True).count()
            
            return Response({
                'total_matieres': total_matieres,
                'total_chapitres': total_chapitres,
                'total_quiz': total_quiz,
                'total_utilisateurs': total_utilisateurs
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques globales: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération des statistiques'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def verifier_matricule(self, request):
        """Vérifier l'unicité d'un matricule"""
        logger.info(f"Vérification du matricule appelée: {request.data}")
        try:
            matricule = request.data.get('matricule', '').strip()
            user_id = request.data.get('user_id')
            
            if not matricule:
                return Response(
                    {'error': 'Matricule requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Vérifier si le matricule existe déjà
            existing_user = Utilisateur.objects.filter(matricule=matricule).first()
            
            if existing_user:
                # Si c'est le même utilisateur, c'est OK
                if user_id and existing_user.id == int(user_id):
                    return Response({
                        'unique': True,
                        'exists': True,
                        'message': 'Matricule valide'
                    })
                else:
                    # Le matricule existe pour un autre utilisateur
                    return Response({
                        'unique': False,
                        'exists': True,
                        'message': 'Ce matricule existe déjà'
                    })
            else:
                # Le matricule n'existe pas dans la base de données
                return Response({
                    'unique': True,
                    'exists': False,
                    'message': 'Matricule disponible'
                })
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du matricule: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la vérification du matricule'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsAuthenticated])
    def preferences(self, request):
        """Récupérer ou mettre à jour les préférences utilisateur"""
        try:
            from .models import PreferencesUtilisateur
            
            if request.method == 'GET':
                # Récupérer ou créer les préférences
                try:
                    preferences, created = PreferencesUtilisateur.objects.get_or_create(
                        utilisateur=request.user,
                        defaults={
                            'notifications_email': True,
                            'rappels_etude': True,
                            'partage_progres': False,
                            'profil_public': False,
                            'langue': 'fr',
                            'pays': 'Côte d\'Ivoire'
                        }
                    )
                    
                    return Response({
                        'notifications_email': preferences.notifications_email,
                        'rappels_etude': preferences.rappels_etude,
                        'partage_progres': preferences.partage_progres,
                        'profil_public': preferences.profil_public,
                        'langue': preferences.langue,
                        'pays': preferences.pays,
                        'temps_session_etude': preferences.temps_session_etude,
                        'pause_session': preferences.pause_session,
                        'notification_quiz': preferences.notification_quiz,
                        'notification_examen': preferences.notification_examen,
                        'notification_badge': preferences.notification_badge
                    })
                except Exception as e:
                    # Si la table n'existe pas, retourner des préférences par défaut
                    logger.warning(f"Table PreferencesUtilisateur n'existe pas encore: {str(e)}")
                    return Response({
                        'notifications_email': True,
                        'rappels_etude': True,
                        'partage_progres': False,
                        'profil_public': False,
                        'langue': 'fr',
                        'pays': 'Côte d\'Ivoire',
                        'temps_session_etude': 45,
                        'pause_session': 15,
                        'notification_quiz': True,
                        'notification_examen': True,
                        'notification_badge': True
                    })
            
            elif request.method == 'PATCH':
                # Récupérer ou créer les préférences
                try:
                    preferences, created = PreferencesUtilisateur.objects.get_or_create(
                        utilisateur=request.user,
                        defaults={
                            'notifications_email': True,
                            'rappels_etude': True,
                            'partage_progres': False,
                            'profil_public': False,
                            'langue': 'fr',
                            'pays': 'Côte d\'Ivoire'
                        }
                    )
                    
                    # Mettre à jour les champs
                    allowed_fields = [
                        'notifications_email', 'rappels_etude', 'partage_progres', 
                        'profil_public', 'langue', 'pays', 'temps_session_etude', 
                        'pause_session', 'notification_quiz', 'notification_examen', 
                        'notification_badge'
                    ]
                    
                    for field in allowed_fields:
                        if field in request.data:
                            setattr(preferences, field, request.data[field])
                    
                    preferences.save()
                    
                    # Retourner les préférences mises à jour
                    return Response({
                        'notifications_email': preferences.notifications_email,
                        'rappels_etude': preferences.rappels_etude,
                        'partage_progres': preferences.partage_progres,
                        'profil_public': preferences.profil_public,
                        'langue': preferences.langue,
                        'pays': preferences.pays,
                        'temps_session_etude': preferences.temps_session_etude,
                        'pause_session': preferences.pause_session,
                        'notification_quiz': preferences.notification_quiz,
                        'notification_examen': preferences.notification_examen,
                        'notification_badge': preferences.notification_badge
                    })
                except Exception as e:
                    # Si la table n'existe pas, retourner les préférences par défaut
                    logger.warning(f"Table PreferencesUtilisateur n'existe pas encore: {str(e)}")
                    return Response({
                        'notifications_email': True,
                        'rappels_etude': True,
                        'partage_progres': False,
                        'profil_public': False,
                        'langue': 'fr',
                        'pays': 'Côte d\'Ivoire',
                        'temps_session_etude': 45,
                        'pause_session': 15,
                        'notification_quiz': True,
                        'notification_examen': True,
                        'notification_badge': True
                    })
                
        except Exception as e:
            logger.error(f"Erreur lors de la gestion des préférences: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la gestion des préférences'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def profil_public(self, request):
        """Récupérer le profil public de l'utilisateur"""
        try:
            user = request.user
            
            # Récupérer les statistiques
            from progression.models import ProgressionChapitre, ProgressionMatiere
            from gamification.models import BadgeEtudiant
            
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=user, statut='termine'
            ).count()
            
            badges_obtenus = BadgeEtudiant.objects.filter(
                etudiant=user
            ).count()
            
            # Récupérer les badges récents
            badges_recent = BadgeEtudiant.objects.filter(
                etudiant=user
            ).select_related('badge').order_by('-date_obtention')[:5]
            
            badges_data = []
            for badge_etudiant in badges_recent:
                badges_data.append({
                    'nom': badge_etudiant.badge.nom,
                    'description': badge_etudiant.badge.description,
                    'icone': badge_etudiant.badge.icone,
                    'date_obtention': badge_etudiant.date_obtention
                })
            
            return Response({
                'id': user.id,
                'nom': f"{user.first_name} {user.last_name}",
                'first_name': user.first_name,
                'last_name': user.last_name,
                'avatar_choisi': user.avatar_choisi,
                'niveau': user.niveau.nom if user.niveau else None,
                'date_inscription': user.date_inscription,
                'statistiques': {
                    'chapitres_termines': chapitres_termines,
                    'badges_obtenus': badges_obtenus,
                    'quiz_reussis': 0  # Valeur par défaut
                },
                'badges': badges_data
            })
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du profil public: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération du profil public'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def partage_progres(self, request):
        """Récupérer les paramètres de partage de progrès"""
        try:
            user = request.user
            
            # Récupérer les statistiques
            from progression.models import ProgressionChapitre, ProgressionMatiere
            from gamification.models import BadgeEtudiant
            
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=user, statut='termine'
            ).count()
            
            chapitres_commences = ProgressionChapitre.objects.filter(
                etudiant=user, statut='en_cours'
            ).count()
            
            # Calculer la progression moyenne
            total_chapitres = ProgressionChapitre.objects.filter(etudiant=user).count()
            progression_moyenne = (chapitres_termines / total_chapitres * 100) if total_chapitres > 0 else 0
            
            # Récupérer les progrès détaillés par matière
            progres_detailles = []
            matieres = ProgressionMatiere.objects.filter(etudiant=user).select_related('matiere')
            for progres in matieres:
                progres_detailles.append({
                    'matiere': progres.matiere.nom,
                    'progression': progres.progression,
                    'chapitres_termines': ProgressionChapitre.objects.filter(
                        etudiant=user, 
                        chapitre__matiere=progres.matiere,
                        statut='termine'
                    ).count()
                })
            
            return Response({
                'partage_progres': True,  # Valeur par défaut
                'statistiques_globales': {
                    'chapitres_termines': chapitres_termines,
                    'chapitres_commences': chapitres_commences,
                    'progression_moyenne': progression_moyenne,
                    'total_chapitres': total_chapitres
                },
                'progres_detailles': progres_detailles
            })
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du partage de progrès: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération du partage de progrès'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def utilisateurs_publics(self, request):
        """Récupérer la liste des utilisateurs avec profil public"""
        try:
            from .models import PreferencesUtilisateur
            
            # Récupérer les utilisateurs qui ont activé leur profil public
            users_with_public_profile = PreferencesUtilisateur.objects.filter(
                profil_public=True
            ).select_related('utilisateur', 'utilisateur__niveau')
            
            utilisateurs_data = []
            for prefs in users_with_public_profile:
                user = prefs.utilisateur
                
                # Récupérer les statistiques de l'utilisateur
                from progression.models import ProgressionChapitre
                from gamification.models import BadgeEtudiant
                
                chapitres_termines = ProgressionChapitre.objects.filter(
                    etudiant=user, statut='termine'
                ).count()
                
                badges_obtenus = BadgeEtudiant.objects.filter(
                    etudiant=user
                ).count()
                
                utilisateurs_data.append({
                    'id': user.id,
                    'nom': f"{user.first_name} {user.last_name}",
                    'avatar_choisi': user.avatar_choisi,
                    'niveau': user.niveau.nom if user.niveau else None,
                    'date_inscription': user.date_inscription,
                    'statistiques': {
                        'chapitres_termines': chapitres_termines,
                        'badges_obtenus': badges_obtenus
                    }
                })
            
            return Response(utilisateurs_data)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des utilisateurs publics: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération des utilisateurs publics'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def demandes_parente(self, request):
        """Récupérer les demandes de parenté"""
        try:
            from .models import DemandeParente
            demandes = DemandeParente.objects.filter(
                parent=request.user
            ).select_related('enfant')
            
            demandes_data = []
            for demande in demandes:
                demandes_data.append({
                    'id': demande.id,
                    'enfant': {
                        'id': demande.enfant.id,
                        'first_name': demande.enfant.first_name,
                        'last_name': demande.enfant.last_name,
                        'email': demande.enfant.email
                    },
                    'statut': demande.statut,
                    'date_demande': demande.date_demande
                })
            
            return Response(demandes_data)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des demandes de parenté: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération des demandes de parenté'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def repondre_demande_parente(self, request):
        """Répondre à une demande de parenté"""
        try:
            from .models import DemandeParente, LienParentEnfant
            demande_id = request.data.get('demande_id')
            action = request.data.get('action')  # 'accepter' ou 'refuser'
            
            if not demande_id or not action:
                return Response(
                    {'error': 'ID de demande et action requis'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                demande = DemandeParente.objects.get(id=demande_id, parent=request.user)
            except DemandeParente.DoesNotExist:
                return Response(
                    {'error': 'Demande non trouvée'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if action == 'accepter':
                # Créer le lien parent-enfant
                LienParentEnfant.objects.create(
                    parent=request.user,
                    enfant=demande.enfant
                )
                demande.statut = 'acceptee'
                demande.save()
                return Response({'message': 'Demande acceptée'})
            elif action == 'refuser':
                demande.statut = 'refusee'
                demande.save()
                return Response({'message': 'Demande refusée'})
            else:
                return Response(
                    {'error': 'Action invalide'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la réponse à la demande de parenté: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la réponse à la demande de parenté'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'], permission_classes=[IsAuthenticated])
    def supprimer_compte(self, request):
        """Supprimer le compte utilisateur"""
        try:
            user = request.user
            # Désactiver l'utilisateur au lieu de le supprimer
            user.is_active = False
            user.save()
            
            # Supprimer le token d'authentification
            if hasattr(user, 'auth_token'):
                user.auth_token.delete()
            
            return Response({'message': 'Compte supprimé avec succès'})
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du compte: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la suppression du compte'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='dashboard-parent')
    def dashboard_parent(self, request):
        """Récupère les statistiques du tableau de bord pour les parents"""
        if not request.user.is_authenticated:
            return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
        if request.user.role != 'parent':
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Récupérer les enfants liés
            enfants = Utilisateur.objects.filter(liens_enfant__parent=request.user).distinct()
            enfants_count = enfants.count()
            
            # Calculer les abonnements actifs et les dépenses totales
            from abonnements.models import Abonnement
            abonnements_actifs = 0
            depenses_totales = 0
            
            for enfant in enfants:
                # Vérifier si l'enfant a un abonnement actif
                abonnement = Abonnement.objects.filter(
                    utilisateur=enfant,
                    statut='actif'
                ).select_related('pack').first()
                
                if abonnement:
                    abonnements_actifs += 1
                    # Ajouter le prix de l'abonnement aux dépenses totales
                    if abonnement.montant_paye:
                        depenses_totales += float(abonnement.montant_paye)
            
            # Calculer d'autres statistiques utiles
            from progression.models import ProgressionChapitre
            from datetime import datetime, timedelta
            
            # Activité cette semaine
            une_semaine = datetime.now() - timedelta(days=7)
            activite_semaine = ProgressionChapitre.objects.filter(
                etudiant__in=enfants,
                date_debut__gte=une_semaine
            ).count()
            
            return Response({
                'enfants_count': enfants_count,
                'abonnements_actifs': abonnements_actifs,
                'depenses_totales': depenses_totales,
                'activite_semaine': activite_semaine,
                'derniere_mise_a_jour': timezone.now()
            })
            
        except Exception as e:
            logger.error(f"ERREUR dashboard_parent: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': 'Erreur interne du serveur'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='verifier-enfant')
    def verifier_enfant(self, request):
        """Vérifie si un enfant existe par email ou matricule"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'parent':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data
            email = data.get('email')
            matricule = data.get('matricule')
            
            if not email and not matricule:
                return Response({
                    'valid': False,
                    'message': 'Email ou matricule requis'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Chercher l'enfant par email ou matricule
            enfant = None
            if email:
                try:
                    enfant = Utilisateur.objects.get(email=email, role='eleve')
                except Utilisateur.DoesNotExist:
                    pass
            
            if not enfant and matricule:
                try:
                    enfant = Utilisateur.objects.get(matricule=matricule, role='eleve')
                except Utilisateur.DoesNotExist:
                    pass
            
            if not enfant:
                return Response({
                    'valid': False,
                    'message': 'Aucun élève trouvé avec ces informations'
                })
            
            # Vérifier si l'enfant n'est pas déjà lié à un parent
            if hasattr(enfant, 'liens_enfant') and enfant.liens_enfant.filter(actif=True).exists():
                return Response({
                    'valid': False,
                    'message': 'Cet élève est déjà lié à un parent'
                })
            
            return Response({
                'valid': True,
                'message': f'Élève trouvé : {enfant.first_name or ""} {enfant.last_name or ""}'.strip(),
                'enfant': {
                    'id': enfant.id,
                    'email': enfant.email,
                    'matricule': enfant.matricule,
                    'nom': f"{enfant.first_name or ''} {enfant.last_name or ''}".strip()
                }
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'enfant: {e}")
            return Response({
                'valid': False,
                'message': 'Erreur lors de la vérification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='demande-ajout-enfant')
    def demande_ajout_enfant(self, request):
        """Crée une demande d'ajout d'enfant"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'parent':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            data = request.data
            email = data.get('email')
            matricule = data.get('matricule')
            
            if not email and not matricule:
                return Response({
                    'error': 'Email ou matricule requis'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Chercher l'enfant
            enfant = None
            if email:
                try:
                    enfant = Utilisateur.objects.get(email=email, role='eleve')
                except Utilisateur.DoesNotExist:
                    pass
            
            if not enfant and matricule:
                try:
                    enfant = Utilisateur.objects.get(matricule=matricule, role='eleve')
                except Utilisateur.DoesNotExist:
                    pass
            
            if not enfant:
                return Response({
                    'error': 'Aucun élève trouvé avec ces informations'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Vérifier si l'enfant n'est pas déjà lié
            if LienParentEnfant.objects.filter(enfant=enfant, actif=True).exists():
                return Response({
                    'error': 'Cet élève est déjà lié à un parent'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Créer la demande (simulation - à adapter selon votre modèle)
            # Pour l'instant, on crée directement le lien parent-enfant
            
            try:
                lien, created = LienParentEnfant.objects.get_or_create(
                    parent=request.user,
                    enfant=enfant,
                    defaults={
                        'actif': False,  # En attente de confirmation
                        'date_confirmation': timezone.now()  # Date de création de la demande
                    }
                )
                
                if not created:
                    return Response({
                        'error': 'Une demande est déjà en cours pour cet élève'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                return Response({
                    'success': True,
                    'message': 'Demande envoyée avec succès',
                    'nom_enfant': f"{enfant.first_name or ''} {enfant.last_name or ''}".strip() or enfant.email
                })
                
            except Exception as e:
                logger.error(f"Erreur lors de la création du lien parent-enfant: {e}")
                return Response({
                    'error': f'Erreur lors de la création du lien: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la demande: {e}")
            return Response({
                'error': 'Erreur lors de la création de la demande'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='demandes-parente')
    def demandes_parente(self, request):
        """Récupère les demandes de lien de parenté pour un élève"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'eleve':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer les demandes en attente pour cet élève
            demandes = LienParentEnfant.objects.filter(
                enfant=request.user,
                actif=False  # Demandes en attente de confirmation
            ).select_related('parent')
            
            demandes_data = []
            for demande in demandes:
                demandes_data.append({
                    'id': demande.id,
                    'parent_nom': f"{demande.parent.first_name or ''} {demande.parent.last_name or ''}".strip() or demande.parent.email,
                    'parent_email': demande.parent.email,
                    'date_demande': demande.date_creation,
                    'statut': 'en_attente'
                })
            
            return Response({
                'success': True,
                'demandes': demandes_data
            })
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des demandes de parenté: {e}")
            return Response({
                'error': 'Erreur lors du chargement des demandes'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='confirmer-demande-parente')
    def confirmer_demande_parente(self, request):
        """Confirme une demande de lien de parenté"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'eleve':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            demande_id = request.data.get('demande_id')
            if not demande_id:
                return Response({'error': 'ID de demande requis'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Récupérer la demande
            try:
                demande = LienParentEnfant.objects.get(
                    id=demande_id,
                    enfant=request.user,
                    actif=False
                )
            except LienParentEnfant.DoesNotExist:
                return Response({'error': 'Demande non trouvée'}, status=status.HTTP_404_NOT_FOUND)
            
            # Confirmer la demande
            demande.actif = True
            demande.date_confirmation = timezone.now()
            demande.save()
            
            return Response({
                'success': True,
                'message': 'Demande confirmée avec succès'
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la confirmation de la demande: {e}")
            return Response({
                'error': 'Erreur lors de la confirmation'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='refuser-demande-parente')
    def refuser_demande_parente(self, request):
        """Refuse une demande de lien de parenté"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'eleve':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            demande_id = request.data.get('demande_id')
            if not demande_id:
                return Response({'error': 'ID de demande requis'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Récupérer la demande
            try:
                demande = LienParentEnfant.objects.get(
                    id=demande_id,
                    enfant=request.user,
                    actif=False
                )
            except LienParentEnfant.DoesNotExist:
                return Response({'error': 'Demande non trouvée'}, status=status.HTTP_404_NOT_FOUND)
            
            # Supprimer la demande
            demande.delete()
            
            return Response({
                'success': True,
                'message': 'Demande refusée'
            })
            
        except Exception as e:
            logger.error(f"Erreur lors du refus de la demande: {e}")
            return Response({
                'error': 'Erreur lors du refus'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='repondre-demande-parente')
    def repondre_demande_parente(self, request):
        """Répond à une demande de lien de parenté (accepter ou refuser)"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            if request.user.role != 'eleve':
                return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
            
            demande_id = request.data.get('demande_id')
            accepte = request.data.get('accepte')
            
            if not demande_id or accepte is None:
                return Response({'error': 'ID de demande et statut requis'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Récupérer la demande
            try:
                demande = LienParentEnfant.objects.get(
                    id=demande_id,
                    enfant=request.user,
                    actif=False
                )
            except LienParentEnfant.DoesNotExist:
                return Response({'error': 'Demande non trouvée'}, status=status.HTTP_404_NOT_FOUND)
            
            if accepte:
                # Confirmer la demande
                demande.actif = True
                demande.date_confirmation = timezone.now()
                demande.save()
                
                return Response({
                    'success': True,
                    'message': 'Demande acceptée avec succès'
                })
            else:
                # Refuser la demande
                demande.delete()
                
                return Response({
                    'success': True,
                    'message': 'Demande refusée'
                })
            
        except Exception as e:
            logger.error(f"Erreur lors de la réponse à la demande: {e}")
            return Response({
                'error': 'Erreur lors de la réponse à la demande'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='profil_public')
    def profil_public(self, request):
        """Récupère les données du profil public de l'utilisateur"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            user = request.user
            
            # Récupérer les préférences de l'utilisateur
            preferences = self.get_user_preferences(user)
            
            # Vérifier si le profil public est activé
            if not preferences.get('profil_public', False):
                return Response({'error': 'Profil public non activé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer les données de progression
            from progression.models import ProgressionMatiere, ProgressionChapitre
            from cours.models import Chapitre
            
            # Statistiques globales
            total_chapitres = Chapitre.objects.filter(actif=True).count()
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut='termine'
            ).count()
            chapitres_commences = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut='en_cours'
            ).count()
            
            # Calculer la progression moyenne
            progressions = ProgressionMatiere.objects.filter(etudiant=user)
            progression_moyenne = 0
            if progressions.exists():
                progression_moyenne = sum(p.pourcentage_completion for p in progressions) / progressions.count()
            
            # Temps total d'étude
            temps_total = ProgressionChapitre.objects.filter(
                etudiant=user
            ).aggregate(
                total=models.Sum('temps_etudie')
            )['total'] or 0
            
            profil_data = {
                'nom': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                'niveau': user.niveau.nom if hasattr(user, 'niveau') and user.niveau else 'Non défini',
                'avatar': user.avatar if hasattr(user, 'avatar') else 'default',
                'statistiques_globales': {
                    'chapitres_termines': chapitres_termines,
                    'chapitres_commences': chapitres_commences,
                    'total_chapitres': total_chapitres,
                    'progression_moyenne': round(progression_moyenne, 1),
                    'temps_total': temps_total
                },
                'progres_detailles': []
            }
            
            # Ajouter les détails par matière
            for progression in progressions:
                profil_data['progres_detailles'].append({
                    'matiere': progression.matiere.nom,
                    'pourcentage': round(progression.pourcentage_completion, 1),
                    'statut': progression.statut,
                    'chapitres_termines': progression.nombre_chapitres_termines,
                    'chapitres_total': progression.nombre_chapitres_total
                })
            
            return Response(profil_data)
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du profil public: {e}")
            return Response({
                'error': 'Erreur lors du chargement du profil public'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='partage_progres')
    def partage_progres(self, request):
        """Récupère les données de partage des progrès de l'utilisateur"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            user = request.user
            
            # Récupérer les préférences de l'utilisateur
            preferences = self.get_user_preferences(user)
            
            # Vérifier si le partage des progrès est activé
            if not preferences.get('partage_progres', False):
                return Response({'error': 'Partage des progrès non activé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer les données de progression détaillées
            from progression.models import ProgressionMatiere, ProgressionChapitre
            from cours.models import Chapitre
            
            # Statistiques globales
            total_chapitres = Chapitre.objects.filter(actif=True).count()
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut='termine'
            ).count()
            chapitres_commences = ProgressionChapitre.objects.filter(
                etudiant=user,
                statut='en_cours'
            ).count()
            
            # Calculer la progression moyenne
            progressions = ProgressionMatiere.objects.filter(etudiant=user)
            progression_moyenne = 0
            if progressions.exists():
                progression_moyenne = sum(p.pourcentage_completion for p in progressions) / progressions.count()
            
            # Temps total d'étude
            temps_total = ProgressionChapitre.objects.filter(
                etudiant=user
            ).aggregate(
                total=models.Sum('temps_etudie')
            )['total'] or 0
            
            progres_data = {
                'statistiques_globales': {
                    'chapitres_termines': chapitres_termines,
                    'chapitres_commences': chapitres_commences,
                    'total_chapitres': total_chapitres,
                    'progression_moyenne': round(progression_moyenne, 1),
                    'temps_total': temps_total
                },
                'progres_detailles': []
            }
            
            # Ajouter les détails par matière
            for progression in progressions:
                progres_data['progres_detailles'].append({
                    'matiere': progression.matiere.nom,
                    'pourcentage': round(progression.pourcentage_completion, 1),
                    'statut': progression.statut,
                    'chapitres_termines': progression.nombre_chapitres_termines,
                    'chapitres_total': progression.nombre_chapitres_total,
                    'temps_etudie': progression.temps_etudie_total
                })
            
            return Response(progres_data)
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des progrès partagés: {e}")
            return Response({
                'error': 'Erreur lors du chargement des progrès partagés'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_user_preferences(self, user):
        """Récupère les préférences de l'utilisateur"""
        try:
            from .models import PreferencesUtilisateur
            
            # Récupérer ou créer les préférences de l'utilisateur
            preferences, created = PreferencesUtilisateur.objects.get_or_create(
                utilisateur=user,
                defaults={
                    'notifications_email': True,
                    'rappels_etude': True,
                    'partage_progres': False,
                    'profil_public': False,
                    'langue': 'fr',
                    'pays': 'Côte d\'Ivoire'
                }
            )
            
            return {
                'profil_public': preferences.profil_public,
                'partage_progres': preferences.partage_progres,
                'notifications_email': preferences.notifications_email,
                'rappels_etude': preferences.rappels_etude,
                'langue': preferences.langue,
                'pays': preferences.pays
            }
        except Exception:
            return {
                'profil_public': False,
                'partage_progres': False,
                'notifications_email': True,
                'rappels_etude': True,
                'langue': 'fr',
                'pays': 'Côte d\'Ivoire'
            }

    @action(detail=False, methods=['get'], url_path='preferences')
    def get_preferences(self, request):
        """Récupère les préférences de l'utilisateur"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            preferences = self.get_user_preferences(request.user)
            return Response(preferences)
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des préférences: {e}")
            return Response({
                'error': 'Erreur lors du chargement des préférences'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='update-preferences')
    def update_preferences(self, request):
        """Met à jour les préférences de l'utilisateur"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            user = request.user
            data = request.data
            
            # Mettre à jour les préférences dans le modèle PreferencesUtilisateur
            from .models import PreferencesUtilisateur
            
            preferences, created = PreferencesUtilisateur.objects.get_or_create(
                utilisateur=user,
                defaults={
                    'notifications_email': True,
                    'rappels_etude': True,
                    'partage_progres': False,
                    'profil_public': False,
                    'langue': 'fr',
                    'pays': 'Côte d\'Ivoire'
                }
            )
            
            updated_preferences = {}
            
            for key, value in data.items():
                if key in ['profil_public', 'partage_progres', 'notifications_email', 'rappels_etude', 'langue', 'pays']:
                    setattr(preferences, key, value)
                    updated_preferences[key] = value
            
            # Sauvegarder les préférences
            preferences.save()
            
            return Response({
                'success': True,
                'message': 'Préférences mises à jour avec succès',
                'preferences': updated_preferences
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des préférences: {e}")
            return Response({
                'error': 'Erreur lors de la mise à jour des préférences'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['patch'], url_path='patch-preferences')
    def patch_preferences(self, request):
        """Met à jour une préférence spécifique de l'utilisateur"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            user = request.user
            data = request.data
            
            # Mettre à jour la préférence spécifique dans le modèle PreferencesUtilisateur
            from .models import PreferencesUtilisateur
            
            preferences, created = PreferencesUtilisateur.objects.get_or_create(
                utilisateur=user,
                defaults={
                    'notifications_email': True,
                    'rappels_etude': True,
                    'partage_progres': False,
                    'profil_public': False,
                    'langue': 'fr',
                    'pays': 'Côte d\'Ivoire'
                }
            )
            
            updated_preferences = {}
            
            for key, value in data.items():
                if key in ['profil_public', 'partage_progres', 'notifications_email', 'rappels_etude', 'langue', 'pays']:
                    setattr(preferences, key, value)
                    updated_preferences[key] = value
            
            # Sauvegarder les préférences
            preferences.save()
            
            return Response({
                'success': True,
                'message': 'Préférence mise à jour avec succès',
                'preferences': updated_preferences
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la préférence: {e}")
            return Response({
                'error': 'Erreur lors de la mise à jour de la préférence'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='badges')
    def get_user_badges(self, request, pk=None):
        """Récupère les badges d'un utilisateur spécifique"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Récupérer l'utilisateur cible
            try:
                target_user = Utilisateur.objects.get(id=pk)
            except Utilisateur.DoesNotExist:
                return Response({'error': 'Utilisateur non trouvé'}, status=status.HTTP_404_NOT_FOUND)
            
            # Vérifier si le partage des progrès est activé pour cet utilisateur
            target_preferences = self.get_user_preferences(target_user)
            if not target_preferences.get('partage_progres', False):
                return Response({'error': 'Partage des progrès non activé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer les badges de l'utilisateur
            try:
                from gamification.models import BadgeEtudiant
                badges = BadgeEtudiant.objects.filter(etudiant=target_user).select_related('badge')
                
                badges_data = []
                for badge_etudiant in badges:
                    badges_data.append({
                        'id': badge_etudiant.badge.id,
                        'nom': badge_etudiant.badge.nom,
                        'description': badge_etudiant.badge.description,
                        'icone': badge_etudiant.badge.icone,
                        'couleur': badge_etudiant.badge.couleur,
                        'date_obtention': badge_etudiant.date_obtention,
                        'rarete': badge_etudiant.badge.rarete
                    })
                
                return Response(badges_data)
                
            except ImportError:
                # Si le modèle gamification n'existe pas encore
                return Response([])
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des badges: {e}")
            return Response({
                'error': 'Erreur lors du chargement des badges'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='activite-recente')
    def get_user_activity(self, request, pk=None):
        """Récupère l'activité récente d'un utilisateur spécifique"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Récupérer l'utilisateur cible
            try:
                target_user = Utilisateur.objects.get(id=pk)
            except Utilisateur.DoesNotExist:
                return Response({'error': 'Utilisateur non trouvé'}, status=status.HTTP_404_NOT_FOUND)
            
            # Vérifier si le partage des progrès est activé pour cet utilisateur
            target_preferences = self.get_user_preferences(target_user)
            if not target_preferences.get('partage_progres', False):
                return Response({'error': 'Partage des progrès non activé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer l'activité récente
            try:
                from progression.models import ProgressionContenu, ProgressionChapitre
                from quiz.models import TentativeQuiz
                from django.utils import timezone
                from datetime import timedelta
                
                # Activité des 7 derniers jours
                date_limite = timezone.now() - timedelta(days=7)
                
                activities = []
                
                # Cours terminés récemment
                cours_recents = ProgressionContenu.objects.filter(
                    etudiant=target_user,
                    lu=True,
                    date_completion__gte=date_limite
                ).select_related('contenu__chapitre__matiere').order_by('-date_completion')[:5]
                
                for cours in cours_recents:
                    activities.append({
                        'type': 'cours',
                        'titre': cours.contenu.titre,
                        'matiere': cours.contenu.chapitre.matiere.nom,
                        'date': cours.date_completion,
                        'icon': 'fas fa-book',
                        'icon_class': 'text-primary'
                    })
                
                # Quiz récents
                quiz_recents = TentativeQuiz.objects.filter(
                    etudiant=target_user,
                    date_debut__gte=date_limite
                ).select_related('quiz').order_by('-date_debut')[:5]
                
                for quiz in quiz_recents:
                    activities.append({
                        'type': 'quiz',
                        'titre': quiz.quiz.titre,
                        'score': quiz.score,
                        'date': quiz.date_debut,
                        'icon': 'fas fa-question-circle',
                        'icon_class': 'text-success'
                    })
                
                # Chapitres terminés récemment
                chapitres_recents = ProgressionChapitre.objects.filter(
                    etudiant=target_user,
                    statut='termine',
                    date_completion__gte=date_limite
                ).select_related('chapitre__matiere').order_by('-date_completion')[:5]
                
                for chapitre in chapitres_recents:
                    activities.append({
                        'type': 'chapitre',
                        'titre': chapitre.chapitre.titre,
                        'matiere': chapitre.chapitre.matiere.nom,
                        'date': chapitre.date_completion,
                        'icon': 'fas fa-graduation-cap',
                        'icon_class': 'text-warning'
                    })
                
                # Trier par date décroissante
                activities.sort(key=lambda x: x['date'], reverse=True)
                
                # Formater les dates
                for activity in activities:
                    activity['date_formatted'] = activity['date'].strftime('%d/%m/%Y à %H:%M')
                
                return Response(activities[:10])  # Limiter à 10 activités
                
            except ImportError:
                # Si les modèles n'existent pas encore
                return Response([])
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'activité: {e}")
            return Response({
                'error': 'Erreur lors du chargement de l\'activité'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='partage_progres')
    def get_shared_progress(self, request, pk=None):
        """Récupère les données de partage des progrès d'un utilisateur spécifique"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Récupérer l'utilisateur cible
            try:
                target_user = Utilisateur.objects.get(id=pk)
            except Utilisateur.DoesNotExist:
                return Response({'error': 'Utilisateur non trouvé'}, status=status.HTTP_404_NOT_FOUND)
            
            # Vérifier si le partage des progrès est activé pour cet utilisateur
            target_preferences = self.get_user_preferences(target_user)
            if not target_preferences.get('partage_progres', False):
                return Response({'error': 'Partage des progrès non activé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer les données de progression détaillées
            from progression.models import ProgressionMatiere, ProgressionChapitre
            from cours.models import Chapitre
            
            # Statistiques globales
            total_chapitres = Chapitre.objects.filter(actif=True).count()
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=target_user,
                statut='termine'
            ).count()
            chapitres_commences = ProgressionChapitre.objects.filter(
                etudiant=target_user,
                statut='en_cours'
            ).count()
            
            # Calculer la progression moyenne
            progressions = ProgressionMatiere.objects.filter(etudiant=target_user)
            progression_moyenne = 0
            if progressions.exists():
                progression_moyenne = sum(p.pourcentage_completion for p in progressions) / progressions.count()
            
            # Temps total d'étude
            temps_total = ProgressionChapitre.objects.filter(
                etudiant=target_user
            ).aggregate(
                total=models.Sum('temps_etudie')
            )['total'] or 0
            
            progres_data = {
                'statistiques_globales': {
                    'chapitres_termines': chapitres_termines,
                    'chapitres_commences': chapitres_commences,
                    'total_chapitres': total_chapitres,
                    'progression_moyenne': round(progression_moyenne, 1),
                    'temps_total': temps_total
                },
                'progres_detailles': []
            }
            
            # Ajouter les détails par matière
            for progression in progressions:
                progres_data['progres_detailles'].append({
                    'matiere': progression.matiere.nom,
                    'pourcentage': round(progression.pourcentage_completion, 1),
                    'statut': progression.statut,
                    'chapitres_termines': progression.nombre_chapitres_termines,
                    'chapitres_total': progression.nombre_chapitres_total,
                    'temps_etudie': progression.temps_etudie_total
                })
            
            return Response(progres_data)
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des progrès partagés: {e}")
            return Response({
                'error': 'Erreur lors du chargement des progrès partagés'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='profil-public')
    def get_public_profile(self, request, pk=None):
        """Récupère le profil public d'un utilisateur spécifique"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Non authentifié'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Récupérer l'utilisateur cible
            try:
                target_user = Utilisateur.objects.get(id=pk)
            except Utilisateur.DoesNotExist:
                return Response({'error': 'Utilisateur non trouvé'}, status=status.HTTP_404_NOT_FOUND)
            
            # Vérifier si le profil public est activé pour cet utilisateur
            target_preferences = self.get_user_preferences(target_user)
            if not target_preferences.get('profil_public', False):
                return Response({'error': 'Profil non public'}, status=status.HTTP_403_FORBIDDEN)
            
            # Récupérer les données de progression
            from progression.models import ProgressionMatiere, ProgressionChapitre
            from cours.models import Chapitre
            
            # Statistiques globales
            total_chapitres = Chapitre.objects.filter(actif=True).count()
            chapitres_termines = ProgressionChapitre.objects.filter(
                etudiant=target_user,
                statut='termine'
            ).count()
            chapitres_commences = ProgressionChapitre.objects.filter(
                etudiant=target_user,
                statut='en_cours'
            ).count()
            
            # Calculer la progression moyenne
            progressions = ProgressionMatiere.objects.filter(etudiant=target_user)
            progression_moyenne = 0
            if progressions.exists():
                progression_moyenne = sum(p.pourcentage_completion for p in progressions) / progressions.count()
            
            # Temps total d'étude
            temps_total = ProgressionChapitre.objects.filter(
                etudiant=target_user
            ).aggregate(
                total=models.Sum('temps_etudie')
            )['total'] or 0
            
            # Récupérer les préférences de l'utilisateur
            target_preferences = self.get_user_preferences(target_user)
            
            profil_data = {
                'id': target_user.id,
                'nom': f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or target_user.email,
                'email': target_user.email,  # Inclure l'email dans le profil public
                'niveau': target_user.niveau.nom if hasattr(target_user, 'niveau') and target_user.niveau else 'Non défini',
                'avatar': target_user.avatar if hasattr(target_user, 'avatar') else 'default',
                'date_inscription': target_user.date_joined,
                'partage_progres': target_preferences.get('partage_progres', False),  # Inclure la préférence de partage
                'statistiques_globales': {
                    'chapitres_termines': chapitres_termines,
                    'chapitres_commences': chapitres_commences,
                    'total_chapitres': total_chapitres,
                    'progression_moyenne': round(progression_moyenne, 1),
                    'temps_total': temps_total
                },
                'progres_detailles': []
            }
            
            # Ajouter les détails par matière
            for progression in progressions:
                profil_data['progres_detailles'].append({
                    'matiere': progression.matiere.nom,
                    'pourcentage': round(progression.pourcentage_completion, 1),
                    'statut': progression.statut,
                    'chapitres_termines': progression.nombre_chapitres_termines,
                    'chapitres_total': progression.nombre_chapitres_total
                })
            
            return Response(profil_data)
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du profil public: {e}")
            return Response({
                'error': 'Erreur lors du chargement du profil public'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NiveauScolaireViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les niveaux scolaires"""
    from academic_structure.models import NiveauScolaire
    queryset = NiveauScolaire.objects.all()
    serializer_class = NiveauScolaireSerializer
    permission_classes = [AllowAny]


class PartenaireViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des partenaires"""
    serializer_class = UtilisateurPartenaireSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Retourne les partenaires de l'utilisateur connecté"""
        if self.request.user.role == 'partenaire':
            return Utilisateur.objects.filter(id=self.request.user.id)
        return Utilisateur.objects.none()
    
    @action(detail=False, methods=['get'])
    def mon_profil(self, request):
        """Récupérer le profil partenaire de l'utilisateur connecté"""
        if request.user.role != 'partenaire':
            return Response(
                {'error': 'Accès refusé. Rôle partenaire requis'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Calculer et mettre à jour le nombre de filleuls uniques
        request.user.calculer_nombre_filleuls_uniques()
        
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def mes_commissions(self, request):
        """Récupérer les commissions du partenaire"""
        if request.user.role != 'partenaire':
                return Response(
                {'error': 'Accès refusé. Rôle partenaire requis'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
        commissions = Commission.objects.filter(partenaire=request.user).order_by('-date_commission')
        serializer = CommissionSerializer(commissions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def mes_retraits(self, request):
        """Récupérer les retraits du partenaire"""
        if request.user.role != 'partenaire':
            return Response(
                {'error': 'Accès refusé. Rôle partenaire requis'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        retraits = RetraitCommission.objects.filter(partenaire=request.user).order_by('-date_demande')
        serializer = RetraitCommissionSerializer(retraits, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def mes_filleuls(self, request):
        """Récupérer les filleuls du partenaire"""
        if request.user.role != 'partenaire':
                return Response(
                {'error': 'Accès refusé. Rôle partenaire requis'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
        from abonnements.models import Parrainage
        from abonnements.models import Abonnement
        
        # Récupérer les parrainages du partenaire
        parrainages = Parrainage.objects.filter(parrain=request.user).select_related('filleul')
        
        filleuls_data = []
        for parrainage in parrainages:
            filleul = parrainage.filleul
            
            # Vérifier si le filleul a un abonnement actif
            abonnement_actif = Abonnement.objects.filter(
                utilisateur=filleul,
                statut='actif'
            ).exists()
            
            # Calculer la commission totale pour ce filleul
            # Récupérer les abonnements du filleul pour trouver les commissions
            abonnements_filleul = Abonnement.objects.filter(utilisateur=filleul)
            abonnement_ids = [ab.id for ab in abonnements_filleul]
            
            commission_totale = Commission.objects.filter(
                partenaire=request.user,
                abonnement_id__in=abonnement_ids
            ).aggregate(total=Sum('montant_commission'))['total'] or 0
            
            filleuls_data.append({
                'nom': filleul.last_name,
                'prenom': filleul.first_name,
                'email': filleul.email,
                'date_inscription': parrainage.date_parrainage,
                'abonnement_actif': abonnement_actif,
                'commission_totale': commission_totale
            })
        
        serializer = FilleulSerializer(filleuls_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def configuration_partenaire(self, request):
        """Récupérer la configuration partenaire pour l'inscription (accessible sans authentification)"""
        try:
            from .models import ConfigurationPartenaire
            config = ConfigurationPartenaire.get_configuration_active()
            serializer = ConfigurationSerializer(config)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la configuration: {str(e)}")
            return Response(
                {'error': 'Configuration non disponible'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def demander_retrait(self, request):
        """Demander un retrait de commission"""
        if request.user.role != 'partenaire':
            return Response(
                {'error': 'Accès refusé. Rôle partenaire requis'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        montant = request.data.get('montant')
        numero_wave = request.data.get('numero_wave')
        mot_de_passe = request.data.get('mot_de_passe')
        
        # Validation des champs requis
        if not montant:
            return Response({'error': 'Le montant est requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not numero_wave:
            return Response({'error': 'Le numéro Wave est requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not mot_de_passe:
            return Response({'error': 'Le mot de passe est requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validation du mot de passe
        from django.contrib.auth import authenticate
        user = authenticate(username=request.user.email, password=mot_de_passe)
        if not user:
            return Response({'error': 'Mot de passe incorrect'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            montant = float(montant)
        except (ValueError, TypeError):
            return Response({'error': 'Montant invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer la configuration partenaire
        from .models import ConfigurationPartenaire
        config = ConfigurationPartenaire.get_configuration_active()
        
        # Validation du montant
        if montant < config.seuil_retrait_minimum:
            return Response({
                'error': f'Le montant minimum est de {config.seuil_retrait_minimum} FCFA'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if montant % config.montant_retrait_multiple != 0:
            return Response({
                'error': f'Le montant doit être un multiple de {config.montant_retrait_multiple} FCFA'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que le partenaire a suffisamment de commission disponible
        from django.db.models import Sum
        from .models import Commission, RetraitCommission
        
        total_commissions = Commission.objects.filter(
            partenaire=request.user
        ).aggregate(total=Sum('montant_commission'))['total'] or 0
        
        total_retraits_approuves = RetraitCommission.objects.filter(
            partenaire=request.user,
            statut='approuve'
        ).aggregate(total=Sum('montant'))['total'] or 0
        
        commission_disponible = float(total_commissions) - float(total_retraits_approuves)
        
        if montant > commission_disponible:
            return Response({
                'error': f'Commission disponible insuffisante. Disponible: {commission_disponible} FCFA'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Créer la demande de retrait
        retrait = RetraitCommission.objects.create(
            partenaire=request.user,
            montant=montant,
            numero_wave=numero_wave,
            statut='en_attente'
        )
        
        return Response({
            'message': 'Demande de retrait créée avec succès',
            'retrait_id': retrait.id
        }, status=status.HTTP_201_CREATED)

    


    
class CommissionViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des commissions"""
    queryset = Commission.objects.all()
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]


class RetraitCommissionViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des retraits de commissions"""
    queryset = RetraitCommission.objects.all()
    serializer_class = RetraitCommissionSerializer
    permission_classes = [IsAuthenticated]

# views.py (dans l'app où se trouve ton modèle Utilisateur, ex: users/views.py)
from django.http import HttpResponse
from django.views import View
from django.shortcuts import render



class CreationOfSuperHeros(View):
    template_name = 'setup/creation_super_heros.html'  # nom de template pour la page de création du super-héros

    def get(self, request):
        secret = request.GET.get('secret', '')
        if secret != 'uiAwuxoMeeOYQXUH0P78jjlc23zMzOW60GW2krKTCzbLsGb7fQCODM6clLOYfUsiLap8J0xCZQQDl6wh2Kq9UXCODMMeilleurGameDeTousLesTemps':
            return HttpResponse("Accès refusé. Paramètre secret manquant ou incorrect.", status=403)
        
        return render(request, self.template_name)

    def post(self, request):
        secret = request.POST.get('secret', '')
        if secret != 'uiAwuxoMeeOYQXUH0P78jjlc23zMzOW60GW2krKTCzbLsGb7fQCODM6clLOYfUsiLap8J0xCZQQDl6wh2Kq9UXCODMMeilleurGameDeTousLesTemps':
            return HttpResponse("Accès refusé.", status=403)

        email = 'superhero@apprendschap.com'           # ← modifie si tu veux
        password = 'SuperHeroAFRIKAU0lzEcpxc6vAlybWYgOE!!'  # ← CHANGE ÇA IMMÉDIATEMENT APRÈS CHAQUE UTILISATION DE CETTE PAGE !
        first_name = 'Super'
        last_name = 'Héros'

        # Vérifie si existe déjà
        if Utilisateur.objects.filter(email=email).exists():
            return HttpResponse(f"Un super-héros avec l'email {email} existe déjà !")

        # Création via le manager custom (recommandé)
        try:
            user = Utilisateur.objects.create_superuser(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='admin',  # valeur par défaut, tu peux changer
                is_active=True,
                
                # Ajoute ces lignes pour éviter les contraintes NOT NULL ou champs manquants
                commission_retiree=0,
                commission_totale_accumulee=0,
                nombre_abonnements_parraines=0,
                nombre_filleuls_uniques=0,
                avatar_choisi='avatar1',  # obligatoire ? default existe, mais au cas où
                email_verifie=False,
                niveau=None,  # NULL OK si tu ne veux pas définir un niveau
                matricule=None,  # NULL OK si tu ne veux pas définir un matricule
                telephone=None,  # NULL OK si tu ne veux pas définir un numéro de téléphone
                date_inscription=timezone.now(),  # pour avoir une date réelle
                last_login=None,  # NULL OK si tu ne veux pas définir la dernière connexion
                is_staff=True,  # obligatoire pour superuser
                is_superuser=True,  # obligatoire pour superuser
            )
            return HttpResponse(
                f"Super-héros créé avec succès !<br>"
                f"Email: {email}<br>"
                f"Nom complet: {user.get_full_name()}<br>"
                f"Connecte-toi maintenant à /admin/ pour régner sur ApprendsChap !"
            )
        except Exception as e:
            return HttpResponse(f"Erreur lors de la création du super-héros : {str(e)}", status=500)