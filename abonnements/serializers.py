# abonnements/serializers.py
from rest_framework import serializers
from .models import (
    Abonnement, PackAbonnement, PaiementWave, 
    PackFamilial, BonusParrainage, Parrainage
)
from django.utils import timezone


class PackAbonnementSerializer(serializers.ModelSerializer):
    prix_reduit = serializers.ReadOnlyField()
    
    # Ajouter les données de permissions (nouvelles données)
    max_cours_par_mois = serializers.SerializerMethodField()
    max_quiz_par_mois = serializers.SerializerMethodField()
    max_examens_par_mois = serializers.SerializerMethodField()
    
    # Ajouter les autres permissions booléennes
    support_ia_standard = serializers.SerializerMethodField()
    acces_ia_prioritaire = serializers.SerializerMethodField()
    certificats_inclus_permissions = serializers.SerializerMethodField()
    contenu_hors_ligne_permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = PackAbonnement
        fields = '__all__'
    
    def get_max_cours_par_mois(self, obj):
        """Récupère le nombre max de cours par mois depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.max_cours_par_mois
        return 0  # Fallback si aucune permission configurée
    
    def get_max_quiz_par_mois(self, obj):
        """Récupère le nombre max de quiz par mois depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.max_quiz_par_mois
        return 0  # Fallback si aucune permission configurée
    
    def get_max_examens_par_mois(self, obj):
        """Récupère le nombre max d'examens par mois depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.max_examens_par_mois
        return 0  # Fallback si aucune permission configurée
    
    def get_support_ia_standard(self, obj):
        """Récupère l'accès IA standard depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.acces_ia_standard
        return False  # Fallback si aucune permission configurée
    
    def get_acces_ia_prioritaire(self, obj):
        """Récupère l'accès IA prioritaire depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.acces_ia_prioritaire
        return False  # Fallback si aucune permission configurée
    
    def get_certificats_inclus_permissions(self, obj):
        """Récupère l'accès aux certificats depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.acces_certificats
        return False  # Fallback si aucune permission configurée
    
    def get_contenu_hors_ligne_permissions(self, obj):
        """Récupère l'accès au contenu hors ligne depuis PackPermissions"""
        if hasattr(obj, 'permissions'):
            return obj.permissions.acces_contenu_hors_ligne
        return False  # Fallback si aucune permission configurée


class PackFamilialSerializer(serializers.ModelSerializer):
    prix_reduit = serializers.ReadOnlyField()
    
    class Meta:
        model = PackFamilial
        fields = '__all__'


class BonusParrainageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonusParrainage
        fields = '__all__'
        read_only_fields = ['utilisateur', 'date_dernier_bonus']


class ParrainageSerializer(serializers.ModelSerializer):
    filleul_email = serializers.EmailField(source='filleul.email', read_only=True)
    filleul_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = Parrainage
        fields = [
            'id', 'parrain', 'filleul', 'filleul_email', 'filleul_nom',
            'date_creation', 'bonus_attribue', 'date_bonus_attribue'
        ]
        read_only_fields = ['parrain', 'date_creation']
    
    def get_filleul_nom(self, obj):
        if obj.filleul.first_name and obj.filleul.last_name:
            return f"{obj.filleul.first_name} {obj.filleul.last_name}"
        return obj.filleul.email



class PaiementWaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaiementWave
        fields = '__all__'
        read_only_fields = ['abonnement', 'transaction_id', 'date_creation', 'date_mise_a_jour']


class AbonnementSerializer(serializers.ModelSerializer):
    pack = PackAbonnementSerializer(read_only=True)
    pack_id = serializers.IntegerField(write_only=True, required=False)
    jours_restants = serializers.ReadOnlyField()
    pourcentage_utilise = serializers.ReadOnlyField()
    statut_display = serializers.ReadOnlyField()
    est_valide = serializers.ReadOnlyField()
    
    class Meta:
        model = Abonnement
        fields = [
            'id', 'utilisateur', 'pack', 'pack_id', 'date_debut', 'date_fin',
            'montant_paye', 'statut', 'actif', 'wave_transaction_id',
            'wave_payment_status', 'wave_payment_date', 'est_essai_gratuit',
            'date_fin_essai', 'renouvellement_auto', 'jours_restants',
            'pourcentage_utilise', 'statut_display', 'est_valide'
        ]
        read_only_fields = ['utilisateur', 'date_debut', 'date_fin', 'est_valide']


class AbonnementDetailSerializer(serializers.ModelSerializer):
    pack = PackAbonnementSerializer(read_only=True)
    jours_restants = serializers.ReadOnlyField()
    pourcentage_utilise = serializers.ReadOnlyField()
    statut_display = serializers.ReadOnlyField()
    est_valide = serializers.ReadOnlyField()
    paiements = PaiementWaveSerializer(many=True, read_only=True)
    utilisation_mensuelle = serializers.SerializerMethodField()
    
    class Meta:
        model = Abonnement
        fields = [
            'id', 'pack', 'date_debut', 'date_fin', 'montant_paye', 'statut',
            'actif', 'est_essai_gratuit', 'date_fin_essai', 'renouvellement_auto',
            'jours_restants', 'pourcentage_utilise', 'statut_display', 'est_valide',
            'paiements', 'utilisation_mensuelle'
        ]
    
    def get_utilisation_mensuelle(self, obj):
        """Récupère l'utilisation du mois en cours"""
        from .services import StatistiquesService
        return StatistiquesService.get_utilisation_mensuelle(obj)


class DemandePaiementSerializer(serializers.Serializer):
    pack_id = serializers.IntegerField()
    telephone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)
    renouvellement_auto = serializers.BooleanField(default=False)
    
    def validate_pack_id(self, value):
        try:
            pack = PackAbonnement.objects.get(id=value, actif=True)
            return value
        except PackAbonnement.DoesNotExist:
            raise serializers.ValidationError("Pack d'abonnement invalide")
    
    def validate_telephone(self, value):
        # Validation basique du numéro de téléphone ivoirien
        if not value.startswith('+225') and not value.startswith('225'):
            raise serializers.ValidationError("Numéro de téléphone ivoirien requis")
        return value


class CallbackWaveSerializer(serializers.Serializer):
    """Sérialiseur pour les callbacks Wave"""
    transaction_id = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    reference = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    timestamp = serializers.DateTimeField(required=False)


class StatistiquesAbonnementSerializer(serializers.Serializer):
    """Sérialiseur pour les statistiques d'abonnement"""
    total_abonnements = serializers.IntegerField()
    abonnements_actifs = serializers.IntegerField()
    abonnements_essai = serializers.IntegerField()
    revenus_mensuels = serializers.DecimalField(max_digits=10, decimal_places=2)
    taux_conversion = serializers.FloatField()
    packs_populaires = serializers.ListField()
    utilisation_mensuelle = serializers.DictField(required=False)
