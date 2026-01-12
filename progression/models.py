# progression/models.py
from django.db import models
from utilisateurs.models import Utilisateur
from cours.models import Chapitre
from academic_structure.models import Matiere
from cours.models import ContenuChapitre
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


class ProgressionChapitre(models.Model):
    """Progression des étudiants par chapitre"""
    etudiant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE)
    statut = models.CharField(max_length=20, choices=[
        ('non_commence', 'Non commencé'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('maitrise', 'Maîtrisé')
    ], default='non_commence')
    pourcentage_completion = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    temps_etudie = models.PositiveIntegerField(default=0)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_completion = models.DateTimeField(blank=True, null=True)

    # Ajouter au modèle ProgressionChapitre une méthode pour tracker les changements
    def save(self, *args, **kwargs):
        """Override save pour tracker les changements de statut"""
        # Tracker si c'est un changement vers 'termine'
        if self.pk:
            try:
                old_instance = ProgressionChapitre.objects.get(pk=self.pk)
                self._statut_precedent = old_instance.statut
            except ProgressionChapitre.DoesNotExist:
                self._statut_precedent = None
        else:
            self._statut_precedent = None
        
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['etudiant', 'chapitre']
        verbose_name = "Progression chapitre"
        verbose_name_plural = "Progressions chapitres"

    def __str__(self):
        return f"{self.etudiant.email} - {self.chapitre.titre}"


class ProgressionMatiere(models.Model):
    """Progression globale par matière (remplace ProgressionChapitre)"""
    etudiant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    statut = models.CharField(max_length=20, choices=[
        ('non_commence', 'Non commencé'),
        ('en_cours', 'En cours'), 
        ('termine', 'Terminé'),
        ('maitrise', 'Maîtrisé')
    ], default='non_commence')
    pourcentage_completion = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    temps_etudie_total = models.PositiveIntegerField(default=0, help_text="Temps total en secondes pour tous les chapitres de cette matière")
    nombre_chapitres_termines = models.PositiveIntegerField(default=0)
    nombre_chapitres_total = models.PositiveIntegerField(default=0)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_completion = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ['etudiant', 'matiere']
        verbose_name = "Progression matière"
        verbose_name_plural = "Progressions matières"

    def __str__(self):
        return f"{self.etudiant.email} - {self.matiere.nom}"

    def calculer_progression(self):
        """Calcule la progression basée sur les contenus et chapitres"""
        from cours.models import Chapitre
        
        # Récupérer tous les chapitres de cette matière
        chapitres = Chapitre.objects.filter(matiere=self.matiere)
        self.nombre_chapitres_total = chapitres.count()
        
        if self.nombre_chapitres_total == 0:
            self.pourcentage_completion = 0
            self.statut = 'non_commence'
            return
        
        # Calculer les stats basées sur les contenus lus
        contenus_lus = 0
        contenus_total = 0
        temps_total = 0
        chapitres_termines = 0
        
        for chapitre in chapitres:
            contenus_chapitre = ContenuChapitre.objects.filter(chapitre=chapitre)
            contenus_total += contenus_chapitre.count()
            
            # Compter les contenus lus pour ce chapitre
            progressions_contenu = ProgressionContenu.objects.filter(
                etudiant=self.etudiant,
                contenu__chapitre=chapitre
            )
            
            contenus_lus_chapitre = progressions_contenu.filter(lu=True).count()
            contenus_lus += contenus_lus_chapitre
            
            # Additionner le temps de lecture
            temps_chapitre = sum(p.temps_lecture for p in progressions_contenu)
            temps_total += temps_chapitre
            
            # Vérifier si le chapitre est terminé (tous ses contenus lus)
            if contenus_chapitre.count() > 0 and contenus_lus_chapitre == contenus_chapitre.count():
                chapitres_termines += 1
        
        # Mettre à jour les statistiques
        self.temps_etudie_total = temps_total
        self.nombre_chapitres_termines = chapitres_termines
        
        # Calculer le pourcentage basé sur les contenus
        if contenus_total > 0:
            self.pourcentage_completion = round((contenus_lus / contenus_total) * 100, 1)
        else:
            self.pourcentage_completion = 0
        
        # Déterminer le statut
        if self.pourcentage_completion == 0:
            self.statut = 'non_commence'
        elif self.pourcentage_completion == 100:
            self.statut = 'termine'
        else:
            self.statut = 'en_cours'


class ProgressionContenu(models.Model):
    """Progression détaillée par contenu"""
    etudiant = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    contenu = models.ForeignKey(ContenuChapitre, on_delete=models.CASCADE)
    lu = models.BooleanField(default=False)
    temps_lecture = models.PositiveIntegerField(default=0)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_completion = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ['etudiant', 'contenu']
        verbose_name = "Progression contenu"
        verbose_name_plural = "Progressions contenus"

    def __str__(self):
        return f"{self.etudiant.email} - {self.contenu.titre}"


@receiver(post_save, sender=ProgressionChapitre)
def progression_chapitre_saved(sender, instance, created, **kwargs):
    """Signal déclenché quand une progression de chapitre est sauvegardée"""
    
    # **PROTECTION CONTRE LES EMAILS MULTIPLES**
    # Envoyer email seulement si le statut vient de changer vers 'termine'
    statut_precedent = getattr(instance, '_statut_precedent', None)
    
    if (instance.statut == 'termine' and statut_precedent != 'termine'):
        # Envoyer une notification seulement lors du changement vers 'termine'
        try:
            from utilisateurs.services import envoyer_notification_email
            
            # Créer le message de notification
            sujet = f"🎉 Chapitre terminé - {instance.chapitre.matiere.nom}"
            message_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #10b981;">Félicitations !</h2>
                
                <div style="background-color: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #065f46; margin-top: 0;">📚 Chapitre terminé</h3>
                    <p><strong>Matière :</strong> {instance.chapitre.matiere.nom}</p>
                    <p><strong>Chapitre :</strong> {instance.chapitre.titre}</p>
                    <p><strong>Score :</strong> {instance.pourcentage_completion}%</p>
                    <p><strong>Temps d'étude :</strong> {instance.temps_etudie // 60} minutes</p>
                </div>
                
                <p style="color: #6b7280;">
                    Continuez vos efforts ! Chaque chapitre terminé vous rapproche de vos objectifs.
                </p>
                
                <a href="http://localhost:3000/progression.html" 
                   style="background-color: #10b981; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;">
                    Voir ma progression
                </a>
            </div>
            """
            
            # Envoyer la notification
            result = envoyer_notification_email(instance.etudiant, sujet, message_html)
            if result:
                print(f"✅ Email de chapitre terminé envoyé à {instance.etudiant.email}")
            else:
                print(f"ℹ️ Notifications désactivées pour {instance.etudiant.email}")
            
        except Exception as e:
            print(f"❌ Erreur notification chapitre terminé: {e}")
            
    # Mettre à jour la progression de la matière
    try:
        from .models import ProgressionMatiere
        
        # Récupérer ou créer la progression de matière
        progression_matiere, created = ProgressionMatiere.objects.get_or_create(
            etudiant=instance.etudiant,
            matiere=instance.chapitre.matiere
        )
        
        # Recalculer la progression
        progression_matiere.calculer_progression()
        progression_matiere.save()
        
    except Exception as e:
        print(f"❌ Erreur mise à jour progression matière: {e}")