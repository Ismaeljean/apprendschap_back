# ia/admin.py
from django.contrib import admin
from .models import MessageIA, ConversationIA


class MessageIAInline(admin.TabularInline):
    model = MessageIA
    extra = 0
    fields = ('expediteur', 'contenu_court', 'timestamp', 'lu')
    readonly_fields = ('timestamp', 'contenu_court')
    ordering = ('timestamp',)

    def contenu_court(self, obj):
        return obj.contenu[:100] + "..." if len(obj.contenu) > 100 else obj.contenu
    contenu_court.short_description = 'Contenu'

@admin.register(ConversationIA)
class ConversationIAAdmin(admin.ModelAdmin):
    list_display = ('etudiant', 'titre_auto', 'nombre_messages', 'active', 'date_creation', 'derniere_activite')
    list_filter = ('active', 'date_creation', 'derniere_activite')
    list_editable = ('active',)
    search_fields = ('etudiant__email', 'titre', 'session_id')
    readonly_fields = ('session_id', 'date_creation', 'derniere_activite')
    ordering = ('-derniere_activite',)
    inlines = [MessageIAInline]

    def titre_auto(self, obj):
        return obj.titre or f"Conversation du {obj.date_creation.strftime('%d/%m/%Y')}"
    titre_auto.short_description = 'Titre'

    def nombre_messages(self, obj):
        return obj.messages.count()
    nombre_messages.short_description = 'Nb messages'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etudiant').prefetch_related('messages')

@admin.register(MessageIA)
class MessageIAAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'expediteur', 'contenu', 'contexte_chapitre', 'timestamp', 'lu')
    list_filter = ('expediteur', 'lu', 'contexte_chapitre', 'timestamp')
    list_editable = ('lu',)
    search_fields = ('conversation__etudiant__email', 'contenu')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)

    def contenu_court(self, obj):
        return obj.contenu[:80] + "..." if len(obj.contenu) > 80 else obj.contenu
    contenu_court.short_description = 'Contenu'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'conversation__etudiant', 
            'contexte_chapitre'
        )
