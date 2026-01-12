# abonnements/admin.py
from django.contrib import admin
from .models import (
    PackAbonnement, Abonnement, PaiementWave, 
    PackFamilial, BonusParrainage, Parrainage, 
    HistoriqueRenouvellement, PackPermissions
)


@admin.register(PackAbonnement)
class PackAbonnementAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_pack', 'prix', 'periode', 'duree_jours', 'actif']
    list_filter = ['type_pack', 'periode', 'actif', 'pack_special']
    search_fields = ['nom', 'description']
    ordering = ['prix', 'duree_jours']


@admin.register(PackPermissions)
class PackPermissionsAdmin(admin.ModelAdmin):
    list_display = ['pack', 'max_cours_par_mois', 'max_quiz_par_mois', 'max_examens_par_mois', 'upgrade_reminder']
    list_filter = ['upgrade_reminder', 'teaser_content', 'restriction_temps', 'restriction_contenu']
    search_fields = ['pack__nom']
    ordering = ['pack__prix']


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'pack', 'statut', 'date_debut', 'date_fin', 'montant_paye', 'est_valide']
    list_filter = ['statut', 'actif', 'est_essai_gratuit', 'renouvellement_auto', 'pack__type_pack']
    search_fields = ['utilisateur__username', 'utilisateur__email', 'pack__nom']
    readonly_fields = ['jours_restants', 'pourcentage_utilise', 'est_valide']
    
    fieldsets = (
        ('Informations utilisateur', {
            'fields': ('utilisateur', 'pack')
        }),
        ('Période', {
            'fields': ('date_debut', 'date_fin', 'jours_restants', 'pourcentage_utilise')
        }),
        ('Statut et paiement', {
            'fields': ('statut', 'actif', 'montant_paye', 'est_valide')
        }),
        ('Options', {
            'fields': ('est_essai_gratuit', 'date_fin_essai', 'renouvellement_auto')
        }),
        ('Wave', {
            'fields': ('wave_transaction_id', 'wave_payment_status', 'wave_payment_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaiementWave)
class PaiementWaveAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'abonnement', 'montant', 'devise', 'statut', 'date_creation']
    list_filter = ['statut', 'devise', 'date_creation']
    search_fields = ['transaction_id', 'abonnement__utilisateur__username']
    readonly_fields = ['date_creation', 'date_mise_a_jour', 'est_reussi']
    
    fieldsets = (
        ('Transaction', {
            'fields': ('transaction_id', 'abonnement', 'montant', 'devise', 'statut')
        }),
        ('Informations Wave', {
            'fields': ('wave_reference', 'wave_phone', 'wave_email')
        }),
        ('Données', {
            'fields': ('callback_data', 'date_creation', 'date_mise_a_jour', 'est_reussi'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PackFamilial)
class PackFamilialAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_familial', 'nombre_enfants', 'prix', 'periode', 'duree_jours', 'reduction_pourcentage', 'actif']
    list_filter = ['type_familial', 'periode', 'actif', 'nombre_enfants', 'offre_semaine_gratuite']
    search_fields = ['nom', 'description']
    list_editable = ['actif', 'prix', 'reduction_pourcentage']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'type_familial', 'nombre_enfants', 'description', 'actif')
        }),
        ('Tarification', {
            'fields': ('prix', 'periode', 'duree_jours', 'reduction_pourcentage')
        }),
        ('Fonctionnalités', {
            'fields': ('offre_semaine_gratuite',)
        }),
        ('Options spéciales', {
            'fields': ('pack_familial', 'conditions_speciales')
        }),
    )


@admin.register(BonusParrainage)
class BonusParrainageAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'bonus_accumules', 'bonus_utilises', 'bonus_disponibles', 'peut_utiliser_bonus', 'date_dernier_bonus']
    list_filter = ['bonus_accumules', 'bonus_utilises', 'date_dernier_bonus']
    search_fields = ['utilisateur__email', 'utilisateur__first_name', 'utilisateur__last_name']
    readonly_fields = ['bonus_disponibles', 'peut_utiliser_bonus', 'date_dernier_bonus']
    
    fieldsets = (
        ('Utilisateur', {
            'fields': ('utilisateur',)
        }),
        ('Bonus', {
            'fields': ('bonus_accumules', 'bonus_utilises', 'bonus_disponibles', 'peut_utiliser_bonus')
        }),
        ('Dates', {
            'fields': ('date_dernier_bonus',)
        }),
    )


@admin.register(Parrainage)
class ParrainageAdmin(admin.ModelAdmin):
    list_display = ['parrain', 'filleul', 'code_parrainage', 'date_parrainage', 'bonus_attribue', 'filleul_bonus_attribue']
    list_filter = ['bonus_attribue', 'filleul_bonus_attribue', 'date_parrainage']
    search_fields = ['parrain__email', 'filleul__email', 'code_parrainage']
    readonly_fields = ['date_parrainage', 'date_filleul_bonus']
    
    fieldsets = (
        ('Relation de parrainage', {
            'fields': ('parrain', 'filleul', 'code_parrainage')
        }),
        ('Statut du bonus', {
            'fields': ('bonus_attribue', 'date_bonus_attribue')
        }),
        ('Bonus filleul', {
            'fields': ('filleul_bonus_attribue', 'date_filleul_bonus')
        }),
        ('Informations temporelles', {
            'fields': ('date_parrainage',)
        }),
    )


@admin.register(HistoriqueRenouvellement)
class HistoriqueRenouvellementAdmin(admin.ModelAdmin):
    list_display = ['abonnement', 'date_renouvellement', 'duree_ajoutee', 'montant_renouvellement']
    list_filter = ['date_renouvellement', 'duree_ajoutee']
    search_fields = ['abonnement__utilisateur__email', 'abonnement__pack__nom']
    readonly_fields = ['date_renouvellement']
    
    fieldsets = (
        ('Abonnement', {
            'fields': ('abonnement',)
        }),
        ('Renouvellement', {
            'fields': ('date_renouvellement', 'duree_ajoutee', 'montant_renouvellement')
        }),
    )



