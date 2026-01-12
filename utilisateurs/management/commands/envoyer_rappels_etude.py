# utilisateurs/management/commands/envoyer_rappels_etude.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from utilisateurs.services import envoyer_rappel_etude
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Envoie les rappels d\'étude quotidiens aux utilisateurs qui les ont activés'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait envoyé sans envoyer réellement',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('Mode DRY-RUN activé - Aucun email ne sera envoyé')
            )
        
        # Récupérer tous les utilisateurs avec des préférences
        users_with_preferences = User.objects.filter(
            preferences__rappels_etude=True
        ).select_related('preferences')
        
        self.stdout.write(f"Trouvé {users_with_preferences.count()} utilisateurs avec rappels d'étude activés")
        
        emails_envoyes = 0
        erreurs = 0
        
        for user in users_with_preferences:
            try:
                if dry_run:
                    self.stdout.write(
                        f"DRY-RUN: Envoi de rappel d'étude à {user.email}"
                    )
                    emails_envoyes += 1
                else:
                    # Vérifier si un rappel a déjà été envoyé aujourd'hui
                    from utilisateurs.models import LogRappelEtude
                    
                    aujourd_hui = timezone.now().date()
                    rappel_existant = LogRappelEtude.objects.filter(
                        utilisateur=user,
                        date_envoi__date=aujourd_hui
                    ).exists()
                    
                    if not rappel_existant:
                        # Envoyer le rappel
                        if envoyer_rappel_etude(user):
                            # Logger l'envoi
                            LogRappelEtude.objects.create(
                                utilisateur=user,
                                date_envoi=timezone.now()
                            )
                            emails_envoyes += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"Rappel envoyé à {user.email}")
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(f"Échec de l'envoi à {user.email}")
                            )
                            erreurs += 1
                    else:
                        self.stdout.write(
                            f"Rappel déjà envoyé aujourd'hui à {user.email}"
                        )
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Erreur pour {user.email}: {str(e)}")
                )
                erreurs += 1
        
        # Résumé
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY-RUN terminé: {emails_envoyes} rappels seraient envoyés'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Terminé: {emails_envoyes} rappels envoyés, {erreurs} erreurs'
                )
            )
