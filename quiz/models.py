# quiz/models.py
from django.db import models
from cours.models import Chapitre
from utilisateurs.models import Utilisateur
from django.db.models.signals import post_save
from django.dispatch import receiver

class Quiz(models.Model):
    """Quiz liés aux chapitres"""
    titre = models.CharField(max_length=200)
    description = models.TextField()
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name='quiz')
    duree_minutes = models.PositiveIntegerField()
    nombre_questions = models.PositiveIntegerField()
    note_passage = models.FloatField(default=50.0)
    difficulte = models.CharField(max_length=20, choices=[
        ('facile', 'Facile'),
        ('moyen', 'Moyen'),
        ('difficile', 'Difficile')
    ])
    melanger_questions = models.BooleanField(default=True)
    melanger_reponses = models.BooleanField(default=True)
    tentatives_autorisees = models.PositiveIntegerField(default=3)
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.titre
    
    @property
    def matiere(self):
        """Accès à la matière via le chapitre"""
        return self.chapitre.matiere

class QuestionQuiz(models.Model):
    """Questions des quiz"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    explication = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=1)
    ordre = models.PositiveIntegerField(default=0)
    type_question = models.CharField(max_length=20, choices=[
        ('choix_unique', 'Choix unique'),
        ('choix_multiple', 'Choix multiple'),
        ('vrai_faux', 'Vrai/Faux'),
        ('texte_libre', 'Texte libre')
    ], default='choix_unique')

    class Meta:
        ordering = ['quiz', 'ordre']

    def __str__(self):
        return f"{self.quiz.titre} - Q{self.ordre}"

class ReponseQuestion(models.Model):
    """Réponses possibles aux questions"""
    question = models.ForeignKey(QuestionQuiz, on_delete=models.CASCADE, related_name='reponses')
    texte_reponse = models.TextField()
    est_correcte = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['question', 'ordre']

    def __str__(self):
        return f"{self.question} - {self.texte_reponse[:50]}"


class TentativeQuiz(models.Model):
    """Tentatives de quiz par les étudiants"""
    etudiant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    numero_tentative = models.PositiveIntegerField()
    score = models.FloatField(blank=True, null=True)
    pourcentage = models.FloatField(blank=True, null=True)
    temps_ecoule = models.PositiveIntegerField(blank=True, null=True)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(blank=True, null=True)
    termine = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """Override save pour tracker les changements de statut"""
        # Tracker si c'est un changement vers 'termine'
        if self.pk:
            try:
                old_instance = TentativeQuiz.objects.get(pk=self.pk)
                self._termine_precedent = old_instance.termine
            except TentativeQuiz.DoesNotExist:
                self._termine_precedent = False
        else:
            self._termine_precedent = False
        
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['etudiant', 'quiz', 'numero_tentative']
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.etudiant.email} - {self.quiz.titre} (Tentative {self.numero_tentative})"



class ReponseEtudiant(models.Model):
    """Réponses données par les étudiants"""
    tentative = models.ForeignKey(TentativeQuiz, on_delete=models.CASCADE, related_name='reponses')
    question = models.ForeignKey(QuestionQuiz, on_delete=models.CASCADE)
    reponses_choisies = models.ManyToManyField(ReponseQuestion, blank=True)
    reponse_libre = models.TextField(blank=True)
    temps_reponse = models.PositiveIntegerField(blank=True, null=True)
    correcte = models.BooleanField(blank=True, null=True)
    points_obtenus = models.FloatField(default=0)

    class Meta:
        unique_together = ['tentative', 'question']
        
    def __str__(self):
        return f"Réponse de {self.tentative.etudiant.email} - {self.question}"


@receiver(post_save, sender=TentativeQuiz)
def tentative_quiz_terminee(sender, instance, created, **kwargs):
    """Signal déclenché quand une tentative de quiz est sauvegardée"""
    
    # **PROTECTION CONTRE LES EMAILS MULTIPLES**
    # Envoyer email seulement si le quiz vient d'être terminé
    termine_precedent = getattr(instance, '_termine_precedent', False)
    
    if (instance.termine and not termine_precedent and instance.pourcentage >= instance.quiz.note_passage):
        try:
            from utilisateurs.services import envoyer_notification_quiz
            
            # Envoyer notification pour quiz réussi
            result = envoyer_notification_quiz(instance.etudiant, instance.quiz, instance.pourcentage)
            if result:
                print(f"✅ Notification quiz réussi envoyée à {instance.etudiant.email}")
            else:
                print(f"ℹ️ Notifications quiz désactivées pour {instance.etudiant.email}")
                
        except Exception as e:
            print(f"❌ Erreur notification quiz: {e}")
        