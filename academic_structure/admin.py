# academic_structure/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import NiveauScolaire, Matiere

@admin.register(NiveauScolaire)
class NiveauScolaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre', 'nombre_matieres')
    list_editable = ('ordre',)
    ordering = ('ordre',)
    
    def nombre_matieres(self, obj):
        return obj.matiere_set.count()
    nombre_matieres.short_description = "Nb matières"

@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ('nom', 'niveau', 'couleur_display', 'icone', 'ordre', 'active', 'nombre_chapitres')
    list_filter = ('niveau', 'active')
    list_editable = ('ordre', 'active')
    search_fields = ('nom', 'description')
    prepopulated_fields = {'slug': ('nom',)}
    ordering = ('niveau__ordre', 'ordre')
    
    def couleur_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px;"></div>',
            obj.couleur
        )
    couleur_display.short_description = "Couleur"
    
    def nombre_chapitres(self, obj):
        return obj.chapitres.count()
    nombre_chapitres.short_description = "Nb chapitres"