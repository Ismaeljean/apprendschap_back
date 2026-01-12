# analytics/admin.py
from django.contrib import admin
from .models import StatistiqueGlobale


@admin.register(StatistiqueGlobale)
class StatistiqueGlobaleAdmin(admin.ModelAdmin):
    list_display = ('date_mise_a_jour', 'nombre_utilisateurs', 'nombre_chapitres_termines', 
                   'temps_etude_formatted', 'nombre_quiz_reussis', 'moyenne_generale')
    readonly_fields = ('date_mise_a_jour', 'temps_etude_formatted')
    ordering = ('-date_mise_a_jour',)

    fieldsets = (
        ('Statistiques utilisateurs', {
            'fields': ('nombre_utilisateurs', 'temps_etude_total', 'temps_etude_formatted')
        }),
        ('Statistiques apprentissage', {
            'fields': ('nombre_chapitres_termines', 'nombre_quiz_reussis', 'moyenne_generale')
        }),
        ('Métadonnées', {
            'fields': ('date_mise_a_jour',)
        }),
    )

    def temps_etude_formatted(self, obj):
        heures = obj.temps_etude_total // 60
        minutes = obj.temps_etude_total % 60
        return f"{heures}h {minutes}min"
    temps_etude_formatted.short_description = 'Temps étude total'

    def has_add_permission(self, request):
        # Limiter à une seule instance de statistiques
        return not StatistiqueGlobale.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False