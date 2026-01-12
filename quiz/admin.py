# quiz/admin.py
from django.contrib import admin
from .models import Quiz, QuestionQuiz, ReponseQuestion, TentativeQuiz, ReponseEtudiant

class ReponseQuestionInline(admin.TabularInline):
    model = ReponseQuestion
    extra = 2
    fields = ('texte_reponse', 'est_correcte', 'ordre')
    ordering = ('ordre',)

class QuestionQuizInline(admin.StackedInline):
    model = QuestionQuiz
    extra = 1
    fields = ('question', 'type_question', 'points', 'ordre', 'explication')
    ordering = ('ordre',)

def activer_quiz(modeladmin, request, queryset):
    queryset.update(actif=True)
activer_quiz.short_description = "Activer les quiz sélectionnés"

def desactiver_quiz(modeladmin, request, queryset):
    queryset.update(actif=False)
desactiver_quiz.short_description = "Désactiver les quiz sélectionnés"

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('titre', 'chapitre', 'get_matiere', 'nombre_questions', 'duree_minutes', 'difficulte', 'actif')
    list_filter = ('chapitre__matiere__niveau', 'chapitre__matiere', 'difficulte', 'actif')
    list_editable = ('actif',)
    search_fields = ('titre', 'description', 'chapitre__titre')
    ordering = ('chapitre__matiere__niveau__ordre', 'chapitre__numero')
    readonly_fields = ('date_creation',)
    inlines = [QuestionQuizInline]
    actions = [activer_quiz, desactiver_quiz]

    fieldsets = (
        ('Informations générales', {
            'fields': ('titre', 'description', 'chapitre')
        }),
        ('Paramètres du quiz', {
            'fields': ('duree_minutes', 'nombre_questions', 'note_passage', 'difficulte')
        }),
        ('Options avancées', {
            'fields': ('melanger_questions', 'melanger_reponses', 'tentatives_autorisees', 'actif'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation',),
            'classes': ('collapse',)
        }),
    )

    def get_matiere(self, obj):
        return obj.chapitre.matiere.nom
    get_matiere.short_description = 'Matière'
    get_matiere.admin_order_field = 'chapitre__matiere__nom'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('chapitre__matiere__niveau')

@admin.register(QuestionQuiz)
class QuestionQuizAdmin(admin.ModelAdmin):
    list_display = ('get_question_courte', 'quiz', 'type_question', 'points', 'ordre', 'nombre_reponses')
    list_filter = ('type_question', 'quiz__chapitre__matiere')
    list_editable = ('ordre', 'points')
    search_fields = ('question', 'quiz__titre')
    ordering = ('quiz__chapitre__matiere__niveau__ordre', 'quiz__id', 'ordre')
    inlines = [ReponseQuestionInline]

    def get_question_courte(self, obj):
        return obj.question[:60] + "..." if len(obj.question) > 60 else obj.question
    get_question_courte.short_description = 'Question'

    def nombre_reponses(self, obj):
        return obj.reponses.count()
    nombre_reponses.short_description = 'Nb réponses'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('quiz__chapitre__matiere').prefetch_related('reponses')

@admin.register(ReponseQuestion)
class ReponseQuestionAdmin(admin.ModelAdmin):
    list_display = ('get_reponse_courte', 'question', 'est_correcte', 'ordre')
    list_filter = ('est_correcte', 'question__quiz__chapitre__matiere')
    list_editable = ('est_correcte', 'ordre')
    search_fields = ('texte_reponse', 'question__question')
    ordering = ('question__quiz__id', 'question__ordre', 'ordre')

    def get_reponse_courte(self, obj):
        return obj.texte_reponse[:50] + "..." if len(obj.texte_reponse) > 50 else obj.texte_reponse
    get_reponse_courte.short_description = 'Réponse'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('question__quiz__chapitre__matiere')

@admin.register(TentativeQuiz)
class TentativeQuizAdmin(admin.ModelAdmin):
    list_display = ('etudiant', 'quiz', 'numero_tentative', 'score', 'pourcentage', 'termine', 'date_debut')
    list_filter = ('termine', 'quiz__chapitre__matiere', 'date_debut')
    search_fields = ('etudiant__email', 'quiz__titre')
    readonly_fields = ('date_debut', 'temps_ecoule_formatted')
    ordering = ('-date_debut',)

    def temps_ecoule_formatted(self, obj):
        if obj.temps_ecoule:
            minutes = obj.temps_ecoule // 60
            secondes = obj.temps_ecoule % 60
            return f"{minutes}min {secondes}s"
        return "Non défini"
    temps_ecoule_formatted.short_description = 'Temps écoulé'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etudiant', 'quiz__chapitre__matiere')

@admin.register(ReponseEtudiant)
class ReponseEtudiantAdmin(admin.ModelAdmin):
    list_display = ('tentative', 'question', 'correcte', 'points_obtenus', 'temps_reponse_formatted')
    list_filter = ('correcte', 'tentative__quiz__chapitre__matiere')
    search_fields = ('tentative__etudiant__email', 'question__question')
    readonly_fields = ('temps_reponse_formatted',)
    ordering = ('-tentative__date_debut',)

    def temps_reponse_formatted(self, obj):
        if obj.temps_reponse:
            return f"{obj.temps_reponse}s"
        return "Non défini"
    temps_reponse_formatted.short_description = 'Temps réponse'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tentative__etudiant', 
            'tentative__quiz', 
            'question'
        ).prefetch_related('reponses_choisies')

