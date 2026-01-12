from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from abonnements.models import Abonnement
from abonnements.services import ExpirationService

class Command(BaseCommand):
    help = 'Vérifie et traite les abonnements expirés'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Vérification des abonnements expirés...")
        
        # Utiliser le service d'expiration existant
        resultats = ExpirationService.verifier_et_traiter_expirations()
        
        self.stdout.write(f"📊 Résultats:")
        self.stdout.write(f"   ✅ Abonnements traités: {resultats['traites']}")
        self.stdout.write(f"   ❌ Erreurs: {resultats['erreurs']}")
        
        if resultats['details']:
            self.stdout.write("\n📝 Détails:")
            for detail in resultats['details']:
                self.stdout.write(f"   {detail}")
        
        self.stdout.write("\n🎉 Vérification terminée !")