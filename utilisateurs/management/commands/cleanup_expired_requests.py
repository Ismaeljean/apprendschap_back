"""
Commande Django pour nettoyer automatiquement les demandes de parenté expirées.

Usage:
    python manage.py cleanup_expired_requests
    
Cette commande peut être exécutée via un cron job pour nettoyer automatiquement
les demandes expirées périodiquement.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from utilisateurs.models import DemandeParente


class Command(BaseCommand):
    help = 'Nettoie automatiquement les demandes de parenté expirées'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait supprimé sans effectuer les suppressions',
        )
        parser.add_argument(
            '--delete-expired',
            action='store_true',
            help='Supprime complètement les demandes expirées au lieu de juste les marquer',
        )

    def handle(self, *args, **options):
        """Exécute le nettoyage des demandes expirées."""
        
        self.stdout.write(self.style.HTTP_INFO('=== NETTOYAGE DES DEMANDES EXPIRÉES ==='))
        
        now = timezone.now()
        
        # Trouver toutes les demandes expirées non encore marquées
        demandes_a_expirer = DemandeParente.objects.filter(
            statut='en_attente',
            date_expiration__lt=now
        )
        
        # Trouver toutes les demandes déjà marquées comme expirées (pour suppression)
        demandes_expirees = DemandeParente.objects.filter(statut='expiree')
        
        self.stdout.write(f"📊 Demandes à marquer comme expirées: {demandes_a_expirer.count()}")
        self.stdout.write(f"📊 Demandes déjà expirées: {demandes_expirees.count()}")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 MODE DRY-RUN - Aucune modification effectuée'))
            
            if demandes_a_expirer.exists():
                self.stdout.write('\n📋 Demandes qui seraient marquées comme expirées:')
                for demande in demandes_a_expirer:
                    temps_expire = now - demande.date_expiration
                    self.stdout.write(
                        f"  - ID {demande.id}: {demande.parent.email} → {demande.enfant.email} "
                        f"(expirée depuis {temps_expire})"
                    )
            
            if options['delete_expired'] and demandes_expirees.exists():
                self.stdout.write('\n🗑️  Demandes qui seraient supprimées:')
                for demande in demandes_expirees:
                    self.stdout.write(
                        f"  - ID {demande.id}: {demande.parent.email} → {demande.enfant.email} "
                        f"(expirée le {demande.date_expiration})"
                    )
            
            return
        
        # Marquer les demandes expirées
        if demandes_a_expirer.exists():
            count_marked = demandes_a_expirer.update(
                statut='expiree',
                date_reponse=now
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ {count_marked} demandes marquées comme expirées')
            )
            
            # Afficher les détails
            for demande in demandes_a_expirer:
                temps_expire = now - demande.date_expiration
                self.stdout.write(
                    f"  ⏰ {demande.parent.email} → {demande.enfant.email} "
                    f"(expirée depuis {temps_expire})"
                )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Aucune demande en attente expirée trouvée'))
        
        # Supprimer les demandes expirées si demandé
        if options['delete_expired']:
            if demandes_expirees.exists():
                count_deleted = demandes_expirees.count()
                demandes_expirees.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'🗑️  {count_deleted} demandes expirées supprimées de la base')
                )
            else:
                self.stdout.write(self.style.SUCCESS('🗑️  Aucune demande expirée à supprimer'))
        
        # Statistiques finales
        self.stdout.write('\n📊 STATISTIQUES FINALES:')
        total_demandes = DemandeParente.objects.count()
        en_attente = DemandeParente.objects.filter(statut='en_attente').count()
        acceptees = DemandeParente.objects.filter(statut='acceptee').count()
        refusees = DemandeParente.objects.filter(statut='refusee').count()
        expirees = DemandeParente.objects.filter(statut='expiree').count()
        
        self.stdout.write(f"  Total: {total_demandes}")
        self.stdout.write(f"  En attente: {en_attente}")
        self.stdout.write(f"  Acceptées: {acceptees}")
        self.stdout.write(f"  Refusées: {refusees}")
        self.stdout.write(f"  Expirées: {expirees}")
        
        self.stdout.write(self.style.HTTP_INFO('=== NETTOYAGE TERMINÉ ==='))
