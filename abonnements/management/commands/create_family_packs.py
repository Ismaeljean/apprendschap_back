from django.core.management.base import BaseCommand
from abonnements.models import PackAbonnement

class Command(BaseCommand):
    help = 'Crée les packs familiaux dans la base de données'

    def handle(self, *args, **options):
        # Packs familiaux à créer
        family_packs = [
            {
                'nom': 'Pack Famille 2 Enfants',
                'type_pack': 'famille',
                'description': 'Pack familial pour 2 enfants avec réduction de 20%',
                'prix': 2500,
                'periode': 'mois',
                'duree_jours': 30,
                'actif': True,
                'pack_special': False,
                'reduction_pourcentage': 20,
                'conditions_speciales': 'Pack familial - Accès pour le parent et 2 enfants',
                'offre_semaine_gratuite': False,
            },
            {
                'nom': 'Pack Famille 3 Enfants',
                'type_pack': 'famille',
                'description': 'Pack familial pour 3 enfants avec réduction de 25% - Le plus populaire',
                'prix': 4000,
                'periode': 'mois',
                'duree_jours': 30,
                'actif': True,
                'pack_special': False,
                'reduction_pourcentage': 25,
                'conditions_speciales': 'Pack familial - Accès pour le parent et 3 enfants',
                'offre_semaine_gratuite': False,
            },
            {
                'nom': 'Pack Famille 4 Enfants',
                'type_pack': 'famille',
                'description': 'Pack familial pour 4 enfants avec réduction de 30%',
                'prix': 5000,
                'periode': 'mois',
                'duree_jours': 30,
                'actif': True,
                'pack_special': False,
                'reduction_pourcentage': 30,
                'conditions_speciales': 'Pack familial - Accès pour le parent et 4 enfants',
                'offre_semaine_gratuite': False,
            },
        ]

        created_count = 0
        for pack_data in family_packs:
            pack, created = PackAbonnement.objects.get_or_create(
                nom=pack_data['nom'],
                defaults=pack_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Pack créé: {pack.nom} (ID: {pack.id})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Pack existe déjà: {pack.nom} (ID: {pack.id})')
                )

        self.stdout.write(
            self.style.SUCCESS(f'🎉 {created_count} nouveaux packs familiaux créés')
        )
