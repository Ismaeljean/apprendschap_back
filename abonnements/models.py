# abonnements/models.py
from django.db import models
from utilisateurs.models import Utilisateur
from django.utils import timezone
from datetime import timedelta
import uuid


class PackAbonnement(models.Model):
    """Modèle pour définir les différents packs d'abonnement"""
    TYPE_CHOICES = [
        ('gratuit', 'Gratuit'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('special', 'Pack Spécial'),
        ('famille', 'Pack Familial'),
    ]
    
    PERIODE_CHOICES = [
        ('semaine', 'Semaine'),
        ('mois', 'Mois'),
        ('trimestre', 'Trimestre'),
        ('semestre', 'Semestre'),
        ('annee', 'Année'),
    ]
    
    nom = models.CharField(max_length=100)
    type_pack = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField()
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES)
    duree_jours = models.IntegerField(help_text="Durée en jours")
    actif = models.BooleanField(default=True)
    pack_special = models.BooleanField(default=False)
    reduction_pourcentage = models.IntegerField(default=0, help_text="Réduction en pourcentage")
    conditions_speciales = models.TextField(blank=True, null=True)
    
    # Note: Les fonctionnalités sont maintenant gérées par le modèle PackPermissions
    
    # Semaine gratuite
    offre_semaine_gratuite = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Pack d'abonnement"
        verbose_name_plural = "Packs d'abonnement"
    
    def __str__(self):
        return f"{self.nom} - {self.prix} FCFA/{self.periode}"
    
    @property
    def prix_reduit(self):
        """Calcule le prix avec réduction"""
        if self.reduction_pourcentage > 0:
            from decimal import Decimal
            reduction_factor = Decimal(str(1 - self.reduction_pourcentage / 100))
            return self.prix * reduction_factor
        return self.prix
    
    @property
    def code_auto(self):
        """Génère automatiquement un code basé sur le nom du pack"""
        nom_lower = self.nom.lower()
        if "gratuit" in nom_lower or "1" in self.nom:
            return "pack-1"
        elif "standard" in nom_lower or "2" in self.nom:
            return "pack-2"  
        elif "premium" in nom_lower or "3" in self.nom:
            return "pack-3"
        elif "4" in self.nom:
            return "pack-4"
        elif "vacances" in nom_lower:
            return "pack-vacances"
        elif "bac" in nom_lower or "bepc" in nom_lower or "examen" in nom_lower:
            return "pack-examen"
        elif "découverte" in nom_lower or "bienvenue" in nom_lower:
            return "pack-decouverte"
        else:
            return f"pack-{self.id}"


class PackPermissions(models.Model):
    """Modèle pour définir les permissions et restrictions de chaque pack"""
    pack = models.OneToOneField(PackAbonnement, on_delete=models.CASCADE, related_name='permissions')
    
    # Limites de contenu mensuelles
    max_cours_par_mois = models.PositiveIntegerField(default=0, help_text="0 = illimité")
    max_quiz_par_mois = models.PositiveIntegerField(default=0, help_text="0 = illimité")
    max_examens_par_mois = models.PositiveIntegerField(default=0, help_text="0 = illimité")
    
    # Accès aux fonctionnalités
    acces_cours_premium = models.BooleanField(default=False, help_text="Accès aux cours premium")
    acces_ia_standard = models.BooleanField(default=False, help_text="Support IA standard")
    acces_ia_prioritaire = models.BooleanField(default=False, help_text="Support IA prioritaire")
    acces_certificats = models.BooleanField(default=False, help_text="Accès aux certificats")
    acces_contenu_hors_ligne = models.BooleanField(default=False, help_text="Téléchargement de contenu")
    acces_communautaire = models.BooleanField(default=False, help_text="Accès au forum communautaire")
    support_prioritaire = models.BooleanField(default=False, help_text="Support prioritaire")
    acces_prioritaire_nouveautes = models.BooleanField(default=False, help_text="Accès prioritaire aux nouveautés")
    
    # Spécialisations
    specialisation_examens = models.BooleanField(default=False, help_text="Spécialisé pour les examens")
    contenu_examens_prioritaire = models.BooleanField(default=False, help_text="Contenu examens prioritaire")
    
    # Fonctionnalités familiales
    nombre_enfants_max = models.PositiveIntegerField(default=0, help_text="Nombre maximum d'enfants")
    profils_separes = models.BooleanField(default=False, help_text="Profils séparés pour chaque enfant")
    suivi_familial = models.BooleanField(default=False, help_text="Suivi familial")
    
    # Incitations et restrictions
    upgrade_reminder = models.BooleanField(default=False, help_text="Rappels d'upgrade")
    teaser_content = models.BooleanField(default=False, help_text="Contenu teaser premium")
    restriction_temps = models.BooleanField(default=False, help_text="Restriction temporelle")
    restriction_contenu = models.BooleanField(default=False, help_text="Restriction de contenu")
    restriction_examens = models.BooleanField(default=False, help_text="Restriction d'examens")
    
    # Messages de restriction personnalisés
    message_restriction = models.TextField(
        default="Vous avez atteint votre limite. Passez à un pack supérieur !",
        help_text="Message affiché quand les restrictions sont atteintes"
    )
    
    # Bonus et incitations
    bonus_parrainage = models.BooleanField(default=False, help_text="Bonus pour parrainage")
    bonus_inscription = models.BooleanField(default=False, help_text="Bonus pour inscription")
    bonus_conversion_parrainage = models.BooleanField(default=False, help_text="Bonus de conversion parrainage")
    bonus_conversion_standard = models.BooleanField(default=False, help_text="Bonus de conversion standard")
    bonus_annuel = models.BooleanField(default=False, help_text="Bonus annuel")
    acces_exclusif = models.BooleanField(default=False, help_text="Contenu exclusif")
    
    # Sources et types
    source_parrainage = models.BooleanField(default=False, help_text="Source parrainage")
    source_inscription = models.BooleanField(default=False, help_text="Source inscription")
    
    class Meta:
        verbose_name = "Permissions du pack"
        verbose_name_plural = "Permissions des packs"
    
    def __str__(self):
        return f"Permissions - {self.pack.nom}"
    
    def get_message_restriction_dynamique(self, jours_restants=None, cours_utilises=None, quiz_utilises=None):
        """Retourne le message de restriction avec des variables dynamiques"""
        message = self.message_restriction
        
        if jours_restants is not None:
            message = message.replace('{jours_restants}', str(jours_restants))
        
        if cours_utilises is not None and self.max_cours_par_mois > 0:
            message = message.replace('{cours_utilises}', str(cours_utilises))
            message = message.replace('{max_cours}', str(self.max_cours_par_mois))
        
        if quiz_utilises is not None and self.max_quiz_par_mois > 0:
            message = message.replace('{quiz_utilises}', str(quiz_utilises))
            message = message.replace('{max_quiz}', str(self.max_quiz_par_mois))
        
        return message


class Abonnement(models.Model):
    """Gestion des abonnements utilisateurs"""
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('expire', 'Expiré'),
        ('suspendu', 'Suspendu'),
        ('essai', 'Essai gratuit'),
    ]
    
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    pack = models.ForeignKey(PackAbonnement, on_delete=models.CASCADE, null=True, blank=True)
    date_debut = models.DateTimeField(default=timezone.now)
    date_fin = models.DateTimeField(null=True, blank=True)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
    actif = models.BooleanField(default=True)
    
    # Informations de paiement Wave
    wave_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    wave_payment_status = models.CharField(max_length=50, blank=True, null=True)
    wave_payment_date = models.DateTimeField(null=True, blank=True)
    
    # Essai gratuit
    est_essai_gratuit = models.BooleanField(default=False)
    date_fin_essai = models.DateTimeField(null=True, blank=True)
    
    # Renouvellement automatique
    renouvellement_auto = models.BooleanField(default=False)
    
    # 🎁 Source parrainage
    source_parrainage = models.BooleanField(default=False, help_text="True si l'abonnement provient du système de parrainage")
    
    # Historique des renouvellements
    date_renouvellement = models.DateTimeField(null=True, blank=True, help_text="Date du dernier renouvellement")
    
    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
    
    def __str__(self):
        return f"Abonnement {self.pack.nom} de {self.utilisateur.email}"
    
    def save(self, *args, **kwargs):
        """Calcule automatiquement la date de fin lors de la création"""
        if not self.pk and not self.date_fin:
            if self.est_essai_gratuit:
                self.date_fin = timezone.now() + timedelta(days=7)
                self.date_fin_essai = self.date_fin
            else:
                self.date_fin = timezone.now() + timedelta(days=self.pack.duree_jours)
        super().save(*args, **kwargs)
    
    @property
    def est_valide(self):
        """Vérifie si l'abonnement est valide"""
        if not self.actif or self.statut in ['inactif', 'suspendu']:
            return False
        if self.date_fin is None:  # Abonnement illimité
            return True
        return self.date_fin > timezone.now()
    
    @property
    def jours_restants(self):
        """Calcule le nombre de jours restants"""
        if not self.date_fin:
            return None
        delta = self.date_fin - timezone.now()
        return max(0, delta.days)
    
    @property
    def pourcentage_utilise(self):
        """Calcule le pourcentage de temps utilisé"""
        if not self.date_fin or not self.date_debut:
            return 0
        total_duree = (self.date_fin - self.date_debut).days
        temps_ecoule = (timezone.now() - self.date_debut).days
        return min(100, max(0, (temps_ecoule / total_duree) * 100))
    
    @property
    def statut_display(self):
        """Retourne le statut lisible"""
        if self.statut == 'essai':
            return "Essai gratuit"
        if not self.actif:
            return "Inactif"
        if self.date_fin is None:
            return "Illimité"
        if self.date_fin > timezone.now():
            return "Actif"
        return "Expiré"


class PaiementWave(models.Model):
    """Modèle pour gérer les paiements via Wave"""
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('reussi', 'Réussi'),
        ('echoue', 'Échoué'),
        ('annule', 'Annulé'),
    ]
    
    # Abonnement peut être null pendant l'initiation du paiement
    abonnement = models.ForeignKey(Abonnement, on_delete=models.CASCADE, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    devise = models.CharField(max_length=3, default='XOF')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Données Wave
    wave_reference = models.CharField(max_length=100, blank=True, null=True)
    wave_phone = models.CharField(max_length=20, blank=True, null=True)
    wave_email = models.EmailField(blank=True, null=True)
    
    # Informations temporaires pour créer l'abonnement après paiement
    pack_id = models.IntegerField(null=True, blank=True, help_text="ID du pack à créer après paiement")
    utilisateur_id = models.IntegerField(null=True, blank=True, help_text="ID de l'utilisateur")
    parent_id = models.IntegerField(null=True, blank=True, help_text="ID du parent qui effectue le paiement (pour les abonnements enfants)")
    renouvellement_auto = models.BooleanField(default=False, help_text="Renouvellement automatique")
    
    # Données de callback
    callback_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Paiement Wave"
        verbose_name_plural = "Paiements Wave"
    
    def __str__(self):
        return f"Paiement {self.transaction_id} - {self.montant} {self.devise}"
    
    @property
    def est_reussi(self):
        return self.statut == 'reussi'


class PackFamilial(models.Model):
    """Modèle pour les packs familiaux"""
    TYPE_CHOICES = [
        ('familial_2', 'Famille 2 enfants'),
        ('familial_3', 'Famille 3+ enfants'),
        ('familial_4', 'Famille 4+ enfants'),
    ]
    
    PERIODE_CHOICES = [
        ('semaine', 'Semaine'),
        ('mois', 'Mois'),
        ('trimestre', 'Trimestre'),
        ('semestre', 'Semestre'),
        ('annee', 'Année'),
    ]
    
    nom = models.CharField(max_length=100)
    type_familial = models.CharField(max_length=20, choices=TYPE_CHOICES, default='familial_2')
    nombre_enfants = models.IntegerField(default=2)
    description = models.TextField()
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES, default='mois')
    duree_jours = models.IntegerField(help_text="Durée en jours", default=30)
    actif = models.BooleanField(default=True)
    pack_familial = models.BooleanField(default=True)
    reduction_pourcentage = models.IntegerField(default=20, help_text="Réduction en pourcentage")
    conditions_speciales = models.TextField(blank=True, null=True)
    
    # Note: Les fonctionnalités sont maintenant gérées par le modèle PackPermissions
    
    # Semaine gratuite
    offre_semaine_gratuite = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Pack familial"
        verbose_name_plural = "Packs familiaux"
    
    def __str__(self):
        return f"{self.nom} - {self.prix} FCFA/{self.periode} ({self.nombre_enfants} enfants)"
    
    @property
    def prix_reduit(self):
        """Calcule le prix avec réduction"""
        if self.reduction_pourcentage > 0:
            from decimal import Decimal
            reduction_factor = Decimal(str(1 - self.reduction_pourcentage / 100))
            return self.prix * reduction_factor
        return self.prix


class BonusParrainage(models.Model):
    """Modèle pour gérer les bonus de parrainage accumulés par utilisateur"""
    utilisateur = models.OneToOneField('utilisateurs.Utilisateur', on_delete=models.CASCADE, related_name='bonus_parrainage')
    bonus_accumules = models.PositiveIntegerField(default=0, help_text="Nombre de semaines gratuites accumulées")
    bonus_utilises = models.PositiveIntegerField(default=0, help_text="Nombre de bonus déjà utilisés")
    date_dernier_bonus = models.DateTimeField(auto_now=True, help_text="Date du dernier bonus reçu")
    
    class Meta:
        verbose_name = "Bonus de parrainage"
        verbose_name_plural = "Bonus de parrainage"
    
    def __str__(self):
        return f"Bonus de {self.utilisateur.email} ({self.bonus_accumules} accumulés, {self.bonus_utilises} utilisés)"
    
    @property
    def bonus_disponibles(self):
        """Retourne le nombre de bonus disponibles (accumulés - utilisés)"""
        return max(0, self.bonus_accumules - self.bonus_utilises)
    
    @property
    def peut_utiliser_bonus(self):
        """Retourne True si l'utilisateur peut utiliser ses bonus (dès qu'il en a au moins 1)"""
        return self.bonus_disponibles > 0
    
    def ajouter_bonus(self, nombre=1):
        """Ajoute des bonus (pas de limite)"""
        self.bonus_accumules += nombre
        self.save()
        return True
    
    def utiliser_bonus(self, nombre=1):
        """Utilise des bonus disponibles"""
        if self.bonus_disponibles >= nombre:
            self.bonus_utilises += nombre
            self.save()
            return True
        return False


class Parrainage(models.Model):
    """Modèle pour gérer les relations parrain-filleul"""
    parrain = models.ForeignKey('utilisateurs.Utilisateur', on_delete=models.CASCADE, related_name='filleuls', help_text="Utilisateur qui parraine")
    filleul = models.OneToOneField('utilisateurs.Utilisateur', on_delete=models.CASCADE, related_name='parrain', help_text="Utilisateur parrainé")
    code_parrainage = models.CharField(max_length=20, help_text="Code de parrainage utilisé")
    date_parrainage = models.DateTimeField(auto_now_add=True, help_text="Date de création du parrainage")
    bonus_attribue = models.BooleanField(default=False, help_text="True si le bonus a été attribué au parrain")
    date_bonus_attribue = models.DateTimeField(null=True, blank=True, help_text="Date d'attribution du bonus")
    
    # 🎁 NOUVEAUX CHAMPS POUR LES AVANTAGES DU FILLEUL
    filleul_bonus_attribue = models.BooleanField(default=False, help_text="True si le bonus a été attribué au filleul")
    date_filleul_bonus = models.DateTimeField(null=True, blank=True, help_text="Date d'attribution du bonus au filleul")
    
    class Meta:
        verbose_name = "Parrainage"
        verbose_name_plural = "Parrainages"
        unique_together = ['parrain', 'filleul']
    
    def __str__(self):
        return f"{self.parrain.email} → {self.filleul.email}"
    
    def attribuer_bonus(self):
        """Attribue le bonus au parrain si pas encore fait"""
        if not self.bonus_attribue:
            # Créer ou récupérer le bonus du parrain
            bonus, created = BonusParrainage.objects.get_or_create(utilisateur=self.parrain)
            
            # Ajouter le bonus (1 semaine gratuite)
            if bonus.ajouter_bonus(1):
                self.bonus_attribue = True
                self.date_bonus_attribue = timezone.now()
                self.save()
                return True
        return False
    
    def attribuer_bonus_filleul(self):
        """Attribue le bonus au filleul lors de l'inscription"""
        if not self.filleul_bonus_attribue:
            try:
                # Créer un abonnement gratuit d'une semaine pour le filleul
                from .models import PackAbonnement, Abonnement
                from django.utils import timezone
                from datetime import timedelta
                
                # Trouver le pack gratuit ou créer un pack de bienvenue
                pack_bienvenue, created = PackAbonnement.objects.get_or_create(
                    nom="Pack de Bienvenue Parrainage",
                    defaults={
                        'prix': 0,
                        'duree_jours': 7,
                        'description': 'Pack gratuit d\'une semaine offert grâce au parrainage',
                        'cours_limites': 10,
                        'quiz_limites': 5,
                        'examens_inclus': False,
                        'certificats_inclus': False,
                        'support_ia_prioritaire': False,
                        'contenu_hors_ligne': False,
                        'offre_semaine_gratuite': False,
                        'actif': True
                    }
                )
                
                # Créer l'abonnement gratuit
                date_debut = timezone.now()
                date_fin = date_debut + timedelta(days=7)
                
                abonnement = Abonnement.objects.create(
                    utilisateur=self.filleul,
                    pack=pack_bienvenue,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    statut='actif',
                    actif=True,
                    est_essai_gratuit=True,
                    source_parrainage=True
                )
                
                # Marquer le bonus comme attribué
                self.filleul_bonus_attribue = True
                self.date_filleul_bonus = timezone.now()
                self.save()
                
                return {
                    'success': True,
                    'abonnement': abonnement,
                    'message': 'Pack de bienvenue d\'une semaine activé !'
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Erreur lors de l\'attribution du bonus filleul: {str(e)}'
                }
        
        return {
            'success': False,
            'error': 'Bonus déjà attribué au filleul'
        }


class HistoriqueRenouvellement(models.Model):
    """Modèle pour tracer l'historique des renouvellements d'abonnements"""
    abonnement = models.ForeignKey(Abonnement, on_delete=models.CASCADE, related_name='renouvellements')
    date_renouvellement = models.DateTimeField(auto_now_add=True, help_text="Date du renouvellement")
    duree_ajoutee = models.PositiveIntegerField(help_text="Nombre de jours ajoutés")
    montant_renouvellement = models.DecimalField(max_digits=10, decimal_places=2, help_text="Montant du renouvellement")
    
    class Meta:
        verbose_name = "Historique de renouvellement"
        verbose_name_plural = "Historiques de renouvellements"
        ordering = ['-date_renouvellement']
    
    def __str__(self):
        return f"Renouvellement {self.abonnement.pack.nom} +{self.duree_ajoutee}j ({self.date_renouvellement.strftime('%d/%m/%Y')})"


