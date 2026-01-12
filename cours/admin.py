# cours/admin.py
from django.contrib import admin
from .models import Chapitre, ContenuChapitre
from django.utils.html import format_html


class ContenuChapitreInline(admin.TabularInline):
    model = ContenuChapitre
    extra = 1
    fields = ('ordre', 'titre', 'obligatoire', 'type_contenu_display')
    readonly_fields = ('type_contenu_display',)
    ordering = ('ordre',)
    
    def type_contenu_display(self, obj):
        """Affiche le type de contenu disponible"""
        if not obj.pk:  # Nouvel objet
            return '-'
        
        types = []
        if obj.fichier_pdf:
            types.append('📄 PDF')
        if obj.url_video:
            types.append('🎥 Vidéo')
        if obj.contenu_html:
            types.append('📝 HTML')
        return ' | '.join(types) if types else '❌ Aucun'
    type_contenu_display.short_description = 'Contenu'


@admin.register(Chapitre)
class ChapitreAdmin(admin.ModelAdmin):
    list_display = (
        'numero', 'titre', 'matiere', 'duree_estimee', 
        'difficulte_badge', 'actif', 'nombre_contenus'
    )
    list_filter = ('matiere__niveau', 'matiere', 'difficulte', 'actif')
    search_fields = ('titre', 'description')
    list_editable = ('actif',)
    inlines = [ContenuChapitreInline]
    ordering = ('matiere', 'numero')
    filter_horizontal = ('prerequis',)
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('matiere', 'titre', 'numero', 'description')
        }),
        ('Paramètres', {
            'fields': ('duree_estimee', 'difficulte', 'actif')
        }),
        ('Prérequis', {
            'fields': ('prerequis',),
            'classes': ('collapse',)
        }),
    )
    
    def nombre_contenus(self, obj):
        return obj.contenus.count()
    nombre_contenus.short_description = "Nb contenus"
    
    def difficulte_badge(self, obj):
        """Affiche la difficulté avec un badge coloré"""
        colors = {
            'facile': '#10b981',
            'moyen': '#f59e0b', 
            'difficile': '#ef4444'
        }
        color = colors.get(obj.difficulte, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_difficulte_display()
        )
    difficulte_badge.short_description = 'Difficulté'


@admin.register(ContenuChapitre)
class ContenuChapitreAdmin(admin.ModelAdmin):
    list_display = (
        'titre', 'chapitre', 'ordre', 'obligatoire', 
        'type_contenu_display', 'has_content'
    )
    list_filter = ('obligatoire', 'chapitre__matiere')
    search_fields = ('titre', 'description')
    ordering = ('chapitre', 'ordre')
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('chapitre', 'titre', 'description', 'ordre', 'obligatoire')
        }),
        ('Contenu (au moins un requis)', {
            'fields': ('fichier_pdf', 'url_video', 'contenu_html'),
            'description': 'Ajoutez au moins un type de contenu pour ce chapitre.'
        }),
    )
    
    def type_contenu_display(self, obj):
        """Affiche le type de contenu disponible"""
        types = []
        if obj.fichier_pdf:
            types.append('📄')
        if obj.url_video:
            types.append('🎥')
        if obj.contenu_html:
            types.append('📝')
        return ''.join(types) if types else '❌'
    type_contenu_display.short_description = 'Type'
    
    def has_content(self, obj):
        """Indique si le contenu a au moins un fichier/média"""
        return bool(obj.fichier_pdf or obj.url_video or obj.contenu_html)
    has_content.boolean = True
    has_content.short_description = 'Contenu'

