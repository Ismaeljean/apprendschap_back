# progression/admin.py
from django.contrib import admin
from .models import ProgressionChapitre, ProgressionContenu, ProgressionMatiere
from django.utils.html import format_html


def marquer_comme_termine(modeladmin, request, queryset):
    """Action pour marquer plusieurs progressions comme terminées"""
    queryset.update(statut='termine', pourcentage_completion=100)
    modeladmin.message_user(
        request, 
        f"{queryset.count()} progression(s) marquée(s) comme terminée(s)."
    )
marquer_comme_termine.short_description = "Marquer comme terminé"


def reinitialiser_progression(modeladmin, request, queryset):
    """Action pour remettre à zéro les progressions"""
    queryset.update(
        statut='non_commence', 
        pourcentage_completion=0, 
        temps_etudie=0,
        date_completion=None
    )
    modeladmin.message_user(
        request, 
        f"{queryset.count()} progression(s) réinitialisée(s)."
    )
reinitialiser_progression.short_description = "Réinitialiser progression"


@admin.register(ProgressionChapitre)
class ProgressionChapitreAdmin(admin.ModelAdmin):
    list_display = (
        'etudiant', 'chapitre', 'statut', 'statut_badge', 'pourcentage_completion', 
        'temps_etudie_formatted', 'date_debut'
    )
    list_filter = (
        'statut', 'chapitre__matiere__niveau', 'chapitre__matiere', 
        'chapitre__difficulte', 'date_debut'
    )
    list_editable = ('statut',)
    search_fields = ('etudiant__email', 'etudiant__first_name', 'etudiant__last_name', 'chapitre__titre')
    readonly_fields = ('date_debut', 'temps_etudie_formatted')
    ordering = ('-date_debut',)
    actions = [marquer_comme_termine, reinitialiser_progression]
    list_per_page = 50

    fieldsets = (
        ('Étudiant et Chapitre', {
            'fields': ('etudiant', 'chapitre')
        }),
        ('Progression', {
            'fields': ('statut', 'pourcentage_completion', 'temps_etudie')
        }),
        ('Dates', {
            'fields': ('date_debut', 'date_completion'),
            'classes': ('collapse',)
        }),
    )

    def statut_badge(self, obj):
        """Affiche le statut avec un badge coloré"""
        colors = {
            'non_commence': '#9ca3af',
            'en_cours': '#3b82f6',
            'termine': '#10b981',
            'maitrise': '#8b5cf6'
        }
        color = colors.get(obj.statut, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_statut_display()
        )
    statut_badge.short_description = 'Statut'

    def temps_etudie_formatted(self, obj):
        """Formate le temps étudié (stocké en secondes)"""
        if obj.temps_etudie == 0:
            return "0s"
        
        # Convertir les secondes en heures, minutes, secondes
        heures = obj.temps_etudie // 3600
        minutes = (obj.temps_etudie % 3600) // 60
        secondes = obj.temps_etudie % 60
        
        if heures > 0:
            if minutes > 0:
                return f"{heures}h {minutes}m"
            else:
                return f"{heures}h"
        elif minutes > 0:
            if secondes > 0:
                return f"{minutes}m {secondes}s"
            else:
                return f"{minutes}m"
        else:
            return f"{secondes}s"
    temps_etudie_formatted.short_description = 'Temps étudié'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etudiant', 'chapitre__matiere'
        )


@admin.register(ProgressionContenu)
class ProgressionContenuAdmin(admin.ModelAdmin):
    list_display = (
        'etudiant', 'contenu', 'lu', 'lu_badge', 'temps_lecture_formatted', 'date_debut'
    )
    list_filter = (
        'lu', 'contenu__chapitre__matiere', 'contenu__obligatoire', 'date_debut'
    )
    list_editable = ('lu',)
    search_fields = (
        'etudiant__email', 'etudiant__first_name', 'etudiant__last_name', 
        'contenu__titre', 'contenu__chapitre__titre'
    )
    readonly_fields = ('date_debut', 'temps_lecture_formatted')
    ordering = ('-date_debut',)
    list_per_page = 100
    
    fieldsets = (
        ('Étudiant et Contenu', {
            'fields': ('etudiant', 'contenu')
        }),
        ('Progression', {
            'fields': ('lu', 'temps_lecture')
        }),
        ('Dates', {
            'fields': ('date_debut', 'date_completion'),
            'classes': ('collapse',)
        }),
    )

    def lu_badge(self, obj):
        """Affiche si le contenu est lu avec un badge"""
        if obj.lu:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">✓ Lu</span>'
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">Non lu</span>'
        )
    lu_badge.short_description = 'Lecture'

    def temps_lecture_formatted(self, obj):
        """Formate le temps de lecture (stocké en secondes)"""
        if not obj.temps_lecture or obj.temps_lecture == 0:
            return "0s"
        
        # Convertir les secondes en heures, minutes, secondes
        heures = obj.temps_lecture // 3600
        minutes = (obj.temps_lecture % 3600) // 60
        secondes = obj.temps_lecture % 60
        
        if heures > 0:
            if minutes > 0:
                return f"{heures}h {minutes}m"
            else:
                return f"{heures}h"
        elif minutes > 0:
            if secondes > 0:
                return f"{minutes}m {secondes}s"
            else:
                return f"{minutes}m"
        else:
            return f"{secondes}s"
    temps_lecture_formatted.short_description = 'Temps lecture'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etudiant', 
            'contenu__chapitre__matiere', 
        )


@admin.register(ProgressionMatiere)
class ProgressionMatiereAdmin(admin.ModelAdmin):
    list_display = (
        'etudiant', 'matiere', 'statut', 'statut_badge', 'pourcentage_completion_formatted',
        'chapitres_termines_total', 'temps_etudie_total_formatted', 'date_debut'
    )
    list_filter = (
        'statut', 'matiere__niveau', 'matiere', 'date_debut'
    )
    list_editable = ('statut',)
    search_fields = ('etudiant__email', 'etudiant__first_name', 'etudiant__last_name', 'matiere__nom')
    readonly_fields = (
        'date_debut', 'temps_etudie_total_formatted', 'chapitres_termines_total', 
        'pourcentage_completion_formatted'
    )
    ordering = ('-date_debut',)
    actions = [marquer_comme_termine, reinitialiser_progression]
    list_per_page = 30

    fieldsets = (
        ('Étudiant et Matière', {
            'fields': ('etudiant', 'matiere')
        }),
        ('Progression', {
            'fields': ('statut', 'pourcentage_completion', 'chapitres_termines_total')
        }),
        ('Temps et statistiques', {
            'fields': ('temps_etudie_total_formatted', 'nombre_chapitres_total'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_debut', 'date_completion'),
            'classes': ('collapse',)
        }),
    )

    def statut_badge(self, obj):
        """Affiche le statut avec un badge coloré"""
        colors = {
            'non_commence': '#9ca3af',
            'en_cours': '#3b82f6',
            'termine': '#10b981',
            'maitrise': '#8b5cf6'
        }
        color = colors.get(obj.statut, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_statut_display()
        )
    statut_badge.short_description = 'Statut'

    def pourcentage_completion_formatted(self, obj):
        """Affiche le pourcentage avec une barre de progression"""
        pourcentage = float(obj.pourcentage_completion or 0)
        color = '#10b981' if pourcentage >= 80 else '#3b82f6' if pourcentage >= 50 else '#f59e0b'
        pourcentage_str = f"{pourcentage:.1f}%"
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="background: #e5e7eb; width: 60px; height: 8px; border-radius: 4px; overflow: hidden;">'
            '<div style="background: {}; width: {}%; height: 100%;"></div>'
            '</div>'
            '<span style="font-weight: bold; color: {};">{}</span>'
            '</div>',
            color, pourcentage, color, pourcentage_str
        )
    pourcentage_completion_formatted.short_description = 'Progression'

    def chapitres_termines_total(self, obj):
        """Affiche chapitres terminés / total"""
        if obj.nombre_chapitres_total == 0:
            return "0/0"
        return format_html(
            '<span style="color: #10b981; font-weight: bold;">{}</span> / '
            '<span style="color: #6b7280;">{}</span>',
            obj.nombre_chapitres_termines, obj.nombre_chapitres_total
        )
    chapitres_termines_total.short_description = 'Chapitres'

    def temps_etudie_total_formatted(self, obj):
        """Formate le temps étudié total (stocké en secondes)"""
        if obj.temps_etudie_total == 0:
            return "0s"
        
        # Convertir les secondes en heures, minutes, secondes
        heures = obj.temps_etudie_total // 3600
        minutes = (obj.temps_etudie_total % 3600) // 60
        secondes = obj.temps_etudie_total % 60
        
        if heures > 0:
            if minutes > 0:
                return f"{heures}h {minutes}m"
            else:
                return f"{heures}h"
        elif minutes > 0:
            if secondes > 0:
                return f"{minutes}m {secondes}s"
            else:
                return f"{minutes}m"
        else:
            return f"{secondes}s"
    temps_etudie_total_formatted.short_description = 'Temps étudié'

    def save_model(self, request, obj, form, change):
        """Recalcule automatiquement la progression lors de la sauvegarde"""
        obj.calculer_progression()
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etudiant', 'matiere__niveau'
        )