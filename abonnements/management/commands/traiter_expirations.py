"""
Commande Django pour traiter les abonnements expirés
Usage: python manage.py traiter_expirations
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from abonnements.services import ExpirationService


class Command(BaseCommand):
    help = 'Traite les abonnements expirés et les transfère vers le pack gratuit'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans modification des données',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'🔄 Traitement des expirations - {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
        )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('⚠️  MODE SIMULATION - Aucune modification ne sera apportée')
            )
        
        try:
            if options['dry_run']:
                # Mode simulation
                from abonnements.models import Abonnement
                
                abonnements_expires = Abonnement.objects.filter(
                    actif=True,
                    date_fin__lt=timezone.now(),
                    statut__in=['actif', 'essai']
                ).exclude(
                    pack__type_pack='gratuit'
                )
                
                self.stdout.write(f"📊 {abonnements_expires.count()} abonnements expirés trouvés")
                
                for abonnement in abonnements_expires:
                    self.stdout.write(
                        f"  - {abonnement.utilisateur.email}: {abonnement.pack.nom} "
                        f"(expiré le {abonnement.date_fin.strftime('%d/%m/%Y')})"
                    )
                
                self.stdout.write(
                    self.style.WARNING('🔄 Relancez sans --dry-run pour traiter les expirations')
                )
                
            else:
                # Traitement réel
                resultats = ExpirationService.verifier_et_traiter_expirations()
                
                self.stdout.write(f"📊 RÉSULTATS:")
                self.stdout.write(f"  ✅ Traités avec succès: {resultats['traites']}")
                self.stdout.write(f"  ❌ Erreurs: {resultats['erreurs']}")
                
                if options['verbose'] or resultats['erreurs'] > 0:
                    self.stdout.write(f"\n📋 DÉTAILS:")
                    for detail in resultats['details']:
                        if detail.startswith('✅'):
                            self.stdout.write(self.style.SUCCESS(detail))
                        else:
                            self.stdout.write(self.style.ERROR(detail))
                
                if resultats['traites'] > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"🎉 {resultats['traites']} utilisateurs transférés vers le pack gratuit"
                        )
                    )
                elif resultats['traites'] == 0 and resultats['erreurs'] == 0:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Aucun abonnement expiré à traiter")
                    )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erreur lors du traitement: {e}")
            )
            import traceback
            if options['verbose']:
                traceback.print_exc()
            raise e
        
        self.stdout.write(
            self.style.SUCCESS('✅ Traitement terminé')
        )
