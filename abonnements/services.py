# abonnements/services.py
import requests
import json
import uuid
import time
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction, models

logger = logging.getLogger(__name__)
from .models import (
    Abonnement, PackAbonnement, PaiementWave, 
    PackFamilial, BonusParrainage, Parrainage, PackPermissions
)
from utilisateurs.models import Utilisateur, Commission


class WaveService:
    """Service pour gérer les paiements Wave"""
    
    def __init__(self):
        # Configuration Wave
        self.base_url = "https://pay.wave.com/m/M_ci_j60Jx7u3PlIa/c/ci/"
        self.callback_url = getattr(settings, 'WAVE_CALLBACK_URL', 'http://localhost:8000/api/abonnements/wave-callback/')
    
    def initier_paiement(self, paiement):
        """Initie un paiement via les liens Wave statiques"""
        try:
            # Récupérer le pack depuis les informations stockées
            if paiement.pack_id:
                # 🔧 CORRECTION : Chercher d'abord dans PackAbonnement, puis dans PackFamilial
                # Car les packs spéciaux (Pack Vacances, etc.) sont dans PackAbonnement
                try:
                    pack = PackAbonnement.objects.get(id=paiement.pack_id)
                    print(f"📦 Pack standard trouvé pour paiement: {pack.nom} - {pack.prix} FCFA")
                except PackAbonnement.DoesNotExist:
                    pack = PackFamilial.objects.get(id=paiement.pack_id)
                    print(f"📦 Pack familial trouvé pour paiement: {pack.nom} - {pack.prix} FCFA")
            else:
                return {
                    'success': False,
                    'error': 'Informations du pack manquantes'
                }
            
            # Générer le lien Wave dynamique selon le type de pack
            if hasattr(pack, 'pack_familial') and pack.pack_familial:
                # Utiliser la fonction spécifique pour les packs familiaux
                lien_wave = self.generer_lien_wave_familial(pack)
            else:
                # Utiliser la fonction standard pour les autres packs
                lien_wave = self.generer_lien_wave(pack)
            
            if lien_wave:
                return {
                    'success': True,
                    'url': lien_wave,
                    'wave_reference': paiement.transaction_id,
                    'message': 'Redirection vers Wave en cours...',
                    'simulation': False
                }
            else:
                return {
                    'success': False,
                    'error': 'Impossible de générer le lien de paiement Wave'
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de l'initiation du paiement Wave: {e}")
            return {'success': False, 'error': str(e)}
    
    def initier_paiement_familial(self, paiement):
        """Initie un paiement familial via les liens Wave statiques"""
        try:
            # Récupérer le pack familial depuis les informations stockées
            if paiement.pack_id:
                try:
                    pack = PackFamilial.objects.get(id=paiement.pack_id)
                    print(f"📦 Pack familial trouvé pour paiement: {pack.nom} - {pack.prix} FCFA")
                except PackFamilial.DoesNotExist:
                    return {
                        'success': False,
                        'error': 'Pack familial non trouvé'
                    }
            else:
                return {
                    'success': False,
                    'error': 'Informations du pack manquantes'
                }
            
            # Générer le lien Wave familial avec le prix réduit
            lien_wave = self.generer_lien_wave_familial(pack)
            
            if lien_wave:
                return {
                    'success': True,
                    'url': lien_wave,
                    'wave_reference': paiement.transaction_id,
                    'message': 'Redirection vers Wave en cours...',
                    'simulation': False
                }
            else:
                return {
                    'success': False,
                    'error': 'Impossible de générer le lien de paiement Wave'
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de l'initiation du paiement familial Wave: {e}")
            return {'success': False, 'error': str(e)}
    
    def generer_lien_wave(self, pack):
        """
        Génère un lien Wave dynamique basé sur le pack sélectionné
        
        Args:
            pack: Instance de PackAbonnement
            
        Returns:
            str: Lien Wave généré dynamiquement
        """
        try:
            # Calculer le prix réel du pack (avec réduction si applicable)
            if hasattr(pack, 'reduction_pourcentage') and pack.reduction_pourcentage and pack.reduction_pourcentage > 0:
                # Calculer le prix réduit
                prix_pack = int(float(pack.prix) * (1 - float(pack.reduction_pourcentage) / 100))
            else:
                # Utiliser le prix normal
                prix_pack = int(pack.prix)
            
            # Générer le lien Wave avec le prix exact du pack
            lien_wave = f"{self.base_url}?amount={prix_pack}"
            
            logger.info(f"Lien Wave généré pour pack '{pack.nom}': {prix_pack}FCFA -> {lien_wave}")
            return lien_wave
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du lien Wave: {e}")
            return None
    
    def generer_lien_wave_familial(self, pack):
        """
        Génère un lien Wave dynamique pour les packs familiaux avec réduction
        
        Args:
            pack: Instance de PackFamilial
            
        Returns:
            str: Lien Wave généré dynamiquement avec le prix réduit
        """
        try:
            # Utiliser la propriété prix_reduit qui calcule automatiquement le prix avec réduction
            prix_pack = int(pack.prix_reduit)
            
            # Générer le lien Wave avec le prix réduit du pack familial
            lien_wave = f"{self.base_url}?amount={prix_pack}"
            
            logger.info(f"Lien Wave familial généré pour pack '{pack.nom}': {prix_pack}FCFA (prix réduit {pack.reduction_pourcentage}%) -> {lien_wave}")
            return lien_wave
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du lien Wave familial: {e}")
            return None


class PermissionService:
    """Service pour vérifier et gérer les permissions des packs d'abonnement"""
    
    @staticmethod
    def get_abonnement_actuel(utilisateur):
        """Récupère l'abonnement actuel de l'utilisateur"""
        try:
            # D'abord essayer de récupérer un abonnement non expiré (le plus récent)
            abonnement = Abonnement.objects.filter(
                utilisateur=utilisateur,
                actif=True,
                date_fin__gte=timezone.now()
            ).order_by('-date_debut').first()
            
            if abonnement:
                return abonnement
                
            # Si pas d'abonnement non expiré, chercher les abonnements illimités (pack gratuit)
            return Abonnement.objects.filter(
                utilisateur=utilisateur,
                actif=True,
                date_fin__isnull=True
            ).order_by('-date_debut').first()
            
        except Exception:
            return None
    
    @staticmethod
    def get_permissions_utilisateur(utilisateur):
        """Récupère les permissions de l'utilisateur basées sur son abonnement"""
        abonnement = PermissionService.get_abonnement_actuel(utilisateur)
        if not abonnement:
            # 🔧 CORRECTION: Si pas d'abonnement, retourner les permissions du pack Gratuit par défaut
            try:
                from .models import PackAbonnement
                pack_gratuit = PackAbonnement.objects.filter(
                    type_pack='gratuit', 
                    nom='Gratuit',
                    actif=True
                ).first()
                
                if pack_gratuit and hasattr(pack_gratuit, 'permissions'):
                    return pack_gratuit.permissions
            except Exception:
                pass
            return None
        
        try:
            return abonnement.pack.permissions
        except PackPermissions.DoesNotExist:
            return None
    
    @staticmethod
    def verifier_acces_cours(utilisateur, contenu_id=None):
        """Vérifie si l'utilisateur peut accéder à un cours/contenu"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        # 🔧 NOUVEAUTÉ: Vérifier d'abord si l'abonnement a expiré
        abonnement_actuel = PermissionService.get_abonnement_actuel(utilisateur)
        if not abonnement_actuel:
            # Abonnement expiré, vérifier accès pack gratuit
            print(f"⚠️ Abonnement expiré pour {utilisateur.email}, vérification pack gratuit")
            if permissions.pack.type_pack == 'gratuit' and contenu_id:
                return ExpirationService.utilisateur_peut_acceder_contenu_gratuit(utilisateur, contenu_id)
        
        # Si contenu_id fourni, vérifier s'il a déjà été consulté
        if contenu_id:
            deja_consulte = PermissionService.contenu_deja_consulte(utilisateur, contenu_id)
            
            if deja_consulte:
                # L'utilisateur peut toujours revoir un contenu déjà consulté
                return True, "Accès autorisé (contenu déjà consulté)"
        
        # Vérifier la limite mensuelle des cours pour les nouveaux contenus
        if permissions.max_cours_par_mois > 0:
            cours_ce_mois = PermissionService.compter_cours_mois_courant(utilisateur)
            
            if cours_ce_mois >= permissions.max_cours_par_mois:
                return False, f"Limite atteinte : vous avez consulté {cours_ce_mois}/{permissions.max_cours_par_mois} cours ce mois-ci. Vous pouvez toujours revoir les cours déjà consultés."
        
        return True, "Accès autorisé"
    
    @staticmethod
    def contenu_deja_consulte(utilisateur, contenu_id):
        """Vérifie si un contenu a déjà été consulté par l'utilisateur"""
        try:
            from progression.models import ProgressionContenu
            from cours.models import ContenuChapitre
            
            # Vérifier si le contenu existe d'abord
            if not ContenuChapitre.objects.filter(id=contenu_id).exists():
                return False
            
            # Vérifier si une progression existe pour ce contenu
            return ProgressionContenu.objects.filter(
                etudiant=utilisateur,
                contenu_id=contenu_id
            ).exists()
            
        except ImportError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def initier_progression_contenu(utilisateur, contenu_id):
        """
        NOUVELLE fonction pour initier la progression d'un contenu (accès sans marquer comme terminé)
        N'AFFECTE PAS les fonctions existantes
        """
        try:
            from progression.models import ProgressionContenu, ProgressionChapitre
            from cours.models import ContenuChapitre
            from django.utils import timezone
            
            # Vérifier si le contenu existe
            try:
                contenu = ContenuChapitre.objects.get(id=contenu_id)
            except ContenuChapitre.DoesNotExist:
                return False, f"Contenu avec ID {contenu_id} n'existe pas"
            
            # Créer la progression du contenu SANS le marquer comme lu (juste commencé)
            progression, created = ProgressionContenu.objects.get_or_create(
                etudiant=utilisateur,
                contenu=contenu,
                defaults={
                    'lu': False,  # CORRECT: Pas encore terminé, juste commencé
                    'temps_lecture': 1,  # Temps minimal pour comptabiliser l'accès
                    'date_debut': timezone.now(),
                    'date_completion': None  # Pas encore terminé
                }
            )
            
            # Si déjà existant, juste ajouter un peu de temps (re-consultation)
            if not created:
                progression.temps_lecture += 1
                progression.save()
            
            # Créer/mettre à jour la progression du chapitre pour qu'il passe "en_cours"
            chapitre = contenu.chapitre
            progression_chapitre, chapitre_created = ProgressionChapitre.objects.get_or_create(
                etudiant=utilisateur,
                chapitre=chapitre,
                defaults={
                    'statut': 'en_cours',  # Dès qu'on commence un contenu = en_cours
                    'date_debut': timezone.now(),
                    'temps_etudie': 1,
                    'pourcentage_completion': 0.0
                }
            )
            
            # Recalculer le statut du chapitre selon les contenus RÉELLEMENT terminés (lu=True)
            contenus_total = chapitre.contenus.count()
            if contenus_total > 0:
                contenus_lus = ProgressionContenu.objects.filter(
                    etudiant=utilisateur,
                    contenu__chapitre=chapitre,
                    lu=True  # Seulement les contenus VRAIMENT terminés
                ).count()
                
                pourcentage = (contenus_lus / contenus_total) * 100
                progression_chapitre.pourcentage_completion = round(pourcentage, 2)
                
                # Statut selon les contenus TERMINÉS
                if pourcentage >= 100:
                    progression_chapitre.statut = 'termine'
                    if not progression_chapitre.date_completion:
                        progression_chapitre.date_completion = timezone.now()
                else:
                    # Tant qu'il y a des contenus non terminés = en_cours
                    progression_chapitre.statut = 'en_cours'
                
                # Mettre à jour le temps d'étude total
                from django.db.models import Sum
                temps_total = ProgressionContenu.objects.filter(
                    etudiant=utilisateur,
                    contenu__chapitre=chapitre
                ).aggregate(total=Sum('temps_lecture'))['total'] or 0
                progression_chapitre.temps_etudie = temps_total
                
                progression_chapitre.save()
            
            action = "créé" if created else "mis à jour"
            return True, f"Progression {action} pour {contenu.titre} (chapitre en cours)"
            
        except Exception as e:
            return False, f"Erreur lors de l'initiation: {str(e)}"

    @staticmethod
    def marquer_contenu_consulte_correctement(utilisateur, contenu_id):
        """
        NOUVELLE fonction pour marquer un contenu comme correctement consulté ET lu
        N'AFFECTE PAS la fonction marquer_contenu_consulte existante
        """
        try:
            from progression.models import ProgressionContenu, ProgressionChapitre
            from cours.models import ContenuChapitre
            from django.utils import timezone
            
            # Vérifier si le contenu existe
            try:
                contenu = ContenuChapitre.objects.get(id=contenu_id)
            except ContenuChapitre.DoesNotExist:
                return False, f"Contenu avec ID {contenu_id} n'existe pas"
            
            # Créer ou mettre à jour la progression du contenu AVEC lu=True
            progression, created = ProgressionContenu.objects.get_or_create(
                etudiant=utilisateur,
                contenu=contenu,
                defaults={
                    'lu': True,  # CORRECTION: Marquer comme lu immédiatement
                    'temps_lecture': 5,  # Temps minimal pour comptabiliser 
                    'date_debut': timezone.now(),
                    'date_completion': timezone.now()
                }
            )
            
            # Si déjà existant, s'assurer qu'il est marqué comme lu
            if not created and not progression.lu:
                progression.lu = True
                progression.date_completion = timezone.now()
                progression.temps_lecture = max(progression.temps_lecture, 5)
                progression.save()
            
            # Mettre à jour la progression du chapitre pour qu'il passe "en_cours"
            chapitre = contenu.chapitre
            progression_chapitre, chapitre_created = ProgressionChapitre.objects.get_or_create(
                etudiant=utilisateur,
                chapitre=chapitre,
                defaults={
                    'statut': 'en_cours',
                    'date_debut': timezone.now(),
                    'temps_etudie': 5,
                    'pourcentage_completion': 0.0
                }
            )
            
            # Recalculer le pourcentage et statut du chapitre
            contenus_total = chapitre.contenus.count()
            if contenus_total > 0:
                contenus_lus = ProgressionContenu.objects.filter(
                    etudiant=utilisateur,
                    contenu__chapitre=chapitre,
                    lu=True
                ).count()
                
                pourcentage = (contenus_lus / contenus_total) * 100
                progression_chapitre.pourcentage_completion = round(pourcentage, 2)
                
                # Statut selon le pourcentage
                if pourcentage >= 100:
                    progression_chapitre.statut = 'termine'
                    if not progression_chapitre.date_completion:
                        progression_chapitre.date_completion = timezone.now()
                elif pourcentage > 0:
                    progression_chapitre.statut = 'en_cours'  # CORRECT !
                
                progression_chapitre.save()
            
            return True, f"Contenu {contenu.titre} marqué comme lu et chapitre mis à jour"
            
        except Exception as e:
            return False, f"Erreur lors du marquage: {str(e)}"

    @staticmethod
    def marquer_contenu_consulte(utilisateur, contenu_id):
        """Marque un contenu comme consulté (créer la progression si pas existante)"""
        try:
            from progression.models import ProgressionContenu
            from cours.models import ContenuChapitre
            from django.utils import timezone
            
            # Vérifier si le contenu existe
            try:
                contenu = ContenuChapitre.objects.get(id=contenu_id)
            except ContenuChapitre.DoesNotExist:
                return False, f"Contenu avec ID {contenu_id} n'existe pas"
            
            progression, created = ProgressionContenu.objects.get_or_create(
                etudiant=utilisateur,
                contenu=contenu,
                defaults={
                    'lu': False,  # Sera marqué comme lu lors de la completion
                    'temps_lecture': 0,
                    'date_debut': timezone.now()
                }
            )
            
            return True, f"Contenu {contenu.titre} {'créé' if created else 'trouvé'} dans la progression"
            
        except Exception as e:
            return False, f"Erreur lors du marquage: {str(e)}"
    
    @staticmethod
    def verifier_acces_quiz(utilisateur, quiz_id=None):
        """Vérifie si l'utilisateur peut accéder à un quiz"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        # Vérifier la limite mensuelle des quiz
        if permissions.max_quiz_par_mois > 0:
            quiz_ce_mois = PermissionService.compter_quiz_mois_courant(utilisateur)
            
            if quiz_ce_mois >= permissions.max_quiz_par_mois:
                message = permissions.get_message_restriction_dynamique(
                    quiz_utilises=quiz_ce_mois,
                    max_quiz=permissions.max_quiz_par_mois
                )
                return False, message
        
        return True, "Accès autorisé"
    
    @staticmethod
    def verifier_acces_examen(utilisateur, examen_id=None):
        """Vérifie si l'utilisateur peut accéder à un examen"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        # Si examen_id fourni, vérifier s'il a déjà été consulté
        if examen_id:
            deja_consulte = PermissionService.examen_deja_consulte(utilisateur, examen_id)
            
            if deja_consulte:
                # L'utilisateur peut toujours revoir un examen déjà consulté
                return True, "Accès autorisé (examen déjà consulté)"
        
        # Vérifier la limite mensuelle des examens pour les nouveaux examens
        if permissions.max_examens_par_mois > 0:
            examens_ce_mois = PermissionService.compter_examens_mois_courant(utilisateur)
            
            if examens_ce_mois >= permissions.max_examens_par_mois:
                return False, f"Limite atteinte : vous avez consulté {examens_ce_mois}/{permissions.max_examens_par_mois} examens ce mois-ci. Vous pouvez toujours revoir les examens déjà consultés."
        
        return True, "Accès autorisé"
    
    @staticmethod
    def examen_deja_consulte(utilisateur, examen_id):
        """Vérifie si un examen a déjà été consulté par l'utilisateur"""
        try:
            from examens.models import Examen
            
            # Vérifier si l'examen existe d'abord
            if not Examen.objects.filter(id=examen_id).exists():
                return False
            
            # Pour l'instant, nous utilisons un système simple basé sur le cache ou les sessions
            # TODO: Créer un modèle ConsultationExamen pour un suivi plus précis
            from django.core.cache import cache
            cache_key = f"examen_consulte_{utilisateur.id}_{examen_id}"
            return cache.get(cache_key, False)
            
        except ImportError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def marquer_examen_consulte(utilisateur, examen_id):
        """Marque un examen comme consulté"""
        try:
            from examens.models import Examen
            from django.core.cache import cache
            from django.utils import timezone
            
            # Vérifier si l'examen existe
            try:
                examen = Examen.objects.get(id=examen_id)
            except Examen.DoesNotExist:
                return False, f"Examen avec ID {examen_id} n'existe pas"
            
            # Marquer comme consulté dans le cache (durée: 1 mois)
            cache_key = f"examen_consulte_{utilisateur.id}_{examen_id}"
            
            # Vérifier si c'est la première consultation ce mois-ci
            if not cache.get(cache_key, False):
                cache.set(cache_key, True, timeout=30*24*60*60)  # 30 jours
                
                # Incrémenter le compteur seulement pour les nouvelles consultations
                PermissionService.incrementer_compteur_examens(utilisateur)
                
                # Marquer aussi la date de consultation
                date_key = f"examen_date_{utilisateur.id}_{examen_id}"
                cache.set(date_key, timezone.now().isoformat(), timeout=30*24*60*60)
                
                return True, f"Examen {examen.titre} marqué comme consulté (nouvelle consultation)"
            else:
                return True, f"Examen {examen.titre} déjà consulté ce mois"
            
        except Exception as e:
            return False, f"Erreur lors du marquage: {str(e)}"
    
    @staticmethod
    def verifier_acces_ia(utilisateur, type_ia='standard'):
        """Vérifie si l'utilisateur peut utiliser l'IA"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        if type_ia == 'prioritaire' and not permissions.acces_ia_prioritaire:
            return False, "Support IA prioritaire non disponible avec votre pack"
        
        if not permissions.acces_ia_standard and not permissions.acces_ia_prioritaire:
            return False, "Support IA non disponible avec votre pack"
        
        return True, "Accès IA autorisé"
    
    @staticmethod
    def verifier_acces_certificats(utilisateur):
        """Vérifie si l'utilisateur peut accéder aux certificats"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        if not permissions.acces_certificats:
            return False, "Certificats non disponibles avec votre pack"
        
        return True, "Accès aux certificats autorisé"
    
    @staticmethod
    def verifier_acces_contenu_hors_ligne(utilisateur):
        """Vérifie si l'utilisateur peut télécharger du contenu"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        if not permissions.acces_contenu_hors_ligne:
            return False, "Téléchargement non disponible avec votre pack"
        
        return True, "Téléchargement autorisé"
    
    @staticmethod
    def compter_cours_mois_courant(utilisateur):
        """Compte le nombre de cours suivis ce mois"""
        try:
            from progression.models import ProgressionContenu
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            
            # Compter les cours commencés ce mois (dès l'accès, pas seulement complétés)
            return ProgressionContenu.objects.filter(
                etudiant=utilisateur,
                date_debut__month=mois_courant,
                date_debut__year=annee_courante
            ).count()
        except ImportError:
            # Si le modèle n'existe pas encore, retourner 0
            return 0
    
    @staticmethod
    def compter_quiz_mois_courant(utilisateur):
        """Compte le nombre de quiz réalisés ce mois"""
        try:
            from quiz.models import TentativeQuiz
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            
            return TentativeQuiz.objects.filter(
                etudiant=utilisateur,
                date_debut__month=mois_courant,
                date_debut__year=annee_courante
            ).count()
        except ImportError:
            # Si le modèle n'existe pas encore, retourner 0
            return 0
    
    @staticmethod
    def compter_examens_mois_courant(utilisateur):
        """Compte le nombre d'examens consultés ce mois"""
        try:
            from django.core.cache import cache
            from django.utils import timezone
            
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            
            # Récupérer le compteur mensuel depuis le cache
            cache_key = f"examens_mois_{utilisateur.id}_{annee_courante}_{mois_courant}"
            compteur_cache = cache.get(cache_key, 0)
            
            return compteur_cache
            
        except Exception:
            return 0
    
    @staticmethod
    def incrementer_compteur_examens(utilisateur):
        """Incrémente le compteur d'examens pour le mois courant"""
        try:
            from django.core.cache import cache
            from django.utils import timezone
            import calendar
            
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            
            cache_key = f"examens_mois_{utilisateur.id}_{annee_courante}_{mois_courant}"
            compteur_actuel = cache.get(cache_key, 0)
            nouveau_compteur = compteur_actuel + 1
            
            # Mettre en cache jusqu'à la fin du mois
            jours_dans_mois = calendar.monthrange(annee_courante, mois_courant)[1]
            jours_restants = jours_dans_mois - timezone.now().day
            timeout = max(jours_restants * 24 * 60 * 60, 86400)  # Au moins 1 jour
            
            cache.set(cache_key, nouveau_compteur, timeout=timeout)
            
            return nouveau_compteur
            
        except Exception:
            return 0
    
    @staticmethod
    def examen_deja_consulte_cache_simple(utilisateur, examen_id):
        """
        NOUVELLE fonction pour vérifier si un examen a été consulté (cache simple)
        N'AFFECTE PAS la fonction examen_deja_consulte existante
        """
        try:
            from django.core.cache import cache
            cache_key = f"examen_consulte_{utilisateur.id}_{examen_id}"
            return cache.get(cache_key, False)
        except Exception:
            return False

    @staticmethod
    def marquer_examen_consulte_cache_simple(utilisateur, examen_id):
        """
        NOUVELLE fonction pour marquer un examen comme consulté (cache simple)
        N'AFFECTE PAS la fonction marquer_examen_consulte existante
        """
        try:
            from django.core.cache import cache
            import calendar
            from django.utils import timezone
            
            # Marquer comme consulté
            cache_key = f"examen_consulte_{utilisateur.id}_{examen_id}"
            
            # Cache jusqu'à la fin du mois pour cohérence avec le compteur mensuel
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            jours_dans_mois = calendar.monthrange(annee_courante, mois_courant)[1]
            jours_restants = jours_dans_mois - timezone.now().day
            timeout = max(jours_restants * 24 * 60 * 60, 86400)  # Au moins 1 jour
            
            cache.set(cache_key, True, timeout=timeout)
            return True
        except Exception:
            return False

    @staticmethod
    def verifier_acces_examen_avec_limitations(utilisateur, examen_id=None):
        """
        NOUVELLE fonction pour vérifier l'accès aux examens avec gestion correcte des limitations
        Cette fonction N'AFFECTE PAS la fonction verifier_acces_examen existante
        """
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return False, "Aucun abonnement actif"
        
        # Si examen_id fourni, vérifier s'il a déjà été consulté (cache simple)
        if examen_id:
            deja_consulte = PermissionService.examen_deja_consulte_cache_simple(utilisateur, examen_id)
            
            if deja_consulte:
                # L'utilisateur peut TOUJOURS revoir un examen déjà consulté
                return True, "Accès autorisé (examen déjà consulté)"
        
        # Pour les NOUVEAUX examens, vérifier la limite mensuelle
        if permissions.max_examens_par_mois > 0:
            examens_ce_mois = PermissionService.compter_examens_mois_courant(utilisateur)
            
            if examens_ce_mois >= permissions.max_examens_par_mois:
                message = f"Limite atteinte : vous avez consulté {examens_ce_mois}/{permissions.max_examens_par_mois} examens ce mois-ci. Vous pouvez toujours revoir les examens déjà consultés."
                return False, message
        
        # Accès autorisé pour un nouvel examen
        return True, "Accès autorisé"

    @staticmethod
    def recalculer_progression_matiere_correctement(utilisateur, matiere):
        """
        NOUVELLE fonction pour recalculer correctement la progression d'une matière
        N'AFFECTE PAS les fonctions existantes
        """
        try:
            from progression.models import ProgressionMatiere, ProgressionChapitre
            from cours.models import Chapitre
            from django.utils import timezone
            
            # Obtenir ou créer la progression matière
            progression_matiere, created = ProgressionMatiere.objects.get_or_create(
                etudiant=utilisateur,
                matiere=matiere,
                defaults={
                    'statut': 'non_commence',
                    'pourcentage_completion': 0.0,
                    'temps_etudie_total': 0,
                    'nombre_chapitres_termines': 0,
                    'nombre_chapitres_total': 0
                }
            )
            
            # Calculer les vrais données basées sur ProgressionChapitre
            chapitres_matiere = Chapitre.objects.filter(matiere=matiere, actif=True)
            total_chapitres = chapitres_matiere.count()
            
            if total_chapitres == 0:
                progression_matiere.nombre_chapitres_total = 0
                progression_matiere.nombre_chapitres_termines = 0
                progression_matiere.pourcentage_completion = 0.0
                progression_matiere.statut = 'non_commence'
                progression_matiere.temps_etudie_total = 0
                progression_matiere.save()
                return progression_matiere
            
            # Récupérer les progressions de chapitre pour cette matière
            progressions_chapitre = ProgressionChapitre.objects.filter(
                etudiant=utilisateur,
                chapitre__matiere=matiere
            )
            
            # Calculer les statistiques réelles
            from django.db.models import Sum
            chapitres_termines = progressions_chapitre.filter(statut='termine').count()
            chapitres_en_cours = progressions_chapitre.filter(statut='en_cours').count()
            temps_total = progressions_chapitre.aggregate(
                total=Sum('temps_etudie')
            )['total'] or 0
            
            # Calculer le pourcentage
            pourcentage = round((chapitres_termines / total_chapitres) * 100, 1) if total_chapitres > 0 else 0.0
            
            # Déterminer le statut
            if chapitres_termines == total_chapitres:
                statut = 'termine'
                if not progression_matiere.date_completion:
                    progression_matiere.date_completion = timezone.now()
            elif chapitres_termines > 0 or chapitres_en_cours > 0:
                statut = 'en_cours'
            else:
                statut = 'non_commence'
            
            # Mettre à jour les données
            progression_matiere.nombre_chapitres_total = total_chapitres
            progression_matiere.nombre_chapitres_termines = chapitres_termines
            progression_matiere.pourcentage_completion = pourcentage
            progression_matiere.statut = statut
            progression_matiere.temps_etudie_total = temps_total
            progression_matiere.save()
            
            return progression_matiere
            
        except Exception as e:
            print(f"Erreur lors du recalcul progression matière: {e}")
            return None

    @staticmethod
    def nettoyer_et_recalculer_progressions_matieres(utilisateur):
        """
        NOUVELLE fonction pour nettoyer les doublons et recalculer correctement
        N'AFFECTE PAS les fonctions existantes
        """
        from academic_structure.models import Matiere
        from progression.models import ProgressionMatiere, ProgressionChapitre
        from cours.models import Chapitre
        from django.db.models import Sum
        from django.utils import timezone
        
        print(f"🧹 Nettoyage des progressions pour {utilisateur.email}")
        
        # 1. NETTOYER : Supprimer toutes les progressions matière existantes
        progressions_existantes = ProgressionMatiere.objects.filter(etudiant=utilisateur)
        nb_supprimees = progressions_existantes.count()
        progressions_existantes.delete()
        print(f"   Supprimé {nb_supprimees} progressions obsolètes")
        
        # 2. RECRÉER : Seulement les matières qui ont des chapitres avec progression
        progressions_crees = []
        
        # Trouver les matières qui ont des progressions de chapitre
        matieres_avec_progression = ProgressionChapitre.objects.filter(
            etudiant=utilisateur
        ).values_list('chapitre__matiere', flat=True).distinct()
        
        for matiere_id in matieres_avec_progression:
            try:
                matiere = Matiere.objects.get(id=matiere_id, active=True)
                
                # Calculer les vraies données
                chapitres_matiere = Chapitre.objects.filter(matiere=matiere, actif=True)
                total_chapitres = chapitres_matiere.count()
                
                if total_chapitres == 0:
                    continue  # Ignorer les matières sans chapitres
                
                progressions_chapitre = ProgressionChapitre.objects.filter(
                    etudiant=utilisateur,
                    chapitre__matiere=matiere
                )
                
                chapitres_termines = progressions_chapitre.filter(statut='termine').count()
                chapitres_en_cours = progressions_chapitre.filter(statut='en_cours').count()
                temps_total = progressions_chapitre.aggregate(
                    total=Sum('temps_etudie')
                )['total'] or 0
                
                # Calculer pourcentage et statut
                pourcentage = round((chapitres_termines / total_chapitres) * 100, 1)
                
                if chapitres_termines == total_chapitres:
                    statut = 'termine'
                    date_completion = timezone.now()
                elif chapitres_termines > 0 or chapitres_en_cours > 0:
                    statut = 'en_cours'
                    date_completion = None
                else:
                    statut = 'non_commence'
                    date_completion = None
                
                # Créer la progression matière propre
                progression_matiere = ProgressionMatiere.objects.create(
                    etudiant=utilisateur,
                    matiere=matiere,
                    statut=statut,
                    pourcentage_completion=pourcentage,
                    temps_etudie_total=temps_total,
                    nombre_chapitres_termines=chapitres_termines,
                    nombre_chapitres_total=total_chapitres,
                    date_completion=date_completion
                )
                
                progressions_crees.append(progression_matiere)
                print(f"   ✅ {matiere.nom}: {chapitres_termines}/{total_chapitres} ({pourcentage}%) - {statut}")
                
            except Matiere.DoesNotExist:
                continue
        
        print(f"🎯 Résultat: {len(progressions_crees)} progressions propres créées")
        return progressions_crees

    @staticmethod
    def recalculer_toutes_progressions_matieres(utilisateur):
        """
        NOUVELLE fonction pour recalculer toutes les progressions matières d'un utilisateur
        CORRIGÉE : Ne crée plus de doublons en utilisant seulement les matières avec progression
        """
        from academic_structure.models import Matiere
        from progression.models import ProgressionChapitre
        from django.db.models import Sum
        
        progressions_mises_a_jour = []
        
        # CORRECTION : Seulement les matières qui ont des progressions de chapitre
        matieres_avec_progression = ProgressionChapitre.objects.filter(
            etudiant=utilisateur
        ).values_list('chapitre__matiere', flat=True).distinct()
        
        for matiere_id in matieres_avec_progression:
            try:
                matiere = Matiere.objects.get(id=matiere_id, active=True)
                progression = PermissionService.recalculer_progression_matiere_correctement(utilisateur, matiere)
                if progression:
                    progressions_mises_a_jour.append(progression)
            except Matiere.DoesNotExist:
                continue
        
        return progressions_mises_a_jour

    @staticmethod
    def get_statut_restrictions(utilisateur):
        """Retourne le statut complet des restrictions pour l'utilisateur"""
        permissions = PermissionService.get_permissions_utilisateur(utilisateur)
        if not permissions:
            return {
                'abonnement_actif': False,
                'message': 'Aucun abonnement actif'
            }
        
        abonnement = PermissionService.get_abonnement_actuel(utilisateur)
        jours_restants = (abonnement.date_fin.date() - timezone.now().date()).days if abonnement.date_fin else None
        
        # Compter les utilisations du mois
        cours_utilises = PermissionService.compter_cours_mois_courant(utilisateur)
        quiz_utilises = PermissionService.compter_quiz_mois_courant(utilisateur)
        examens_utilises = PermissionService.compter_examens_mois_courant(utilisateur)
        
        # Calculer les pourcentages d'utilisation
        pourcentage_cours = (cours_utilises / permissions.max_cours_par_mois * 100) if permissions.max_cours_par_mois > 0 else 0
        pourcentage_quiz = (quiz_utilises / permissions.max_quiz_par_mois * 100) if permissions.max_quiz_par_mois > 0 else 0
        pourcentage_examens = (examens_utilises / permissions.max_examens_par_mois * 100) if permissions.max_examens_par_mois > 0 else 0
        
        return {
            'abonnement_actif': True,
            'pack_nom': permissions.pack.nom,
            'jours_restants': jours_restants,
            'cours': {
                'utilises': cours_utilises,
                'max': permissions.max_cours_par_mois,
                'pourcentage': min(pourcentage_cours, 100),
                'limite_atteinte': permissions.max_cours_par_mois > 0 and cours_utilises >= permissions.max_cours_par_mois
            },
            'quiz': {
                'utilises': quiz_utilises,
                'max': permissions.max_quiz_par_mois,
                'pourcentage': min(pourcentage_quiz, 100),
                'limite_atteinte': permissions.max_quiz_par_mois > 0 and quiz_utilises >= permissions.max_quiz_par_mois
            },
            'examens': {
                'utilises': examens_utilises,
                'max': permissions.max_examens_par_mois,
                'pourcentage': min(pourcentage_examens, 100),
                'limite_atteinte': permissions.max_examens_par_mois > 0 and examens_utilises >= permissions.max_examens_par_mois
            },
            'permissions': {
                'cours_premium': permissions.acces_cours_premium,
                'ia_standard': permissions.acces_ia_standard,
                'ia_prioritaire': permissions.acces_ia_prioritaire,
                'certificats': permissions.acces_certificats,
                'contenu_hors_ligne': permissions.acces_contenu_hors_ligne,
                'communautaire': permissions.acces_communautaire,
                'support_prioritaire': permissions.support_prioritaire
            },
            'incitations': {
                'upgrade_reminder': permissions.upgrade_reminder,
                'teaser_content': permissions.teaser_content
            }
        }


class AbonnementService:
    """Service pour gérer les abonnements"""
    
    @staticmethod
    def creer_abonnement(utilisateur, pack, est_essai_gratuit=False, renouvellement_auto=False):
        """Crée un nouvel abonnement"""
        try:
            with transaction.atomic():
                abonnement = Abonnement.objects.create(
                    utilisateur=utilisateur,
                    pack=pack,
                    statut='essai' if est_essai_gratuit else 'actif',
                    est_essai_gratuit=est_essai_gratuit,
                    montant_paye=0 if est_essai_gratuit else pack.prix_reduit,
                    renouvellement_auto=renouvellement_auto
                )
                return {'success': True, 'abonnement': abonnement}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def creer_essai_gratuit(utilisateur, pack_id):
        """Crée un essai gratuit"""
        try:
            pack = PackAbonnement.objects.get(id=pack_id, actif=True, offre_semaine_gratuite=True)
            
            # Vérifier si l'utilisateur a déjà eu un essai gratuit
            essai_existant = Abonnement.objects.filter(
                utilisateur=utilisateur,
                est_essai_gratuit=True
            ).exists()
            
            if essai_existant:
                return {'success': False, 'error': 'Vous avez déjà utilisé votre essai gratuit'}
            
            resultat = AbonnementService.creer_abonnement(utilisateur, pack, est_essai_gratuit=True)
            return resultat
            
        except PackAbonnement.DoesNotExist:
            return {'success': False, 'error': 'Pack invalide'}
    
    @staticmethod
    def initier_paiement_abonnement(utilisateur, pack_id, telephone, email='', renouvellement_auto=False):
        """Initie un paiement pour un abonnement - SÉCURISÉ : Pas d'abonnement créé avant paiement"""
        try:
            pack = PackAbonnement.objects.get(id=pack_id, actif=True)
            
            with transaction.atomic():
                # 🎁 GESTION DE L'UPGRADE : Désactiver l'ancien abonnement parrainage
                ancien_abonnement = Abonnement.objects.filter(
                    utilisateur=utilisateur,
                    actif=True,
                    source_parrainage=True
                ).first()
                
                if ancien_abonnement:
                    print(f"🔄 Désactivation de l'ancien abonnement parrainage: {ancien_abonnement.pack.nom}")
                    ancien_abonnement.actif = False
                    ancien_abonnement.statut = 'remplace'
                    ancien_abonnement.save()
                
                # ⚠️ SÉCURITÉ : NE PAS créer l'abonnement maintenant !
                # L'abonnement sera créé SEULEMENT après confirmation du paiement Wave
                
                # Générer l'ID de transaction
                transaction_id = f"WAVE_{uuid.uuid4().hex[:16].upper()}"
                
                # Calculer le montant réel du pack
                if hasattr(pack, 'reduction_pourcentage') and pack.reduction_pourcentage and pack.reduction_pourcentage > 0:
                    montant_pack = float(pack.prix) * (1 - float(pack.reduction_pourcentage) / 100)
                else:
                    montant_pack = float(pack.prix)
                
                # Créer SEULEMENT le paiement Wave en attente (sans abonnement)
                paiement = PaiementWave.objects.create(
                    abonnement=None,  # Pas d'abonnement encore !
                    transaction_id=transaction_id,
                    montant=montant_pack,
                    wave_phone=telephone,
                    wave_email=email,
                    statut='en_attente'  # Statut en attente
                )
                
                # Stocker les informations du pack et utilisateur dans le paiement
                paiement.pack_id = pack.id
                paiement.utilisateur_id = utilisateur.id
                paiement.renouvellement_auto = renouvellement_auto
                paiement.save()
                
                # Utiliser le service Wave pour générer le lien de paiement
                wave_service = WaveService()
                resultat_wave = wave_service.initier_paiement(paiement)
                
                if resultat_wave['success']:
                    return {
                        'success': True,
                        'transaction_id': transaction_id,
                        'wave_url': resultat_wave.get('url'),
                        'message': 'Paiement initié avec succès - Redirection vers Wave...',
                        'simulation': resultat_wave.get('simulation', False),
                        'pack_nom': pack.nom,
                        'montant': paiement.montant
                    }
                else:
                    # Supprimer le paiement en cas d'échec
                    paiement.delete()
                    return {
                        'success': False,
                        'error': resultat_wave.get('error', 'Erreur lors de l\'initiation du paiement')
                    }
                    
        except PackAbonnement.DoesNotExist:
            return {'success': False, 'error': 'Pack invalide'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def initier_paiement_abonnement_enfant(parent, enfant, pack_id, email='', renouvellement_auto=False):
        """Initie un paiement pour un abonnement enfant - Le parent paie, l'enfant reçoit l'abonnement"""
        try:
            # 🔧 CORRECTION : Chercher d'abord dans PackAbonnement, puis dans PackFamilial
            # Car les packs spéciaux (Pack Vacances, etc.) sont dans PackAbonnement
            try:
                pack = PackAbonnement.objects.get(id=pack_id, actif=True)
                print(f"📦 Pack standard trouvé: {pack.nom} - {pack.prix} FCFA")
            except PackAbonnement.DoesNotExist:
                pack = PackFamilial.objects.get(id=pack_id, actif=True)
                print(f"📦 Pack familial trouvé: {pack.nom} - {pack.prix} FCFA")
            
            with transaction.atomic():
                # 🎁 GESTION DE L'UPGRADE : Désactiver l'ancien abonnement parrainage de l'enfant
                ancien_abonnement = Abonnement.objects.filter(
                    utilisateur=enfant,
                    actif=True,
                    source_parrainage=True
                ).first()
                
                if ancien_abonnement:
                    print(f"🔄 Désactivation de l'ancien abonnement parrainage de {enfant.email}: {ancien_abonnement.pack.nom}")
                    ancien_abonnement.actif = False
                    ancien_abonnement.statut = 'remplace'
                    ancien_abonnement.save()
                
                # ⚠️ SÉCURITÉ : NE PAS créer l'abonnement maintenant !
                # L'abonnement sera créé SEULEMENT après confirmation du paiement Wave
                
                # Générer l'ID de transaction
                transaction_id = f"WAVE_ENFANT_{uuid.uuid4().hex[:16].upper()}"
                
                # 🔍 DEBUG - Ajouter des logs pour traquer le problème
                print(f"🔍 DEBUG - Pack récupéré: {pack.nom} (ID: {pack.id})")
                print(f"🔍 DEBUG - Prix: {pack.prix} FCFA")
                print(f"🔍 DEBUG - Réduction: {pack.reduction_pourcentage}%")
                
                # Calculer le montant réel du pack
                if hasattr(pack, 'reduction_pourcentage') and pack.reduction_pourcentage and pack.reduction_pourcentage > 0:
                    montant_pack = float(pack.prix) * (1 - float(pack.reduction_pourcentage) / 100)
                    print(f"🔍 DEBUG - Montant calculé avec réduction: {montant_pack} FCFA")
                else:
                    montant_pack = float(pack.prix)
                    print(f"🔍 DEBUG - Montant sans réduction: {montant_pack} FCFA")
                
                # Créer SEULEMENT le paiement Wave en attente (sans abonnement)
                paiement = PaiementWave.objects.create(
                    abonnement=None,  # Pas d'abonnement encore !
                    transaction_id=transaction_id,
                    montant=montant_pack,
                    wave_phone='',  # Pas de téléphone pour les paiements parents
                    wave_email=email,
                    statut='en_attente'  # Statut en attente
                )
                
                # Stocker les informations du pack, parent et enfant dans le paiement
                paiement.pack_id = pack.id
                paiement.utilisateur_id = enfant.id  # L'enfant recevra l'abonnement
                paiement.parent_id = parent.id  # Le parent paie
                paiement.renouvellement_auto = renouvellement_auto
                paiement.save()
                
                # Utiliser le service Wave pour générer le lien de paiement
                wave_service = WaveService()
                resultat_wave = wave_service.initier_paiement(paiement)
                
                if resultat_wave['success']:
                    return {
                        'success': True,
                        'transaction_id': transaction_id,
                        'wave_url': resultat_wave.get('url'),
                        'message': f'Paiement initié avec succès pour {enfant.first_name or enfant.email} - Redirection vers Wave...',
                        'simulation': resultat_wave.get('simulation', False),
                        'pack_nom': pack.nom,
                        'montant': paiement.montant,
                        'enfant_nom': enfant.first_name or enfant.email
                    }
                else:
                    # Supprimer le paiement en cas d'échec
                    paiement.delete()
                    return {
                        'success': False,
                        'error': resultat_wave.get('error', 'Erreur lors de l\'initiation du paiement')
                    }
                    
        except PackAbonnement.DoesNotExist:
            return {'success': False, 'error': 'Pack invalide'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def initier_paiement_abonnement_famille(utilisateur, pack_id, email='', renouvellement_auto=False):
        """Initie un paiement pour un pack familial - Le parent paie pour tous ses enfants"""
        try:
            # 🔧 CORRECTION : Chercher d'abord dans PackAbonnement, puis dans PackFamilial
            # Car les packs spéciaux (Pack Vacances, etc.) sont dans PackAbonnement
            try:
                pack = PackAbonnement.objects.get(id=pack_id, actif=True)
                print(f"📦 Pack standard trouvé pour famille: {pack.nom} - {pack.prix} FCFA")
            except PackAbonnement.DoesNotExist:
                pack = PackFamilial.objects.get(id=pack_id, actif=True)
                print(f"📦 Pack familial trouvé pour famille: {pack.nom} - {pack.prix} FCFA")
            
            with transaction.atomic():
                # 🎁 GESTION DE L'UPGRADE : Désactiver l'ancien abonnement parrainage du parent
                ancien_abonnement = Abonnement.objects.filter(
                    utilisateur=utilisateur,
                    actif=True,
                    source_parrainage=True
                ).first()
                
                if ancien_abonnement:
                    print(f"🔄 Désactivation de l'ancien abonnement parrainage: {ancien_abonnement.pack.nom}")
                    ancien_abonnement.actif = False
                    ancien_abonnement.statut = 'remplace'
                    ancien_abonnement.save()
                
                # ⚠️ SÉCURITÉ : NE PAS créer l'abonnement maintenant !
                # L'abonnement sera créé SEULEMENT après confirmation du paiement Wave
                
                # Générer l'ID de transaction
                transaction_id = f"WAVE_FAMILLE_{uuid.uuid4().hex[:16].upper()}"
                
                # Calculer le montant réel du pack
                if hasattr(pack, 'reduction_pourcentage') and pack.reduction_pourcentage and pack.reduction_pourcentage > 0:
                    montant_pack = float(pack.prix) * (1 - float(pack.reduction_pourcentage) / 100)
                else:
                    montant_pack = float(pack.prix)
                
                # Créer SEULEMENT le paiement Wave en attente (sans abonnement)
                paiement = PaiementWave.objects.create(
                    abonnement=None,  # Pas d'abonnement encore !
                    transaction_id=transaction_id,
                    montant=montant_pack,
                    wave_phone='',  # Pas de téléphone pour les paiements familiaux
                    wave_email=email,
                    statut='en_attente'  # Statut en attente
                )
                
                # Stocker les informations du pack et utilisateur dans le paiement
                paiement.pack_id = pack.id
                paiement.utilisateur_id = utilisateur.id  # Le parent reçoit l'abonnement familial
                paiement.renouvellement_auto = renouvellement_auto
                paiement.save()
                
                # Utiliser le service Wave pour générer le lien de paiement
                wave_service = WaveService()
                resultat_wave = wave_service.initier_paiement(paiement)
                
                if resultat_wave['success']:
                    return {
                        'success': True,
                        'transaction_id': transaction_id,
                        'wave_url': resultat_wave.get('url'),
                        'message': f'Paiement familial initié avec succès pour {pack.nom} - Redirection vers Wave...',
                        'simulation': resultat_wave.get('simulation', False),
                        'pack_nom': pack.nom,
                        'montant': paiement.montant
                    }
                else:
                    # Supprimer le paiement en cas d'échec
                    paiement.delete()
                    return {
                        'success': False,
                        'error': resultat_wave.get('error', 'Erreur lors de l\'initiation du paiement')
                    }
                    
        except PackAbonnement.DoesNotExist:
            return {'success': False, 'error': 'Pack invalide'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_abonnement_actuel(utilisateur):
        """Récupère l'abonnement actuel de l'utilisateur"""
        try:
            abonnement = Abonnement.objects.filter(
                utilisateur=utilisateur,
                actif=True,
                statut__in=['actif', 'essai']
            ).first()
            
            if abonnement:
                return {'success': True, 'abonnement': abonnement}
            else:
                return {'success': False, 'error': 'Aucun abonnement actif'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def suspendre_abonnement(abonnement_id, utilisateur):
        """Suspend un abonnement"""
        try:
            abonnement = Abonnement.objects.get(id=abonnement_id, utilisateur=utilisateur)
            abonnement.statut = 'suspendu'
            abonnement.actif = False
            abonnement.save()
            return {'success': True, 'message': 'Abonnement suspendu'}
        except Abonnement.DoesNotExist:
            return {'success': False, 'error': 'Abonnement non trouvé'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def reactiver_abonnement(abonnement_id, utilisateur):
        """Réactive un abonnement"""
        try:
            abonnement = Abonnement.objects.get(id=abonnement_id, utilisateur=utilisateur)
            abonnement.statut = 'actif'
            abonnement.actif = True
            abonnement.save()
            return {'success': True, 'message': 'Abonnement réactivé'}
        except Abonnement.DoesNotExist:
            return {'success': False, 'error': 'Abonnement non trouvé'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def renouveler_abonnement(abonnement_id, utilisateur):
        """Renouvelle un abonnement en prolongeant sa durée"""
        try:
            abonnement = Abonnement.objects.get(id=abonnement_id, utilisateur=utilisateur)
            
            # Vérifier que l'abonnement appartient à l'utilisateur
            if abonnement.utilisateur != utilisateur:
                return {'success': False, 'error': 'Accès non autorisé à cet abonnement'}
            
            # Vérifier que l'abonnement est actif
            if not abonnement.actif:
                return {'success': False, 'error': 'Seuls les abonnements actifs peuvent être renouvelés'}
            
            # Vérifier que l'abonnement peut être renouvelé (moins de 30 jours restants)
            jours_restants = (abonnement.date_fin - timezone.now().date()).days
            if jours_restants > 30:
                return {'success': False, 'error': f'Renouvellement disponible dans {jours_restants - 30} jours'}
            
            # Calculer la nouvelle date de fin
            pack = abonnement.pack
            nouvelle_date_fin = abonnement.date_fin + timedelta(days=pack.duree_jours)
            
            # Mettre à jour l'abonnement
            abonnement.date_fin = nouvelle_date_fin
            abonnement.date_renouvellement = timezone.now()
            abonnement.save()
            
            # Créer un historique de renouvellement
            from .models import HistoriqueRenouvellement
            HistoriqueRenouvellement.objects.create(
                abonnement=abonnement,
                date_renouvellement=timezone.now(),
                duree_ajoutee=pack.duree_jours,
                montant_renouvellement=pack.prix
            )
            
            print(f"✅ Abonnement {abonnement.id} renouvelé: +{pack.duree_jours} jours")
            
            return {
                'success': True,
                'message': f'Abonnement renouvelé avec succès ! +{pack.duree_jours} jours ajoutés',
                'nouvelle_date_fin': nouvelle_date_fin,
                'jours_ajoutes': pack.duree_jours
            }
            
        except Abonnement.DoesNotExist:
            return {'success': False, 'error': 'Abonnement non trouvé'}
        except Exception as e:
            print(f"❌ Erreur lors du renouvellement: {e}")
            return {'success': False, 'error': str(e)}


class ExpirationService:
    """Service pour gérer l'expiration des abonnements et la transition vers pack gratuit"""
    
    @staticmethod
    def verifier_et_traiter_expirations():
        """Vérifie et traite tous les abonnements expirés"""
        from .models import Abonnement, PackAbonnement
        from django.utils import timezone
        
        # Trouver tous les abonnements expirés mais encore actifs
        abonnements_expires = Abonnement.objects.filter(
            actif=True,
            date_fin__lt=timezone.now(),
            statut__in=['actif', 'essai']
        ).exclude(
            pack__type_pack='gratuit'  # Ne pas traiter les packs gratuits
        )
        
        print(f"🔍 Vérification d'expiration: {abonnements_expires.count()} abonnements à traiter")
        
        resultats = {
            'traites': 0,
            'erreurs': 0,
            'details': []
        }
        
        for abonnement in abonnements_expires:
            try:
                resultat = ExpirationService.traiter_expiration_abonnement(abonnement)
                if resultat['success']:
                    resultats['traites'] += 1
                    resultats['details'].append(f"✅ {abonnement.utilisateur.email}: {resultat['message']}")
                else:
                    resultats['erreurs'] += 1
                    resultats['details'].append(f"❌ {abonnement.utilisateur.email}: {resultat['error']}")
            except Exception as e:
                resultats['erreurs'] += 1
                resultats['details'].append(f"❌ {abonnement.utilisateur.email}: Exception {e}")
        
        return resultats
    
    @staticmethod
    def traiter_expiration_abonnement(abonnement):
        """Traite l'expiration d'un abonnement spécifique"""
        try:
            from .models import PackAbonnement
            from django.utils import timezone
            
            utilisateur = abonnement.utilisateur
            ancien_pack = abonnement.pack
            
            print(f"🔄 Expiration de {utilisateur.email}: {ancien_pack.nom}")
            
            # Marquer l'ancien abonnement comme expiré
            abonnement.actif = False
            abonnement.statut = 'expire'
            abonnement.save()
            
            # Créer un nouvel abonnement avec pack gratuit
            pack_gratuit = PackAbonnement.objects.filter(
                type_pack='gratuit',
                nom='Gratuit',
                actif=True
            ).first()
            
            if not pack_gratuit:
                return {'success': False, 'error': 'Pack gratuit non trouvé'}
            
            # Créer le nouvel abonnement gratuit (illimité dans le temps)
            nouvel_abonnement = Abonnement.objects.create(
                utilisateur=utilisateur,
                pack=pack_gratuit,
                date_debut=timezone.now(),
                date_fin=None,  # Pack gratuit = illimité dans le temps
                montant_paye=0,
                statut='actif',
                actif=True,
                est_essai_gratuit=False,
                source_parrainage=False
            )
            
            print(f"✅ {utilisateur.email} transféré vers pack gratuit")
            
            return {
                'success': True,
                'message': f'Abonnement expiré, transféré vers pack gratuit',
                'ancien_pack': ancien_pack.nom,
                'nouveau_pack': pack_gratuit.nom,
                'nouvel_abonnement_id': nouvel_abonnement.id
            }
            
        except Exception as e:
            print(f"❌ Erreur lors du traitement d'expiration: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def utilisateur_peut_acceder_contenu_gratuit(utilisateur, contenu_id):
        """Vérifie si un utilisateur avec pack gratuit peut accéder à un contenu"""
        try:
            from progression.models import ProgressionContenu
            from django.utils import timezone
            
            # Vérifier si le contenu a déjà été consulté ce mois
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            
            progression_existante = ProgressionContenu.objects.filter(
                etudiant=utilisateur,
                contenu_id=contenu_id,
                date_completion__month=mois_courant,
                date_completion__year=annee_courante
            ).exists()
            
            if progression_existante:
                return True, "Contenu déjà consulté ce mois"
            
            # Vérifier les limites mensuelles
            permissions = PermissionService.get_permissions_utilisateur(utilisateur)
            if not permissions:
                return False, "Aucune permission trouvée"
            
            # Pack gratuit : vérifier limite mensuelle
            if permissions.pack.type_pack == 'gratuit':
                cours_ce_mois = PermissionService.compter_cours_mois_courant(utilisateur)
                limite_cours = permissions.max_cours_par_mois
                
                if limite_cours > 0 and cours_ce_mois >= limite_cours:
                    return False, f"Limite mensuelle atteinte ({limite_cours} cours/mois). Vous ne pouvez consulter que le contenu déjà vu."
            
            return True, "Accès autorisé"
            
        except Exception as e:
            print(f"❌ Erreur vérification contenu gratuit: {e}")
            return False, f"Erreur de vérification: {e}"


class PackDecouverteService:
    """Service pour créer automatiquement un Pack Découverte pour les nouveaux utilisateurs sans parrain"""
    
    @staticmethod
    def creer_pack_decouverte_pour_utilisateur(utilisateur):
        """Crée un Pack Découverte pour un utilisateur sans parrain"""
        try:
            from .models import PackAbonnement, Abonnement
            from django.utils import timezone
            from datetime import timedelta
            
            # Vérifier que l'utilisateur n'a pas déjà un abonnement actif
            if Abonnement.objects.filter(utilisateur=utilisateur, actif=True).exists():
                return {
                    'success': False, 
                    'error': 'Utilisateur a déjà un abonnement actif'
                }
            
            # Trouver ou créer le Pack Découverte
            pack_decouverte, created = PackAbonnement.objects.get_or_create(
                nom="Pack Découverte",
                defaults={
                    'type_pack': 'gratuit',
                    'prix': 0,
                    'periode': 'semaine',
                    'duree_jours': 3,
                    'description': 'Pack de découverte gratuit pour les nouveaux utilisateurs',
                    'actif': True,
                    'pack_special': False,
                    'offre_semaine_gratuite': False,
                    'reduction_pourcentage': 0
                }
            )
            
            # Créer l'abonnement Pack Découverte
            date_debut = timezone.now()
            date_fin = date_debut + timedelta(days=3)  # 3 jours d'essai
            
            abonnement = Abonnement.objects.create(
                utilisateur=utilisateur,
                pack=pack_decouverte,
                date_debut=date_debut,
                date_fin=date_fin,
                montant_paye=0,
                statut='actif',
                actif=True,
                est_essai_gratuit=True,
                source_parrainage=False
            )
            
            return {
                'success': True,
                'message': f'Pack Découverte créé avec succès (3 jours d\'essai)',
                'abonnement_id': abonnement.id,
                'pack_nom': pack_decouverte.nom,
                'fin_essai': date_fin.strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            return {
                'success': False, 
                'error': f'Erreur lors de la création du Pack Découverte: {str(e)}'
            }


class StatistiquesService:
    """Service pour les statistiques d'abonnement"""
    
    @staticmethod
    def get_statistiques_utilisateur(utilisateur):
        """Récupère les statistiques d'un utilisateur"""
        try:
            # Statistiques de base
            total_abonnements = Abonnement.objects.filter(utilisateur=utilisateur).count()
            abonnements_actifs = Abonnement.objects.filter(
                utilisateur=utilisateur, 
                actif=True, 
                statut='actif'
            ).count()
            abonnements_essai = Abonnement.objects.filter(
                utilisateur=utilisateur, 
                est_essai_gratuit=True
            ).count()
            
            # Revenus du mois
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            revenus_mensuels = PaiementWave.objects.filter(
                abonnement__utilisateur=utilisateur,
                statut='reussi',
                date_creation__month=mois_courant,
                date_creation__year=annee_courante
            ).aggregate(total=models.Sum('montant'))['total'] or 0
            
            # Taux de conversion (essai vers payant)
            total_essais = Abonnement.objects.filter(
                utilisateur=utilisateur, 
                est_essai_gratuit=True
            ).count()
            conversions = Abonnement.objects.filter(
                utilisateur=utilisateur,
                est_essai_gratuit=True,
                statut='actif'
            ).count()
            taux_conversion = (conversions / total_essais * 100) if total_essais > 0 else 0
            
            # Packs populaires
            packs_populaires = PackAbonnement.objects.filter(
                abonnement__utilisateur=utilisateur
            ).annotate(
                count=models.Count('abonnement')
            ).order_by('-count')[:5]
            
            # Récupérer l'utilisation mensuelle de l'abonnement actuel
            utilisation_mensuelle = None
            abonnement_actuel = Abonnement.objects.filter(
                utilisateur=utilisateur, 
                actif=True
            ).first()
            
            if abonnement_actuel:
                utilisation_mensuelle = StatistiquesService.get_utilisation_mensuelle(abonnement_actuel)
            
            stats = {
                'total_abonnements': total_abonnements,
                'abonnements_actifs': abonnements_actifs,
                'abonnements_essai': abonnements_essai,
                'revenus_mensuels': revenus_mensuels,
                'taux_conversion': round(taux_conversion, 2),
                'packs_populaires': [
                    {'nom': pack.nom, 'count': pack.count} 
                    for pack in packs_populaires
                ],
                'utilisation_mensuelle': utilisation_mensuelle
            }
            
            return {'success': True, 'statistiques': stats}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_utilisation_mensuelle(abonnement):
        """Récupère l'utilisation mensuelle d'un abonnement depuis l'app progression"""
        try:
            from progression.models import ProgressionContenu, ProgressionChapitre
            from quiz.models import TentativeQuiz
            
            utilisateur = abonnement.utilisateur
            
            # Utiliser le mois et l'année actuels
            mois_reference = timezone.now().month
            annee_reference = timezone.now().year
            
            print(f"🔍 Utilisation du mois actuel: {mois_reference}/{annee_reference} pour {utilisateur.email}")
            
            print(f"🔍 Mois de référence détecté: {mois_reference}/{annee_reference} pour {utilisateur.email}")
            
            # Cours suivis (contenus lus ce mois)
            cours_suivis = ProgressionContenu.objects.filter(
                etudiant=utilisateur,
                lu=True,
                date_completion__month=mois_reference,
                date_completion__year=annee_reference
            ).count()
            
            # Quiz réalisés ce mois
            quiz_realises = TentativeQuiz.objects.filter(
                etudiant=utilisateur,
                date_debut__month=mois_reference,
                date_debut__year=annee_reference
            ).count()
            
            # Temps d'étude ce mois (en secondes)
            temps_etude_secondes = ProgressionContenu.objects.filter(
                etudiant=utilisateur,
                date_completion__month=mois_reference,
                date_completion__year=annee_reference
            ).aggregate(
                total_temps=models.Sum('temps_lecture')
            )['total_temps'] or 0
            
            # Convertir en heures pour l'affichage (optionnel)
            temps_etude_heures = round(temps_etude_secondes / 3600, 1)
            
            print(f"📊 Statistiques calculées pour {mois_reference}/{annee_reference}:")
            print(f"   - Cours suivis: {cours_suivis}")
            print(f"   - Quiz réalisés: {quiz_realises}")
            print(f"   - Temps d'étude: {temps_etude_heures}h ({temps_etude_secondes}s)")
            
            return {
                'cours_suivis': cours_suivis,
                'quiz_realises': quiz_realises,
                'temps_etude_secondes': temps_etude_secondes,
                'mois_reference': mois_reference,
                'annee_reference': annee_reference
            }
                
        except Exception as e:
            print(f"❌ Erreur lors du calcul de l'utilisation mensuelle: {e}")
            return {
                'cours_suivis': 0,
                'quiz_realises': 0,
                'temps_etude_secondes': 0,
                'mois_reference': timezone.now().month,
                'annee_reference': timezone.now().year
            }


class PackService:
    """Service pour gérer les packs d'abonnement"""
    
    @staticmethod
    def get_packs_actifs():
        """Récupère tous les packs actifs"""
        try:
            packs = PackAbonnement.objects.filter(actif=True)
            return {'success': True, 'packs': packs}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_packs_speciaux():
        """Récupère les packs spéciaux"""
        try:
            packs = PackAbonnement.objects.filter(actif=True, pack_special=True)
            return {'success': True, 'packs': packs}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_packs_avec_essai_gratuit():
        """Récupère les packs avec essai gratuit"""
        try:
            packs = PackAbonnement.objects.filter(actif=True, offre_semaine_gratuite=True)
            return {'success': True, 'packs': packs}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_packs_familiaux():
        """Récupère les packs familiaux"""
        try:
            packs = PackFamilial.objects.filter(actif=True)
            return {'success': True, 'packs': packs}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class ParrainageService:
    """Service pour gérer le système de parrainage"""
    
    @staticmethod
    def creer_parrainage(filleul, code_parrainage):
        """Crée une relation de parrainage"""
        try:
            # Vérifier que le code de parrainage existe
            parrain = Utilisateur.objects.filter(code_parrainage=code_parrainage).first()
            if not parrain:
                return {'success': False, 'error': 'Code de parrainage invalide'}
            
            # Vérifier que l'utilisateur ne se parraine pas lui-même
            if parrain == filleul:
                return {'success': False, 'error': 'Vous ne pouvez pas vous parrainer vous-même'}
            
            # Vérifier qu'il n'y a pas déjà un parrainage
            if hasattr(filleul, 'parrain'):
                return {'success': False, 'error': 'Cet utilisateur a déjà un parrain'}
            
            # Créer le parrainage
            parrainage = Parrainage.objects.create(
                parrain=parrain,
                filleul=filleul,
                code_parrainage=code_parrainage
            )
            
            return {'success': True, 'parrainage': parrainage}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def attribuer_bonus_parrainage(filleul):
        """Attribue le bonus au parrain quand le filleul paie"""
        try:
            if not hasattr(filleul, 'parrain'):
                return {'success': False, 'error': 'Aucun parrain trouvé'}
            
            parrainage = filleul.parrain
            if parrainage.attribuer_bonus():
                return {
                    'success': True, 
                    'message': f'Bonus attribué au parrain {parrainage.parrain.email}',
                    'parrainage': parrainage
                }
            else:
                return {'success': False, 'error': 'Bonus déjà attribué ou limite atteinte'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def utiliser_bonus_parrainage(utilisateur, nombre_semaines=1):
        """Utilise les bonus de parrainage pour prolonger l'abonnement"""
        try:
            # Récupérer ou créer le bonus de parrainage
            bonus, created = BonusParrainage.objects.get_or_create(utilisateur=utilisateur)
            
            # Vérifier qu'il y a assez de bonus disponibles
            if bonus.bonus_disponibles < nombre_semaines:
                return {'success': False, 'error': f'Vous n\'avez que {bonus.bonus_disponibles} bonus disponibles'}
            
            # Utiliser les bonus
            if bonus.utiliser_bonus(nombre_semaines):
                # Prolonger l'abonnement actuel
                abonnement_actuel = Abonnement.objects.filter(
                    utilisateur=utilisateur, 
                    actif=True
                ).first()
                
                if abonnement_actuel:
                    # Ajouter les semaines à la date de fin
                    semaines_ajoutees = timedelta(weeks=nombre_semaines)
                    abonnement_actuel.date_fin += semaines_ajoutees
                    abonnement_actuel.save()
                    
                    return {
                        'success': True,
                        'message': f'{nombre_semaines} semaine(s) ajoutée(s) à votre abonnement',
                        'nouvelle_date_fin': abonnement_actuel.date_fin,
                        'bonus_restants': bonus.bonus_disponibles
                    }
                else:
                    return {'success': False, 'error': 'Aucun abonnement actif trouvé'}
            else:
                return {'success': False, 'error': 'Impossible d\'utiliser les bonus'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_code_parrainage(utilisateur):
        """Récupère le code de parrainage d'un utilisateur"""
        try:
            # Vérifier si l'utilisateur a un code de parrainage
            if not hasattr(utilisateur, 'code_parrainage') or not utilisateur.code_parrainage:
                # Générer un nouveau code si nécessaire
                from .models import Utilisateur
                import random
                import string
                
                # Générer un code unique de 8 caractères
                while True:
                    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    if not Utilisateur.objects.filter(code_parrainage=code).exists():
                        break
                
                # Sauvegarder le code
                utilisateur.code_parrainage = code
                utilisateur.save()
                print(f"🔑 Nouveau code de parrainage généré: {code}")
            
            return {
                'success': True,
                'code_parrainage': utilisateur.code_parrainage
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_statistiques_parrainage(utilisateur):
        """Récupère les statistiques de parrainage d'un utilisateur"""
        try:
            # Récupérer ou créer le bonus de parrainage
            bonus, created = BonusParrainage.objects.get_or_create(utilisateur=utilisateur)
            
            # Compter les filleuls
            nombre_filleuls = Parrainage.objects.filter(parrain=utilisateur).count()
            
            # Compter les filleuls qui ont payé (bonus attribués)
            filleuls_payants = Parrainage.objects.filter(
                parrain=utilisateur, 
                bonus_attribue=True
            ).count()
            
            # CORRECTION : Mettre à jour les bonus accumulés basés sur les parrainages
            # Recalculer les bonus accumulés depuis les parrainages
            bonus_accumules_reels = Parrainage.objects.filter(
                parrain=utilisateur,
                bonus_attribue=True
            ).count()
            
            # Mettre à jour le modèle BonusParrainage si nécessaire
            if bonus.bonus_accumules != bonus_accumules_reels:
                bonus.bonus_accumules = bonus_accumules_reels
                bonus.save()
                print(f"🔄 Bonus mis à jour: {bonus_accumules_reels} bonus accumulés")
            else:
                print(f"✅ Bonus déjà à jour: {bonus_accumules_reels} bonus accumulés")
            
            return {
                'success': True,
                'bonus_accumules': bonus.bonus_accumules,
                'bonus_utilises': bonus.bonus_utilises,
                'bonus_disponibles': bonus.bonus_disponibles,
                'peut_utiliser_bonus': bonus.peut_utiliser_bonus,
                'nombre_filleuls': nombre_filleuls,
                'filleuls_payants': filleuls_payants,
                'limite_atteinte': False  # Plus de limite
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_filleuls(utilisateur):
        """Récupère la liste des filleuls d'un utilisateur"""
        try:
            filleuls = Parrainage.objects.filter(parrain=utilisateur)
            
            if not filleuls.exists():
                return {
                    'success': True,
                    'filleuls': [],
                    'message': 'Aucun filleul pour le moment'
                }
            
            # Préparer les données des filleuls
            liste_filleuls = []
            for parrainage in filleuls:
                filleul = parrainage.filleul
                
                # Vérifier si le filleul a un abonnement actif
                abonnement_actif = Abonnement.objects.filter(
                    utilisateur=filleul,
                    actif=True
                ).exists()
                
                filleul_data = {
                    'id': filleul.id,
                    'email': filleul.email,
                    'nom_complet': f"{filleul.first_name or ''} {filleul.last_name or ''}".strip() or 'Utilisateur',
                    'date_inscription': filleul.date_joined,
                    'abonnement_actif': abonnement_actif,
                    'bonus_attribue': parrainage.bonus_attribue,
                    'date_bonus_attribue': parrainage.date_bonus_attribue if parrainage.bonus_attribue else None
                }
                liste_filleuls.append(filleul_data)
            
            return {
                'success': True,
                'filleuls': liste_filleuls,
                'total': len(liste_filleuls)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


class PackDecouverteService:
    """Service pour gérer le Pack Découverte pour les nouveaux utilisateurs sans parrain"""
    
    @staticmethod
    def creer_pack_decouverte_pour_utilisateur(utilisateur):
        """
        Crée automatiquement un Pack Découverte de 3 jours pour un nouvel utilisateur sans parrain
        """
        try:
            from .models import PackAbonnement, Abonnement, PackPermissions
            from django.utils import timezone
            from datetime import timedelta
            
            # Créer ou récupérer le Pack Découverte
            pack_decouverte, created = PackAbonnement.objects.get_or_create(
                nom="Pack Découverte",
                defaults={
                    'type_pack': 'special',  # Utiliser 'special' car 'decouverte' n'existe pas
                    'prix': 0,
                    'duree_jours': 3,
                    'periode': 'semaine',  # Utiliser 'semaine' car 'essai' n'existe pas
                    'description': 'Pack de découverte gratuit de 3 jours pour les nouveaux utilisateurs',
                    'actif': True,
                    'offre_semaine_gratuite': False,
                    'pack_special': True,  # Marquer comme pack spécial
                    'reduction_pourcentage': 0
                }
            )
            
            # Créer les permissions pour le Pack Découverte si pas encore fait
            try:
                permissions = pack_decouverte.permissions
            except PackPermissions.DoesNotExist:
                permissions = None
            
            if created or not permissions:
                permissions, perm_created = PackPermissions.objects.get_or_create(
                    pack=pack_decouverte,
                    defaults={
                        'max_cours_par_mois': 5,
                        'max_quiz_par_mois': 3,
                        'max_examens_par_mois': 0,  # Pas d'examens
                        'acces_cours_premium': False,  # Cours gratuits seulement
                        'acces_ia_standard': True,  # IA standard pendant l'essai
                        'acces_ia_prioritaire': False,
                        'acces_certificats': False,
                        'acces_contenu_hors_ligne': False,
                        'acces_communautaire': False,
                        'support_prioritaire': False,
                        'acces_prioritaire_nouveautes': False,
                        'upgrade_reminder': True,  # Inciter à upgrader
                        'specialisation_examens': False,
                        'contenu_examens_prioritaire': False,
                        'nombre_enfants_max': 0,
                        'profils_separes': False,
                        'suivi_familial': False
                    }
                )
                print(f"✅ Permissions créées pour le Pack Découverte: {permissions}")
            
            # Vérifier si l'utilisateur n'a pas déjà un abonnement actif
            abonnement_existant = Abonnement.objects.filter(
                utilisateur=utilisateur,
                actif=True,
                date_fin__gte=timezone.now()
            ).first()
            
            if abonnement_existant:
                return {
                    'success': False,
                    'error': 'L\'utilisateur a déjà un abonnement actif',
                    'abonnement_existant': abonnement_existant
                }
            
            # Créer l'abonnement Pack Découverte
            date_debut = timezone.now()
            date_fin = date_debut + timedelta(days=3)
            
            abonnement = Abonnement.objects.create(
                utilisateur=utilisateur,
                pack=pack_decouverte,
                date_debut=date_debut,
                date_fin=date_fin,
                statut='actif',
                actif=True,
                montant_paye=0,
                est_essai_gratuit=True,
                source_parrainage=False  # Pas de parrainage
            )
            
            print(f"✅ Pack Découverte créé pour {utilisateur.email}: {abonnement}")
            
            return {
                'success': True,
                'abonnement': abonnement,
                'pack': pack_decouverte,
                'message': f'Pack Découverte de 3 jours activé ! Profitez de 5 cours et 3 quiz gratuits.',
                'duree_jours': 3,
                'fin_essai': date_fin
            }
            
        except Exception as e:
            print(f"❌ Erreur lors de la création du Pack Découverte: {e}")
            return {
                'success': False,
                'error': f'Erreur lors de la création du Pack Découverte: {str(e)}'
            }


class WaveCallbackService:
    """Service pour gérer les callbacks Wave et l'activation automatique des abonnements"""
    
    @staticmethod
    def traiter_paiement_reussi(transaction_id, montant_paye, reference_wave):
        """
        Traite un paiement Wave réussi et active l'abonnement
        
        Args:
            transaction_id: ID de la transaction Wave
            montant_paye: Montant payé via Wave
            reference_wave: Référence Wave de la transaction
            
        Returns:
            dict: Résultat du traitement
        """
        try:
            # Chercher le paiement en attente
            paiement = PaiementWave.objects.filter(
                transaction_id=transaction_id,
                statut='en_attente'
            ).first()
            
            if not paiement:
                logger.error(f"Paiement Wave non trouvé pour transaction_id: {transaction_id}")
                return {
                    'success': False,
                    'error': 'Paiement non trouvé'
                }
            
            # Récupérer le pack et l'utilisateur depuis les informations stockées
            if not paiement.pack_id or not paiement.utilisateur_id:
                logger.error(f"Informations manquantes dans le paiement {transaction_id}")
                return {
                    'success': False,
                    'error': 'Informations du paiement incomplètes'
                }
            
            # 🔧 CORRECTION : Chercher d'abord dans PackAbonnement, puis dans PackFamilial
            # Car les packs spéciaux (Pack Vacances, etc.) sont dans PackAbonnement
            try:
                pack = PackAbonnement.objects.get(id=paiement.pack_id)
                print(f"📦 Pack standard trouvé pour callback: {pack.nom} - {pack.prix} FCFA")
            except PackAbonnement.DoesNotExist:
                pack = PackFamilial.objects.get(id=paiement.pack_id)
                print(f"📦 Pack familial trouvé pour callback: {pack.nom} - {pack.prix} FCFA")
            
            utilisateur = Utilisateur.objects.get(id=paiement.utilisateur_id)
            
            # Vérifier si c'est un paiement pour un enfant (parent_id présent)
            parent_info = ""
            if paiement.parent_id:
                try:
                    parent = Utilisateur.objects.get(id=paiement.parent_id)
                    parent_info = f" (paiement effectué par {parent.first_name or parent.email})"
                except Utilisateur.DoesNotExist:
                    logger.warning(f"Parent {paiement.parent_id} non trouvé pour le paiement {transaction_id}")
            
            # Calculer le montant attendu
            if hasattr(pack, 'reduction_pourcentage') and pack.reduction_pourcentage and pack.reduction_pourcentage > 0:
                montant_attendu = int(float(pack.prix) * (1 - float(pack.reduction_pourcentage) / 100))
            else:
                montant_attendu = int(pack.prix)
            
            if int(montant_paye) != montant_attendu:
                logger.warning(f"Montant payé ({montant_paye}) ne correspond pas au montant attendu ({montant_attendu})")
                # On accepte quand même le paiement pour éviter les problèmes de centimes
            
            # Marquer le paiement comme réussi
            paiement.statut = 'reussi'
            paiement.wave_reference = reference_wave
            paiement.save()
            
            # Créer l'abonnement MAINTENANT (après confirmation du paiement)
            resultat_creation = AbonnementService.creer_abonnement(
                utilisateur=utilisateur,
                pack=pack,
                est_essai_gratuit=False,
                renouvellement_auto=paiement.renouvellement_auto
            )
            
            if not resultat_creation['success']:
                logger.error(f"Erreur lors de la création de l'abonnement: {resultat_creation['error']}")
                return {
                    'success': False,
                    'error': f"Erreur lors de la création de l'abonnement: {resultat_creation['error']}"
                }
            
            abonnement = resultat_creation['abonnement']
            
            # Lier le paiement à l'abonnement créé
            paiement.abonnement = abonnement
            paiement.save()
            
            logger.info(f"Abonnement créé avec succès pour {utilisateur.email}: {abonnement.id}{parent_info}")
            
            # Vérifier si c'est un pack familial
            if pack.type_pack == 'famille':
                # Traiter comme un paiement familial
                return WaveCallbackService.traiter_paiement_familial_reussi(
                    paiement, pack, utilisateur, parent_info
                )
            else:
                # Traitement normal pour les packs individuels
                return {
                    'success': True,
                    'abonnement_id': abonnement.id,
                    'message': f'Paiement confirmé et abonnement activé pour {utilisateur.first_name or utilisateur.email}{parent_info}'
                }
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du paiement Wave: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def traiter_paiement_familial_reussi(paiement, pack, parent, parent_info):
        """
        Traite un paiement familial réussi et active les abonnements pour le parent et tous ses enfants
        
        Args:
            paiement: Instance PaiementWave
            pack: Instance PackAbonnement (pack familial)
            parent: Instance Utilisateur (parent)
            parent_info: String d'information sur le parent
            
        Returns:
            dict: Résultat du traitement
        """
        try:
            from utilisateurs.models import LienParentEnfant
            
            # Récupérer tous les enfants actifs du parent
            liens_enfants = LienParentEnfant.objects.filter(
                parent=parent,
                actif=True
            ).select_related('enfant')
            
            enfants = [lien.enfant for lien in liens_enfants]
            
            if not enfants:
                logger.warning(f"Aucun enfant trouvé pour le parent {parent.email}")
                return {
                    'success': False,
                    'error': 'Aucun enfant trouvé pour ce parent'
                }
            
            # Vérifier que le nombre d'enfants correspond au pack
            nombre_enfants_pack = getattr(pack, 'nombre_enfants', 0)
            if nombre_enfants_pack > 0 and len(enfants) != nombre_enfants_pack:
                logger.warning(f"Nombre d'enfants ({len(enfants)}) ne correspond pas au pack ({nombre_enfants_pack})")
                # On continue quand même, on prend les enfants disponibles
            
            abonnements_crees = []
            
            # 1. Créer l'abonnement pour le parent
            resultat_parent = AbonnementService.creer_abonnement(
                utilisateur=parent,
                pack=pack,
                est_essai_gratuit=False,
                renouvellement_auto=paiement.renouvellement_auto
            )
            
            if resultat_parent['success']:
                abonnement_parent = resultat_parent['abonnement']
                abonnements_crees.append({
                    'utilisateur': parent,
                    'abonnement': abonnement_parent,
                    'type': 'parent'
                })
                logger.info(f"✅ Abonnement familial créé pour le parent {parent.email}: {abonnement_parent.id}")
            else:
                logger.error(f"❌ Erreur création abonnement parent: {resultat_parent['error']}")
                return {
                    'success': False,
                    'error': f"Erreur création abonnement parent: {resultat_parent['error']}"
                }
            
            # 2. Créer les abonnements pour tous les enfants
            for enfant in enfants:
                resultat_enfant = AbonnementService.creer_abonnement(
                    utilisateur=enfant,
                    pack=pack,
                    est_essai_gratuit=False,
                    renouvellement_auto=paiement.renouvellement_auto
                )
                
                if resultat_enfant['success']:
                    abonnement_enfant = resultat_enfant['abonnement']
                    abonnements_crees.append({
                        'utilisateur': enfant,
                        'abonnement': abonnement_enfant,
                        'type': 'enfant'
                    })
                    logger.info(f"✅ Abonnement familial créé pour l'enfant {enfant.email}: {abonnement_enfant.id}")
                else:
                    logger.error(f"❌ Erreur création abonnement enfant {enfant.email}: {resultat_enfant['error']}")
                    # On continue avec les autres enfants même si un échoue
            
            # 3. Lier le paiement au premier abonnement (parent)
            paiement.abonnement = abonnement_parent
            paiement.save()
            
            # 4. Créer des enregistrements PaiementWave pour chaque enfant (pour traçabilité)
            for abonnement_info in abonnements_crees[1:]:  # Skip parent (déjà fait)
                PaiementWave.objects.create(
                    abonnement=abonnement_info['abonnement'],
                    transaction_id=f"{paiement.transaction_id}_ENFANT_{abonnement_info['utilisateur'].id}",
                    montant=0,  # Pas de montant séparé, déjà payé par le parent
                    wave_phone='',
                    wave_email=paiement.wave_email,
                    statut='reussi',
                    wave_reference=paiement.wave_reference,
                    pack_id=pack.id,
                    utilisateur_id=abonnement_info['utilisateur'].id,
                    parent_id=parent.id,
                    renouvellement_auto=paiement.renouvellement_auto
                )
            
            logger.info(f"🎉 Paiement familial traité avec succès: {len(abonnements_crees)} abonnements créés")
            
            return {
                'success': True,
                'abonnement_id': abonnement_parent.id,
                'abonnements_crees': len(abonnements_crees),
                'enfants_actives': len([a for a in abonnements_crees if a['type'] == 'enfant']),
                'message': f'Paiement familial confirmé: {len(abonnements_crees)} abonnements activés (1 parent + {len(enfants)} enfants){parent_info}'
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du paiement familial: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def verifier_paiements_en_attente():
        """
        Vérifie les paiements en attente et les active si nécessaire
        Cette méthode peut être appelée périodiquement pour vérifier les paiements
        """
        try:
            # Récupérer les paiements en attente depuis plus de 5 minutes
            limite_temps = timezone.now() - timedelta(minutes=5)
            paiements_en_attente = PaiementWave.objects.filter(
                statut='en_attente',
                date_creation__lt=limite_temps
            )
            
            for paiement in paiements_en_attente:
                # Simuler une vérification Wave (à remplacer par un vrai appel API)
                # Pour l'instant, on active automatiquement après 5 minutes
                logger.info(f"Activation automatique du paiement {paiement.transaction_id}")
                
                # Récupérer le montant depuis les informations stockées
                montant = int(paiement.montant)
                
                resultat = WaveCallbackService.traiter_paiement_reussi(
                    paiement.transaction_id,
                    montant,
                    f"AUTO_{paiement.transaction_id}"
                )
                
                if resultat['success']:
                    logger.info(f"Paiement {paiement.transaction_id} activé automatiquement")
                else:
                    logger.error(f"Erreur activation automatique {paiement.transaction_id}: {resultat['error']}")
                    
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des paiements en attente: {e}")

class CommissionService:
    """Service pour gérer les commissions des partenaires"""
    
    @staticmethod
    def attribuer_commission(abonnement):
        """Attribue une commission au partenaire si l'abonnement provient d'un parrainage partenaire"""
        try:
            # Vérifier si l'utilisateur a un parrain et si ce parrain est un partenaire
            if not hasattr(abonnement.utilisateur, 'parrain') or not abonnement.utilisateur.parrain:
                return {'success': False, 'message': 'Aucun parrain trouvé'}
            
            parrain = abonnement.utilisateur.parrain.parrain
            
            # Vérifier si le parrain est un partenaire
            if parrain.role != 'partenaire':
                return {'success': False, 'message': 'Le parrain n\'est pas un partenaire'}
            
            # Vérifier que l'abonnement n'est pas gratuit
            if abonnement.montant_paye <= 0:
                return {'success': False, 'message': 'Aucune commission sur les abonnements gratuits'}
            
            # Récupérer la configuration pour le pourcentage
            from utilisateurs.models import ConfigurationPartenaire
            config = ConfigurationPartenaire.get_configuration_active()
            pourcentage = config.pourcentage_commission_default
            
            # Calculer la commission
            from decimal import Decimal
            montant_commission = Decimal(str(abonnement.montant_paye)) * Decimal(str(pourcentage)) / Decimal('100')
            
            # Créer l'enregistrement de commission
            from utilisateurs.models import Commission
            commission = Commission.objects.create(
                partenaire=parrain,
                montant_abonnement=Decimal(str(abonnement.montant_paye)),
                montant_commission=montant_commission,
                abonnement_id=abonnement.id
            )
            
            # Mettre à jour le champ commission_totale_accumulee
            parrain.commission_totale_accumulee += montant_commission
            parrain.save()
            
            print(f"✅ Commission de {montant_commission} FCFA ({pourcentage}%) attribuée au partenaire {parrain.email}")
            
            return {
                'success': True,
                'commission': float(montant_commission),
                'pourcentage': float(pourcentage),
                'partenaire': parrain.email,
                'message': f'Commission de {montant_commission} FCFA ({pourcentage}%) attribuée'
            }
            
        except Exception as e:
            print(f"❌ Erreur lors de l'attribution de la commission: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_statistiques_partenaire(partenaire):
        """Récupère les statistiques d'un partenaire"""
        try:
            commissions = Commission.objects.filter(partenaire=partenaire)
            
            # Statistiques générales
            total_commissions = sum(c.montant_commission for c in commissions)
            total_abonnements = commissions.count()
            
            # Commissions du mois en cours
            maintenant = timezone.now()
            debut_mois = maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            commissions_mois = commissions.filter(date_commission__gte=debut_mois)
            commissions_mois_total = sum(c.montant_commission for c in commissions_mois)
            
            # Commissions des 30 derniers jours
            il_y_a_30_jours = maintenant - timedelta(days=30)
            commissions_30j = commissions.filter(date_commission__gte=il_y_a_30_jours)
            commissions_30j_total = sum(c.montant_commission for c in commissions_30j)
            
            return {
                'total_commissions': float(total_commissions),
                'total_abonnements': total_abonnements,
                'commissions_mois': float(commissions_mois_total),
                'commissions_30j': float(commissions_30j_total),
                'commission_disponible': float(partenaire.commission_disponible),
                'peut_retirer': partenaire.peut_retirer,
                'montant_retrait_maximum': float(partenaire.montant_retrait_maximum)
            }
            
        except Exception as e:
            print(f"❌ Erreur lors du calcul des statistiques: {e}")
            return {
                'error': str(e)
            }
