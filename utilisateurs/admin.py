# utilisateurs/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, InscriptionEnAttente, Commission, RetraitCommission, ConfigurationPartenaire, LienParentEnfant

@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'matricule', 'telephone', 'is_active', 'date_inscription')
    list_filter = ('role', 'is_active', 'date_inscription', 'avatar_choisi')
    search_fields = ('email', 'first_name', 'last_name', 'matricule', 'telephone', 'code_parrainage')
    ordering = ('-date_inscription',)
    readonly_fields = ('date_inscription', 'derniere_activite', 'code_parrainage')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'role', 'matricule', 'telephone')}),
        ('Avatar et photo', {'fields': ('avatar_choisi', 'photo_profil')}),
        ('Parrainage', {'fields': ('code_parrainage',), 'classes': ('collapse',)}),
        ('Paramètres compte', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Apprentissage', {'fields': ('objectifs_apprentissage',)}),
        ('Dates importantes', {'fields': ('date_inscription', 'derniere_activite', 'last_login')}),
        ('Permissions', {'fields': ('groups', 'user_permissions'), 'classes': ('collapse',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'matricule', 'telephone', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request)




@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('partenaire', 'montant_abonnement', 'montant_commission', 'date_commission', 'abonnement_id')
    list_filter = ('date_commission', 'partenaire')
    search_fields = ('partenaire__email', 'partenaire__first_name', 'partenaire__last_name')
    readonly_fields = ('date_commission',)
    ordering = ['-date_commission']
    # Temporairement commenté pour éviter les erreurs de colonnes manquantes
    # fields = ('partenaire', 'montant_abonnement', 'montant_commission', 'abonnement_id', 'notes')


@admin.register(RetraitCommission)
class RetraitCommissionAdmin(admin.ModelAdmin):
    list_display = ('partenaire', 'montant', 'statut', 'date_demande')
    list_filter = ('statut', 'date_demande')
    search_fields = ('partenaire__email', 'partenaire__first_name')
    readonly_fields = ('date_demande',)
    ordering = ['-date_demande']
    
    # Temporairement simplifié pour éviter les erreurs de colonnes manquantes
    # fieldsets = (
    #     ('Informations générales', {
    #         'fields': ('partenaire', 'montant', 'statut')
    #     }),
    #     ('Informations de paiement', {
    #         'fields': ('methode_paiement', 'telephone_paiement', 'reference_transaction')
    #     }),
    #     ('Traitement', {
    #         'fields': ('date_demande', 'date_traitement', 'notes')
    #     }),
    # )
    
    def nb_enfants(self, obj):
        """Nombre d'enfants liés pour les parents"""
        if obj.role == 'parent':
            return obj.enfants_lies.filter(actif=True).count()
        return '-'
    nb_enfants.short_description = "Enfants"
    
    def nb_parents(self, obj):
        """Nombre de parents liés pour les élèves"""
        if obj.role == 'eleve':
            return obj.parents_lies.filter(actif=True).count()
        return '-'
    nb_parents.short_description = "Parents"

@admin.register(InscriptionEnAttente)
class InscriptionEnAttenteAdmin(admin.ModelAdmin):
    list_display = ('email', 'nom', 'prenom', 'role', 'otp_expires_at', 'date_creation')
    list_filter = ('role', 'date_creation')
    search_fields = ('email', 'nom', 'prenom')
    readonly_fields = ('date_creation',)
    ordering = ('-date_creation',)

    def get_queryset(self, request):
        return super().get_queryset(request)



@admin.register(ConfigurationPartenaire)
class ConfigurationPartenaireAdmin(admin.ModelAdmin):
    """Admin pour la configuration des partenaires"""
    list_display = ('nom', 'actif', 'pourcentage_commission_default', 'seuil_retrait_minimum', 'montant_retrait_multiple', 'date_creation')
    list_filter = ('actif', 'date_creation')
    search_fields = ('nom',)
    readonly_fields = ('date_creation', 'date_modification')
    ordering = ('-date_creation',)
    
    fieldsets = (
        ('Configuration générale', {
            'fields': ('nom', 'description', 'actif')
        }),
        ('Paramètres de commission', {
            'fields': ('pourcentage_commission_default',),
            'classes': ('collapse',)
        }),
        ('Paramètres de retrait', {
            'fields': ('seuil_retrait_minimum', 'montant_retrait_multiple'),
            'classes': ('collapse',)
        }),
        ('Paramètres de paiement', {
            'fields': ('methodes_paiement_autorisees',),
            'classes': ('collapse',)
        }),
        ('Paramètres de traitement', {
            'fields': ('validation_automatique_retrait', 'delai_traitement_retrait_heures'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """S'assurer qu'une seule configuration est active à la fois"""
        if obj.actif:
            # Désactiver toutes les autres configurations
            ConfigurationPartenaire.objects.filter(actif=True).exclude(id=obj.id).update(actif=False)
        super().save_model(request, obj, form, change)


@admin.register(LienParentEnfant)
class LienParentEnfantAdmin(admin.ModelAdmin):
    list_display = ('parent', 'enfant', 'actif', 'date_creation')
    list_filter = ('actif', 'date_creation')
    search_fields = ('parent__email', 'parent__first_name', 'parent__last_name', 'enfant__email', 'enfant__first_name', 'enfant__last_name')
    readonly_fields = ('date_creation',)
    ordering = ['-date_creation']
    
    fieldsets = (
        ('Relation', {
            'fields': ('parent', 'enfant', 'actif')
        }),
        ('Dates', {
            'fields': ('date_creation',),
            'classes': ('collapse',)
        }),
    )
