# utilisateurs/management/commands/fake_0018.py

from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder

class Command(BaseCommand):
    help = 'Marque la migration 0018 comme appliquée (fake) pour éviter l\'erreur table existe déjà'

    def handle(self, *args, **options):
        MigrationRecorder.Migration.objects.filter(
            app='utilisateurs',
            name='0018_auto_20250912_1743'  # ← nom exact de la migration qui plante
        ).update(applied=True)

        self.stdout.write(self.style.SUCCESS('Migration utilisateurs.0018 marquée comme appliquée !'))