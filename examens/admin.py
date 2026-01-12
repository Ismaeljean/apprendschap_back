# examens/admin.py
from django.contrib import admin
from .models import TypeExamen, Examen


def activer_examens(modeladmin, request, queryset):
    queryset.update(actif=True)
activer_examens.short_description = "Activer les examens sélectionnés"


def desactiver_examens(modeladmin, request, queryset):
    queryset.update(actif=False)
desactiver_examens.short_description = "Désactiver les examens sélectionnés"


@admin.register(TypeExamen)
class TypeExamenAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'nombre_examens')
    search_fields = ('nom', 'description')
    ordering = ('nom',)

    def nombre_examens(self, obj):
        return obj.examens.count()  # ✅ Utilise le related_name défini
    nombre_examens.short_description = 'Nb examens'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('examens')  # ✅ Plus lisible


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    list_display = (
        'titre', 'matiere', 'type_examen', 'annee', 'session',
        'duree_heures', 'nombre_telechargements', 'actif'
    )
    list_filter = (
        'type_examen', 'matiere__niveau', 'matiere', 'annee',
        'session', 'difficulte', 'actif'
    )
    list_editable = ('actif',)
    search_fields = ('titre', 'description', 'matiere__nom')
    readonly_fields = ('date_ajout', 'nombre_telechargements')
    ordering = ('-annee', 'matiere__nom', 'session')
    actions = [activer_examens, desactiver_examens]

    fieldsets = (
        ('Informations générales', {
            'fields': ('titre', 'matiere', 'type_examen', 'description')
        }),
        ('Paramètres examen', {
            'fields': ('annee', 'session', 'duree_heures', 'points_total', 'difficulte')
        }),
        ('Fichiers', {
            'fields': ('fichier_sujet', 'fichier_correction')
        }),
        ('Statistiques', {
            'fields': ('nombre_telechargements', 'actif', 'date_ajout'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('matiere__niveau', 'type_examen')
