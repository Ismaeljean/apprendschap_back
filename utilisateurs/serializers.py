# utilisateurs/serializers.py
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import make_password
from .models import Utilisateur, InscriptionEnAttente, Commission, RetraitCommission, ConfigurationPartenaire, LienParentEnfant
from academic_structure.models import NiveauScolaire
from academic_structure.serializers import NiveauScolaireSerializer
from .services import generer_otp, envoyer_otp_email

from django.db.models import Avg, Sum, F


class UtilisateurSerializer(serializers.ModelSerializer):
    niveau = NiveauScolaireSerializer(read_only=True)
    niveau_id = serializers.PrimaryKeyRelatedField(
        queryset=NiveauScolaire.objects.all(),
        write_only=True,
        source='niveau',
        required=False
    )

    class Meta:
        model = Utilisateur
        fields = ['id', 'first_name', 'last_name', 'email', 'role', 'niveau', 'niveau_id', 'date_inscription', 'email_verifie', 'matricule', 'telephone', 'avatar_choisi']
        read_only_fields = ['id', 'date_inscription', 'email_verifie']
        
    def validate_matricule(self, value):
        """Valider l'unicité du matricule"""
        if not value:
            return value  # Matricule optionnel
            
        value = value.strip()
        
        # Vérifier l'unicité
        queryset = Utilisateur.objects.filter(matricule=value)
        
        # Exclure l'instance actuelle lors de la mise à jour
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        if queryset.exists():
            raise serializers.ValidationError(
                "Ce matricule est déjà utilisé par un autre utilisateur"
            )
            
        return value


class UtilisateurPartenaireSerializer(serializers.ModelSerializer):
    """Serializer pour les utilisateurs partenaires avec leurs données spécifiques"""
    commission_disponible = serializers.SerializerMethodField()
    commission_totale = serializers.SerializerMethodField()
    peut_retirer = serializers.SerializerMethodField()
    
    # Champs dynamiques depuis ConfigurationPartenaire
    pourcentage_commission = serializers.SerializerMethodField()
    seuil_retrait_minimum = serializers.SerializerMethodField()
    montant_retrait_multiple = serializers.SerializerMethodField()
    methodes_paiement = serializers.SerializerMethodField()
    
    class Meta:
        model = Utilisateur
        fields = [
            'id', 'first_name', 'last_name', 'email', 'code_parrainage',
            'pourcentage_commission', 'seuil_retrait_minimum', 'montant_retrait_multiple', 
            'methodes_paiement', 'commission_disponible', 'commission_totale', 'date_inscription', 'peut_retirer'
        ]
        read_only_fields = [
            'id', 'date_inscription'
        ]
    
    def get_pourcentage_commission(self, obj):
        """Récupère le pourcentage depuis ConfigurationPartenaire"""
        try:
            config = ConfigurationPartenaire.get_configuration_active()
            return config.pourcentage_commission_default
        except:
            return 10  # Valeur par défaut
    
    def get_seuil_retrait_minimum(self, obj):
        """Récupère le seuil minimum depuis ConfigurationPartenaire"""
        try:
            config = ConfigurationPartenaire.get_configuration_active()
            return config.seuil_retrait_minimum
        except:
            return 25000  # Valeur par défaut
    
    def get_montant_retrait_multiple(self, obj):
        """Récupère le multiple de retrait depuis ConfigurationPartenaire"""
        try:
            config = ConfigurationPartenaire.get_configuration_active()
            return config.montant_retrait_multiple
        except:
            return 5000  # Valeur par défaut
    
    def get_methodes_paiement(self, obj):
        """Récupère les méthodes de paiement depuis ConfigurationPartenaire"""
        try:
            config = ConfigurationPartenaire.get_configuration_active()
            return config.methodes_paiement
        except:
            return ['wave', 'orange_money', 'mtn_money', 'moov_money']
    
    def get_commission_disponible(self, obj):
        """Calcule la commission disponible pour retrait"""
        try:
            from django.db.models import Sum
            from .models import Commission, RetraitCommission
            
            # Calculer le total des commissions
            total_commissions = Commission.objects.filter(
                partenaire=obj
            ).aggregate(total=Sum('montant_commission'))['total'] or 0
            
            # Calculer le total des retraits approuvés
            total_retraits = RetraitCommission.objects.filter(
                partenaire=obj,
                statut='approuve'
            ).aggregate(total=Sum('montant'))['total'] or 0
            
            # Commission disponible = total commissions - total retraits approuvés
            commission_disponible = float(total_commissions) - float(total_retraits)
            
            
            return max(0, commission_disponible)  # Ne pas retourner de valeur négative
        except Exception as e:
            return 0.0
    
    def get_commission_totale(self, obj):
        """Calcule le total des commissions gagnées"""
        try:
            from django.db.models import Sum
            from .models import Commission
            
            total_commissions = Commission.objects.filter(
                partenaire=obj
            ).aggregate(total=Sum('montant_commission'))['total'] or 0
            
            return float(total_commissions)
        except Exception as e:
            return 0.0
    
    def get_peut_retirer(self, obj):
        """Détermine si le partenaire peut retirer ses commissions"""
        try:
            # Calculer le total des commissions (pas la commission disponible)
            from django.db.models import Sum
            from .models import Commission
            
            total_commissions = Commission.objects.filter(
                partenaire=obj
            ).aggregate(total=Sum('montant_commission'))['total'] or 0
            
            # Récupérer le seuil minimum
            config = ConfigurationPartenaire.get_configuration_active()
            seuil_minimum = config.seuil_retrait_minimum
            
            # Le partenaire peut retirer si ses commissions totales >= seuil minimum
            return float(total_commissions) >= float(seuil_minimum)
        except Exception as e:
            return False
    
    def validate_telephone_paiement(self, value):
        """Valider le numéro de téléphone"""
        if not value:
            raise serializers.ValidationError("Le numéro de téléphone est obligatoire")
        
        # Validation basique du format
        if len(value) < 8:
            raise serializers.ValidationError("Le numéro de téléphone doit contenir au moins 8 caractères")
        
        return value


class InscriptionEnAttenteSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions en attente"""
    niveau = NiveauScolaireSerializer(read_only=True)
    niveau_id = serializers.PrimaryKeyRelatedField(
        queryset=NiveauScolaire.objects.all(),
        write_only=True,
        source='niveau',
        required=False
    )
    
    class Meta:
        model = InscriptionEnAttente
        fields = ['id', 'email', 'nom', 'prenom', 'role', 'niveau', 'niveau_id', 'code_parrain_utilise', 'otp', 'otp_expires_at', 'date_creation']
        read_only_fields = ['id', 'otp', 'otp_expires_at', 'date_creation']



class CommissionSerializer(serializers.ModelSerializer):
    """Serializer pour les commissions"""
    partenaire_nom = serializers.CharField(source='partenaire.get_full_name', read_only=True)
    partenaire_email = serializers.CharField(source='partenaire.email', read_only=True)
    
    class Meta:
        model = Commission
        fields = ['id', 'partenaire', 'partenaire_nom', 'partenaire_email', 'montant_abonnement', 'montant_commission', 'abonnement_id', 'date_commission']
        read_only_fields = ['id', 'date_commission']


class RetraitCommissionSerializer(serializers.ModelSerializer):
    """Serializer pour les retraits de commissions"""
    partenaire_nom = serializers.CharField(source='partenaire.get_full_name', read_only=True)
    partenaire_email = serializers.CharField(source='partenaire.email', read_only=True)
    
    class Meta:
        model = RetraitCommission
        fields = ['id', 'partenaire', 'partenaire_nom', 'partenaire_email', 'montant', 'statut', 'methode_paiement', 'telephone_paiement', 'numero_wave', 'date_demande', 'date_traitement', 'notes']
        read_only_fields = ['id', 'date_demande', 'date_traitement']


class FilleulSerializer(serializers.Serializer):
    """Serializer pour les filleuls (utilisateurs parrainés)"""
    nom = serializers.CharField()
    prenom = serializers.CharField()
    email = serializers.EmailField()
    date_inscription = serializers.DateTimeField()
    abonnement_actif = serializers.BooleanField()
    commission_totale = serializers.DecimalField(max_digits=10, decimal_places=2)


class DemandeRetraitSerializer(serializers.Serializer):
    """Serializer pour les demandes de retrait"""
    montant = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    def validate_montant(self, value):
        """Valider le montant du retrait"""
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être positif")
        return value


class ConfigurationSerializer(serializers.ModelSerializer):
    """Serializer pour la configuration des partenaires"""
    
    class Meta:
        model = ConfigurationPartenaire
        fields = [
            'id', 'nom', 'pourcentage_commission', 'seuil_retrait_minimum',
            'montant_retrait_multiple', 'methodes_paiement', 'actif',
            'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']
