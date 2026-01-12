# utilisateurs/services.py
import random
from django.core.mail import send_mail

def generer_otp():
    return str(random.randint(100000, 999999))


def envoyer_otp_email(email, otp):
    sujet = "Code de confirmation de votre inscription"
    message = f"Bonjour,\n\nVoici votre code de confirmation : {otp}\n\nMerci de l'entrer pour finaliser votre inscription."
    send_mail(sujet, message, 'no-reply@apprendschap.com', [email])


def envoyer_otp_reinitialisation(email, otp):
    sujet = "Code de réinitialisation de votre mot de passe"
    message = f"Bonjour,\n\nVoici votre code de réinitialisation : {otp}\n\nMerci de l'entrer pour finaliser la réinitialisation de votre mot de passe."
    send_mail(sujet, message, "no-reply@apprendschap.com", [email])

# ===============================
# SERVICES DE NOTIFICATIONS
# ===============================

def envoyer_notification_email(utilisateur, sujet, message_html, message_texte=None):
    """
    Envoyer une notification par email à l'utilisateur
    """
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings
        
        # Vérifier si l'utilisateur a activé les notifications email
        if hasattr(utilisateur, 'preferences') and utilisateur.preferences.notifications_email:
            # Envoyer l'email
            send_mail(
                subject=sujet,
                message=message_texte or message_html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[utilisateur.email],
                html_message=message_html,
                fail_silently=False
            )
            return True
        return False
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")
        return False

def envoyer_rappel_etude(utilisateur):
    """
    Envoyer un rappel d'étude quotidien
    """
    try:
        from progression.models import ProgressionChapitre
        from django.utils import timezone
        from datetime import timedelta
        
        # Vérifier si l'utilisateur a activé les rappels d'étude
        if not hasattr(utilisateur, 'preferences') or not utilisateur.preferences.rappels_etude:
            return False
        
        # Calculer les statistiques d'étude
        aujourd_hui = timezone.now().date()
        hier = aujourd_hui - timedelta(days=1)
        
        # Progression d'hier
        progression_hier = ProgressionChapitre.objects.filter(
            etudiant=utilisateur,
            date_debut__date=hier
        ).count()
        
        # Progression totale
        progression_totale = ProgressionChapitre.objects.filter(
            etudiant=utilisateur,
            statut='termine'
        ).count()
        
        # Créer le message de rappel
        sujet = "📚 Rappel d'étude quotidien - ApprendsChap"
        
        message_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Bonjour {utilisateur.first_name} !</h2>
            
            <p>Voici votre rappel d'étude quotidien :</p>
            
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #1f2937; margin-top: 0;">📊 Votre progression</h3>
                <ul style="color: #374151;">
                    <li><strong>Hier :</strong> {progression_hier} chapitre(s) étudié(s)</li>
                    <li><strong>Total :</strong> {progression_totale} chapitre(s) terminé(s)</li>
                </ul>
            </div>
            
            <p style="color: #6b7280;">
                Continuez vos efforts ! Chaque jour compte dans votre apprentissage.
            </p>
            
            <a href="http://localhost:3000/progression.html" 
               style="background-color: #2563eb; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 6px; display: inline-block;">
                Voir ma progression
            </a>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
            <p style="color: #9ca3af; font-size: 12px;">
                Cet email a été envoyé automatiquement par ApprendsChap.<br>
                Pour désactiver ces rappels, modifiez vos préférences dans votre profil.
            </p>
        </div>
        """
        
        message_texte = f"""
        Bonjour {utilisateur.first_name} !
        
        Voici votre rappel d'étude quotidien :
        
        Votre progression :
        - Hier : {progression_hier} chapitre(s) étudié(s)
        - Total : {progression_totale} chapitre(s) terminé(s)
        
        Continuez vos efforts ! Chaque jour compte dans votre apprentissage.
        
        Voir ma progression : http://localhost:3000/progression.html
        
        ---
        Cet email a été envoyé automatiquement par ApprendsChap.
        Pour désactiver ces rappels, modifiez vos préférences dans votre profil.
        """
        
        return envoyer_notification_email(utilisateur, sujet, message_html, message_texte)
        
    except Exception as e:
        print(f"Erreur lors de l'envoi du rappel d'étude: {e}")
        return False

def envoyer_notification_quiz(utilisateur, quiz, score):
    """
    Envoyer une notification de quiz terminé
    """
    try:
        if not hasattr(utilisateur, 'preferences') or not utilisateur.preferences.notification_quiz:
            return False
        
        sujet = f"🎯 Quiz terminé - {quiz.chapitre.matiere.nom}"
        
        message_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Quiz terminé !</h2>
            
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #1f2937; margin-top: 0;">📝 Résultats</h3>
                <p><strong>Matière :</strong> {quiz.chapitre.matiere.nom}</p>
                <p><strong>Chapitre :</strong> {quiz.chapitre.titre}</p>
                <p><strong>Score :</strong> {score}%</p>
            </div>
            
            <p style="color: #6b7280;">
                Continuez à pratiquer pour améliorer vos résultats !
            </p>
        </div>
        """
        
        return envoyer_notification_email(utilisateur, sujet, message_html)
        
    except Exception as e:
        print(f"Erreur lors de l'envoi de la notification quiz: {e}")
        return False

def envoyer_notification_badge(utilisateur, badge):
    """
    Envoyer une notification de badge obtenu
    """
    try:
        if not hasattr(utilisateur, 'preferences') or not utilisateur.preferences.notification_badge:
            return False
        
        sujet = f"🏆 Nouveau badge obtenu - {badge.nom}"
        
        message_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #f59e0b;">Félicitations !</h2>
            
            <div style="background-color: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #92400e; margin-top: 0;">🏆 Nouveau badge</h3>
                <p><strong>Badge :</strong> {badge.nom}</p>
                <p><strong>Description :</strong> {badge.description}</p>
            </div>
            
            <p style="color: #6b7280;">
                Continuez vos efforts pour débloquer plus de badges !
            </p>
        </div>
        """
        
        return envoyer_notification_email(utilisateur, sujet, message_html)
        
    except Exception as e:
        print(f"Erreur lors de l'envoi de la notification badge: {e}")
        return False