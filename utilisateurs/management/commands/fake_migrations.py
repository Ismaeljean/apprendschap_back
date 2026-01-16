# utilisateurs/management/commands/fake_migrations.py
from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder

class Command(BaseCommand):
    help = 'Marque les migrations problématiques comme appliquées'

    def handle(self, *args, **options):
        MigrationRecorder.Migration.objects.filter(
            app='utilisateurs',
            name='0018_auto_20250912_1743'  # ← le nom de la migration qui plante
        ).update(applied=True)
        
        self.stdout.write(self.style.SUCCESS('Migration 0018 marquée comme appliquée !'))