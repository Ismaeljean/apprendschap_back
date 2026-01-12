from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
import random
import string

class UtilisateurManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('L\'email doit être défini')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)

class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Modèle utilisateur personnalisé"""
    ROLE_CHOICES = [
        ('eleve', 'Élève'),
        ('parent', 'Parent'),
        ('partenaire', 'Partenaire'),
    ]
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='eleve')
    
    # Champs requis pour AbstractBaseUser
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    # Manager personnalisé
    objects = UtilisateurManager()
    
    # Champs d'authentification
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    niveau = models.ForeignKey('academic_structure.NiveauScolaire', on_delete=models.SET_NULL, null=True, blank=True)
    matricule = models.CharField(max_length=20, blank=True, null=True, unique=True, help_text="Numéro matricule de l'étudiant")
    telephone = models.CharField(max_length=20, blank=True, null=True, help_text="Numéro de téléphone")
    
    # Gestion des avatars
    AVATAR_CHOICES = [
        ('avatar1', 'Avatar 1 - Étudiant'),
        ('avatar2', 'Avatar 2 - Étudiante'),
        ('avatar3', 'Avatar 3 - Professeur'),
        ('avatar4', 'Avatar 4 - Scientifique'),
        ('avatar5', 'Avatar 5 - Artiste'),
        ('avatar6', 'Avatar 6 - Sportif'),
        ('avatar7', 'Avatar 7 - Génie'),
    ]
    avatar_choisi = models.CharField(max_length=10, choices=AVATAR_CHOICES, default='avatar1', help_text="Avatar prédéfini choisi par l'utilisateur")
    photo_profil = models.ImageField(upload_to='photos_profil/', blank=True, null=True, help_text="Photo de profil personnalisée")
    
    date_inscription = models.DateTimeField(auto_now_add=True)
    derniere_activite = models.DateTimeField(auto_now=True)
    objectifs_apprentissage = models.TextField(blank=True)
    
    # Système de parrainage
    code_parrainage = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Code de parrainage unique de l'utilisateur")
    code_parrain_utilise = models.CharField(max_length=20, blank=True, null=True, help_text="Code de parrainage utilisé lors de l'inscription")
    
    # Champs pour les parents
    objectifs_apprentissage = models.TextField(blank=True, null=True, help_text="Objectifs d'apprentissage définis par le parent")
    
    # Champs pour les partenaires (avec valeurs par défaut)
    commission_retiree = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Commission retirée")
    commission_totale_accumulee = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Commission totale accumulée")
    methode_paiement = models.CharField(max_length=50, blank=True, null=True, help_text="Méthode de paiement préférée")
    telephone_paiement = models.CharField(max_length=20, blank=True, null=True, help_text="Téléphone pour paiement")
    nombre_abonnements_parraines = models.PositiveIntegerField(default=0, help_text="Nombre d'abonnements parrainés")
    nombre_filleuls_uniques = models.PositiveIntegerField(default=0, help_text="Nombre de filleuls uniques")

    # Champs pour la progression et l'activité
    derniere_activite = models.DateTimeField(default=timezone.now)
    date_inscription = models.DateTimeField(default=timezone.now)
    email_verifie = models.BooleanField(default=False)

    # Relations parent-enfant
    enfants_lies = models.ManyToManyField('self', through='LienParentEnfant', related_name='parents_lies', symmetrical=False, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UtilisateurManager()

    def __str__(self):
        return self.email
    
    def save(self, *args, **kwargs):
        if not self.code_parrainage:
            self.code_parrainage = self.generer_code_parrainage()
        super().save(*args, **kwargs)
    
    def generer_code_parrainage(self):
        """Génère un code de parrainage unique"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Utilisateur.objects.filter(code_parrainage=code).exists():
                return code
    
    
    
    def get_full_name(self):
        """Retourne le nom complet de l'utilisateur"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def calculer_nombre_filleuls_uniques(self):
        """Calcule le nombre de filleuls uniques pour les partenaires"""
        if self.role != 'partenaire':
            return 0
        
        # Compter les utilisateurs qui ont utilisé le code de parrainage de ce partenaire
        from .models import InscriptionEnAttente
        return InscriptionEnAttente.objects.filter(
            code_parrain_utilise=self.code_parrainage
        ).count()
    
    def get_short_name(self):
        """Retourne le prénom de l'utilisateur"""
        return self.first_name
    
    def has_perm(self, perm, obj=None):
        """Vérifie si l'utilisateur a une permission"""
        if self.is_superuser:
            return True
        return super().has_perm(perm, obj)
    
    def has_module_perms(self, app_label):
        """Vérifie si l'utilisateur a des permissions pour un module"""
        if self.is_superuser:
            return True
        return super().has_module_perms(app_label)

class InscriptionEnAttente(models.Model):
    """Gestion des inscriptions temporaires avec OTP"""
    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    role = models.CharField(max_length=20)
    niveau = models.ForeignKey('academic_structure.NiveauScolaire', on_delete=models.SET_NULL, null=True)
    code_parrain_utilise = models.CharField(max_length=8, null=True, blank=True, verbose_name="Code de parrainage utilisé")
    otp = models.CharField(max_length=6)
    otp_expires_at = models.DateTimeField()
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
    
    def ajouter_commission(self, montant_abonnement, abonnement_id=None):
        """Ajoute une commission au partenaire basée sur le pourcentage configuré"""
        from decimal import Decimal
        
        # Récupérer la configuration pour le pourcentage
        config = ConfigurationPartenaire.get_configuration_active()
        pourcentage = config.pourcentage_commission_default
        
        # Calculer la commission (montant_abonnement * pourcentage / 100)
        montant_commission = Decimal(str(montant_abonnement)) * Decimal(str(pourcentage)) / Decimal('100')
        
        # Créer l'enregistrement de commission
        commission = Commission.objects.create(
            partenaire=self,
            montant_abonnement=Decimal(str(montant_abonnement)),
            montant_commission=montant_commission,
            abonnement_id=abonnement_id
        )
        
        # Mettre à jour le champ commission_totale_accumulee
        self.commission_totale_accumulee += montant_commission
        self.save()
        
        return montant_commission

class Commission(models.Model):
    """Enregistrement des commissions gagnées par les partenaires"""
    partenaire = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='commissions')
    montant_abonnement = models.DecimalField(max_digits=10, decimal_places=2, help_text="Montant de l'abonnement (en FCFA)")
    montant_commission = models.DecimalField(max_digits=10, decimal_places=2, help_text="Montant de la commission (en FCFA)")
    abonnement_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID de l'abonnement généré")
    date_commission = models.DateTimeField(auto_now_add=True)
    # notes = models.TextField(blank=True, help_text="Notes additionnelles")  # Temporairement commenté

    class Meta:
        verbose_name = "Commission"
        verbose_name_plural = "Commissions"
        ordering = ['-date_commission']

    def __str__(self):
        return f"Commission {self.partenaire.get_full_name()} - {self.montant_commission} FCFA"

class RetraitCommission(models.Model):
    """Gestion des retraits de commissions"""
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('rejete', 'Rejeté'),
        ('traite', 'Traité'),
    ]
    
    partenaire = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='retraits')
    montant = models.DecimalField(max_digits=10, decimal_places=2, help_text="Montant du retrait (en FCFA)")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    methode_paiement = models.CharField(max_length=20, help_text="Méthode de paiement utilisée")
    telephone_paiement = models.CharField(max_length=20, help_text="Numéro de téléphone pour le paiement")
    numero_wave = models.CharField(max_length=20, blank=True, null=True, help_text="Numéro Wave pour le retrait")
    date_demande = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Notes de traitement", default="")

    class Meta:
        verbose_name = "Retrait de Commission"
        verbose_name_plural = "Retraits de Commissions"
        ordering = ['-date_demande']

    def __str__(self):
        return f"Retrait {self.partenaire.get_full_name()} - {self.montant} FCFA"


class ConfigurationPartenaire(models.Model):
    """Configuration centralisée pour les partenaires"""
    nom = models.CharField(max_length=100, help_text="Nom de la configuration")
    description = models.TextField(blank=True, null=True, help_text="Description de la configuration")
    pourcentage_commission_default = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00,
        help_text="Pourcentage de commission par défaut"
    )
    seuil_retrait_minimum = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=25000.00,
        help_text="Seuil minimum pour les retraits (en FCFA)"
    )
    montant_retrait_multiple = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=5000.00,
        help_text="Montant multiple pour les retraits (en FCFA)"
    )
    methodes_paiement_autorisees = models.TextField(
        default="wave,orange_money,mtn_money,moov_money",
        help_text="Méthodes de paiement autorisées (séparées par des virgules)"
    )
    validation_automatique_retrait = models.BooleanField(
        default=False,
        help_text="Validation automatique des retraits"
    )
    delai_traitement_retrait_heures = models.PositiveIntegerField(
        default=24,
        help_text="Délai de traitement des retraits en heures"
    )
    actif = models.BooleanField(default=True, help_text="Configuration active")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration Partenaire"
        verbose_name_plural = "Configurations Partenaires"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.nom} ({self.pourcentage_commission}%)"

    @classmethod
    def get_configuration_active(cls):
        """Retourne la configuration active"""
        try:
            return cls.objects.filter(actif=True).latest('date_creation')
        except cls.DoesNotExist:
            # Créer une configuration par défaut
            return cls.objects.create(
                nom="Configuration par défaut",
                pourcentage_commission_default=10.00,
                seuil_retrait_minimum=25000.00,
                montant_retrait_multiple=5000.00,
                methodes_paiement_autorisees="wave,orange_money,mtn_money,moov_money"
            )
    
    @property
    def pourcentage_commission(self):
        """Retourne le pourcentage de commission"""
        return self.pourcentage_commission_default
    
    @property
    def methodes_paiement(self):
        """Retourne les méthodes de paiement sous forme de liste"""
        if self.methodes_paiement_autorisees:
            return [methode.strip() for methode in self.methodes_paiement_autorisees.split(',')]
        return ['wave', 'orange_money', 'mtn_money', 'moov_money']


class LienParentEnfant(models.Model):
    """Modèle pour gérer les relations parent-enfant"""
    parent = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='liens_parent')
    enfant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='liens_enfant')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_confirmation = models.DateTimeField(null=True, blank=True, help_text="Date de confirmation du lien par l'enfant")

    class Meta:
        verbose_name = "Lien Parent-Enfant"
        verbose_name_plural = "Liens Parent-Enfant"
        unique_together = ('parent', 'enfant')
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.parent.get_full_name()} -> {self.enfant.get_full_name()}"


class PreferencesUtilisateur(models.Model):
    """Modèle pour les préférences utilisateur"""
    utilisateur = models.OneToOneField(
        Utilisateur, 
        on_delete=models.CASCADE, 
        related_name='preferences'
    )
    notifications_email = models.BooleanField(default=True, verbose_name='Notifications par email')
    rappels_etude = models.BooleanField(default=True, verbose_name="Rappels d'étude")
    partage_progres = models.BooleanField(default=False, verbose_name='Partage des progrès')
    profil_public = models.BooleanField(default=False, verbose_name='Profil public')
    langue = models.CharField(
        choices=[('fr', 'Français'), ('en', 'English'), ('ar', 'العربية')], 
        default='fr', 
        max_length=10, 
        verbose_name='Langue'
    )
    pays = models.CharField(
        choices=[
            ("Côte d'Ivoire", "Côte d'Ivoire"), ('France', 'France'), 
            ('Sénégal', 'Sénégal'), ('Mali', 'Mali'), ('Burkina Faso', 'Burkina Faso'), 
            ('Togo', 'Togo'), ('Bénin', 'Bénin'), ('Niger', 'Niger'), 
            ('Cameroun', 'Cameroun'), ('Gabon', 'Gabon'), ('Congo', 'Congo'), 
            ('RDC', 'République Démocratique du Congo'), ('Autre', 'Autre')
        ], 
        default="Côte d'Ivoire", 
        max_length=50, 
        verbose_name='Pays'
    )
    temps_session_etude = models.PositiveIntegerField(default=45, verbose_name="Durée session d'étude (minutes)")
    pause_session = models.PositiveIntegerField(default=15, verbose_name='Durée pause (minutes)')
    notification_quiz = models.BooleanField(default=True, verbose_name='Notifications de quiz')
    notification_examen = models.BooleanField(default=True, verbose_name="Notifications d'examens")
    notification_badge = models.BooleanField(default=True, verbose_name='Notifications de badges')
    date_modification = models.DateTimeField(auto_now=True, verbose_name='Date de modification')

    class Meta:
        verbose_name = 'Préférences utilisateur'
        verbose_name_plural = 'Préférences utilisateur'

    def __str__(self):
        return f"Préférences de {self.utilisateur.get_full_name()}"
