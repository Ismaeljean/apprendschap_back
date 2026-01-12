# quiz/serializers.py
from rest_framework import serializers
from quiz.models import Quiz, QuestionQuiz, ReponseQuestion, TentativeQuiz, ReponseEtudiant

class ReponseQuestionSerializer(serializers.ModelSerializer):
    """Serializer pour les réponses aux questions"""
    class Meta:
        model = ReponseQuestion
        fields = ['id', 'texte_reponse', 'ordre']
        # Masquer est_correcte par défaut (sera exposé après soumission)


class ReponseQuestionAvecCorrectSerializer(serializers.ModelSerializer):
    """Serializer pour les réponses avec indication de correction"""
    class Meta:
        model = ReponseQuestion
        fields = ['id', 'texte_reponse', 'est_correcte', 'ordre']


class QuestionQuizSerializer(serializers.ModelSerializer):
    """Serializer pour les questions de quiz avec bonnes réponses"""
    reponses = ReponseQuestionAvecCorrectSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuestionQuiz
        fields = ['id', 'question', 'points', 'ordre', 'type_question', 'reponses', 'explication']


class QuestionQuizAvecExplicationSerializer(serializers.ModelSerializer):
    """Serializer pour les questions avec explications (après soumission)"""
    reponses = ReponseQuestionAvecCorrectSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuestionQuiz
        fields = ['id', 'question', 'explication', 'points', 'ordre', 'type_question', 'reponses']


class QuizSerializer(serializers.ModelSerializer):
    """Serializer pour les quiz"""
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    chapitre_titre = serializers.CharField(source='chapitre.titre', read_only=True)
    questions = QuestionQuizSerializer(many=True, read_only=True)
    meilleures_tentatives = serializers.SerializerMethodField()
    
    class Meta:
        model = Quiz
        fields = ['id', 'titre', 'description', 'matiere_nom', 
                 'chapitre', 'chapitre_titre', 'duree_minutes', 'nombre_questions', 
                 'note_passage', 'difficulte', 'tentatives_autorisees', 
                 'questions', 'meilleures_tentatives', 'actif']
    
    def get_meilleures_tentatives(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            tentatives = TentativeQuiz.objects.filter(
                etudiant=request.user,
                quiz=obj,
                termine=True
            ).order_by('-pourcentage')[:3]
            return [{
                'numero': t.numero_tentative,
                'pourcentage': t.pourcentage,
                'date': t.date_fin
            } for t in tentatives]
        return []


class TentativeQuizSerializer(serializers.ModelSerializer):
    """Serializer pour les tentatives de quiz"""
    quiz_titre = serializers.CharField(source='quiz.titre', read_only=True)
    matiere_nom = serializers.CharField(source='quiz.matiere.nom', read_only=True)
    reponses = serializers.SerializerMethodField()
    
    class Meta:
        model = TentativeQuiz
        fields = ['id', 'quiz', 'quiz_titre', 'matiere_nom', 'numero_tentative', 
                 'score', 'pourcentage', 'temps_ecoule', 'date_debut', 'date_fin', 
                 'termine', 'reponses']
    
    def get_reponses(self, obj):
        if obj.termine:
            return ReponseEtudiantSerializer(obj.reponses.all(), many=True).data
        return []


class ReponseEtudiantSerializer(serializers.ModelSerializer):
    """Serializer pour les réponses des étudiants"""
    question_texte = serializers.CharField(source='question.question', read_only=True)
    reponses_choisies_texte = serializers.SerializerMethodField()
    
    class Meta:
        model = ReponseEtudiant
        fields = ['id', 'question', 'question_texte', 'reponses_choisies', 
                 'reponses_choisies_texte', 'reponse_libre', 'temps_reponse', 
                 'correcte', 'points_obtenus']
    
    def get_reponses_choisies_texte(self, obj):
        return [r.texte_reponse for r in obj.reponses_choisies.all()]


class ReponseEtudiantSubmissionSerializer(serializers.Serializer):
    """Serializer pour une réponse d'étudiant lors de la soumission"""
    question_id = serializers.IntegerField()
    reponses_choisies = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    reponse_libre = serializers.CharField(required=False, allow_blank=True)
    temps_reponse = serializers.IntegerField(required=False, default=0)

class SoumissionQuizSerializer(serializers.Serializer):
    """Serializer pour soumettre une tentative de quiz"""
    quiz_id = serializers.IntegerField()
    tentative_id = serializers.IntegerField(required=False)
    reponses = ReponseEtudiantSubmissionSerializer(many=True)
    temps_ecoule = serializers.IntegerField(required=False, default=0)




