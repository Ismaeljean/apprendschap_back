# gamification/admin.py
from django.contrib import admin
from .models import Badge, BadgeEtudiant


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'condition_type', 'condition_valeur', 'points', 'nombre_obtenus')
    list_filter = ('condition_type', 'points')
    search_fields = ('nom', 'description')
    ordering = ('condition_type', 'condition_valeur')

    fieldsets = (
        ('Informations du badge', {
            'fields': ('nom', 'description')
        }),
        ('Conditions d\'obtention', {
            'fields': ('condition_type', 'condition_valeur', 'points')
        }),
    )

    def nombre_obtenus(self, obj):
        return obj.etudiants.count()
    nombre_obtenus.short_description = 'Nb obtenus'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('etudiants')

@admin.register(BadgeEtudiant)
class BadgeEtudiantAdmin(admin.ModelAdmin):
    list_display = ('etudiant', 'badge', 'date_obtention')
    list_filter = ('badge', 'date_obtention', 'badge__condition_type')
    search_fields = ('etudiant__email', 'badge__nom')
    readonly_fields = ('date_obtention',)
    ordering = ('-date_obtention',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etudiant', 'badge')