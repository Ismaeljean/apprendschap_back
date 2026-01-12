#!/usr/bin/env python3
"""
Commande de gestion pour vérifier et activer automatiquement les paiements Wave en attente
Usage: python manage.py verifier_paiements_wave
"""

from django.core.management.base import BaseCommand
from abonnements.services import WaveCallbackService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Vérifie et active automatiquement les paiements Wave en attente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer l\'activation de tous les paiements en attente',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔄 Vérification des paiements Wave en attente...')
        )
        
        try:
            # Vérifier les paiements en attente
            WaveCallbackService.verifier_paiements_en_attente()
            
            self.stdout.write(
                self.style.SUCCESS('✅ Vérification terminée avec succès')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de la vérification: {e}')
            )
            logger.error(f"Erreur dans verifier_paiements_wave: {e}")
