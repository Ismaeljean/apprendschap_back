from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from abonnements.models import Abonnement
from datetime import timedelta

class Command(BaseCommand):
    help = 'Nettoie et corrige les abonnements incohérents'

    def handle(self, *args, **options):
        self.stdout.write("🧹 Début du nettoyage des abonnements...")
        
        # 1. Désactiver tous les abonnements expirés
        maintenant = timezone.now()
        abonnements_expires = Abonnement.objects.filter(
            actif=True,
            date_fin__lt=maintenant,
            statut__in=['actif', 'essai']
        ).exclude(
            pack__type_pack='gratuit'  # Ne pas traiter les packs gratuits
        )
        
        self.stdout.write(f"📅 {abonnements_expires.count()} abonnements expirés trouvés")
        
        with transaction.atomic():
            for abonnement in abonnements_expires:
                abonnement.actif = False
                abonnement.statut = 'expire'
                abonnement.save()
                self.stdout.write(f"   ✅ {abonnement.utilisateur.email} - {abonnement.pack.nom} (expiré le {abonnement.date_fin.strftime('%d/%m/%Y')})")
        
        # 2. Identifier et corriger les abonnements multiples actifs pour le même utilisateur
        self.stdout.write("\n🔍 Recherche des abonnements multiples actifs...")
        
        # Grouper par utilisateur
        from django.db.models import Count
        utilisateurs_multiples = Abonnement.objects.filter(
            actif=True,
            statut__in=['actif', 'essai']
        ).values('utilisateur').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        self.stdout.write(f"👥 {utilisateurs_multiples.count()} utilisateurs avec des abonnements multiples")
        
        for user_data in utilisateurs_multiples:
            utilisateur_id = user_data['utilisateur']
            abonnements_actifs = Abonnement.objects.filter(
                utilisateur_id=utilisateur_id,
                actif=True,
                statut__in=['actif', 'essai']
            ).order_by('-date_debut')
            
            # Garder seulement le plus récent, désactiver les autres
            abonnement_principal = abonnements_actifs.first()
            abonnements_a_desactiver = abonnements_actifs[1:]
            
            self.stdout.write(f"\n👤 {abonnement_principal.utilisateur.email}:")
            self.stdout.write(f"   ✅ Garde: {abonnement_principal.pack.nom} (début: {abonnement_principal.date_debut.strftime('%d/%m/%Y')})")
            
            for abonnement in abonnements_a_desactiver:
                abonnement.actif = False
                abonnement.statut = 'remplace'
                abonnement.save()
                self.stdout.write(f"   ❌ Désactivé: {abonnement.pack.nom} (début: {abonnement.date_debut.strftime('%d/%m/%Y')})")
        
        # 3. Corriger les abonnements avec des dates incohérentes
        self.stdout.write("\n📅 Correction des dates incohérentes...")
        
        abonnements_a_corriger = Abonnement.objects.filter(
            actif=True,
            statut__in=['actif', 'essai']
        ).exclude(
            pack__type_pack='gratuit'
        )
        
        for abonnement in abonnements_a_corriger:
            # Vérifier si la date de fin est cohérente avec la durée du pack
            if abonnement.date_debut and abonnement.pack.duree_jours:
                date_fin_calculee = abonnement.date_debut + timedelta(days=abonnement.pack.duree_jours)
                
                # Si la date de fin ne correspond pas, la corriger
                if abonnement.date_fin != date_fin_calculee:
                    ancienne_date = abonnement.date_fin
                    abonnement.date_fin = date_fin_calculee
                    abonnement.save()
                    self.stdout.write(f"   🔧 {abonnement.utilisateur.email} - {abonnement.pack.nom}: {ancienne_date.strftime('%d/%m/%Y')} → {date_fin_calculee.strftime('%d/%m/%Y')}")
        
        # 4. Statistiques finales
        self.stdout.write("\n📊 Statistiques finales:")
        total_actifs = Abonnement.objects.filter(actif=True).count()
        total_expires = Abonnement.objects.filter(statut='expire').count()
        total_remplaces = Abonnement.objects.filter(statut='remplace').count()
        
        self.stdout.write(f"   ✅ Abonnements actifs: {total_actifs}")
        self.stdout.write(f"   ❌ Abonnements expirés: {total_expires}")
        self.stdout.write(f"   🔄 Abonnements remplacés: {total_remplaces}")
        
        # 5. Afficher les abonnements actifs restants
        self.stdout.write("\n👥 Abonnements actifs restants:")
        abonnements_actifs = Abonnement.objects.filter(actif=True).select_related('utilisateur', 'pack')
        
        for abonnement in abonnements_actifs:
            jours_restants = "Illimité"
            if abonnement.date_fin:
                jours_restants = (abonnement.date_fin - maintenant).days
                jours_restants = f"{jours_restants} jours" if jours_restants > 0 else "Expiré"
            
            self.stdout.write(f"   • {abonnement.utilisateur.email} - {abonnement.pack.nom} - {jours_restants}")
        
        self.stdout.write("\n🎉 Nettoyage terminé !")
