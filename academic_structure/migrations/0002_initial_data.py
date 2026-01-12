# academic_structure/migrations/0001_initial_data.py
from django.db import migrations
from django.utils.text import slugify


def forwards_func(apps, schema_editor):
    NiveauScolaire = apps.get_model('academic_structure', 'NiveauScolaire')
    Matiere = apps.get_model('academic_structure', 'Matiere')

    niveaux = [
        ("CP1", "Cours Préparatoire 1ère année"),
        ("CP2", "Cours Préparatoire 2ème année"),
        ("CE1", "Cours Élémentaire 1ère année"),
        ("CE2", "Cours Élémentaire 2ème année"),
        ("CM1", "Cours Moyen 1ère année"),
        ("CM2", "Cours Moyen 2ème année"),
        ("6ème", "Première année du collège"),
        ("5ème", "Deuxième année du collège"),
        ("4ème", "Troisième année du collège"),
        ("3ème", "Dernière année du collège"),
        ("2nde", "Seconde, première année du lycée"),
        ("1ère", "Première, deuxième année du lycée"),
        ("Terminale", "Dernière année du lycée"),
        ("Parent", "Profil parent pour suivi des élèves"),
    ]

    # Création des niveaux avec ordre
    nom_to_niveau = {}
    for idx, (nom, description) in enumerate(niveaux, start=1):
        niveau, _ = NiveauScolaire.objects.get_or_create(
            nom=nom,
            defaults={
                'ordre': idx,
                'description': description,
            }
        )
        # Met à jour ordre/description si nécessaire (idempotent)
        if niveau.ordre != idx or niveau.description != description:
            niveau.ordre = idx
            niveau.description = description
            niveau.save(update_fields=['ordre', 'description'])
        nom_to_niveau[nom] = niveau

    # Groupes de niveaux par cycle
    primaire_levels = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]
    college_levels = ["6ème", "5ème", "4ème", "3ème"]
    lycee_levels = ["2nde", "1ère", "Terminale"]

    # Matières par cycle (dans l'ordre voulu)
    matieres_par_niveau = {
        "Primaire": [
            "Mathématiques",
            "Sciences (SVT + Découverte du Monde)",
            "Français",
            "Anglais",
            "Histoire-Géographie",
            "Éducation Civique et Morale",
        ],
        "Collège": [
            "Français",
            "Anglais (LV1)",
            "Histoire-Géographie",
            "EDHC",
            "Mathématiques",
            "Physique-Chimie",
            "Sciences de la Vie et de la Terre (SVT)",
            "Technologies / TICE",
            "Culture générale",
        ],
        "Lycée": [
            "Français",
            "Anglais (LV1)",
            "Espagnol",
            "Allemand",
            "Mathématiques",
            "Physique-Chimie",
            "SVT",
            "Histoire-Géographie",
            "Philosophie",
        ],
    }

    # Icônes et couleurs (basés sur matieres.html)
    icon_color_by_subject = {
        # Primaire
        "Mathématiques": ("fas fa-calculator", "#667eea"),
        "Sciences (SVT + Découverte du Monde)": ("fas fa-flask", "#fa709a"),
        "Français": ("fas fa-feather-alt", "#f093fb"),
        "Anglais": ("fas fa-language", "#ffecd2"),
        "Histoire-Géographie": ("fas fa-globe", "#43e97b"),
        "Éducation Civique et Morale": ("fas fa-handshake", "#667eea"),
        # Collège
        "Anglais (LV1)": ("fas fa-language", "#ffecd2"),
        "EDHC": ("fas fa-balance-scale", "#667eea"),
        "Physique-Chimie": ("fas fa-atom", "#a8edea"),
        "Sciences de la Vie et de la Terre (SVT)": ("fas fa-dna", "#a1c4fd"),
        "Technologies / TICE": ("fas fa-microchip", "#a8edea"),
        "Culture générale": ("fas fa-landmark", "#4facfe"),
        # Lycée
        "Espagnol": ("fas fa-language", "#ffecd2"),
        "Allemand": ("fas fa-language", "#ffecd2"),
        "SVT": ("fas fa-microscope", "#a1c4fd"),
        "Philosophie": ("fas fa-brain", "#667eea"),
    }

    # Descriptions génériques inspirées de vos pages
    description_by_subject = {
        "Mathématiques": "Nombres, calculs, géométrie, statistiques et probabilités.",
        "Sciences (SVT + Découverte du Monde)": "Monde vivant, matière, technologie et environnement.",
        "Français": "Lecture, écriture, grammaire, littérature et expression.",
        "Anglais": "Initiation/approfondissement du vocabulaire et des expressions.",
        "Histoire-Géographie": "Repères historiques, enjeux géographiques et territoires.",
        "Éducation Civique et Morale": "Vivre ensemble, respect, droits et devoirs.",
        "Anglais (LV1)": "Compréhension, expression orale/écrite et lexique.",
        "EDHC": "Droits, citoyenneté, institutions et responsabilité.",
        "Physique-Chimie": "Phénomènes physiques et réactions chimiques.",
        "Sciences de la Vie et de la Terre (SVT)": "Organismes vivants, géologie et méthodes expérimentales.",
        "Technologies / TICE": "Culture numérique, algorithmique, sécurité et usages responsables.",
        "Culture générale": "Histoire de l’art, sciences et actualités adaptées.",
        "Espagnol": "Communication, grammaire et civilisation hispanophone.",
        "Allemand": "Structures de la langue, compréhension et expression.",
        "SVT": "Biologie cellulaire, génétique et géologie.",
        "Philosophie": "Réflexion critique et grands courants de pensée.",
    }

    # Génération des matières pour chaque niveau
    cycles = [
        ("Primaire", primaire_levels),
        ("Collège", college_levels),
        ("Lycée", lycee_levels),
    ]

    for cycle_name, level_names in cycles:
        subjects = matieres_par_niveau[cycle_name]
        for level_name in level_names:
            niveau = nom_to_niveau[level_name]
            for ordre_idx, subject_name in enumerate(subjects, start=1):
                icon, color = icon_color_by_subject.get(subject_name, ("fas fa-book", "#4f46e5"))
                description = description_by_subject.get(subject_name, subject_name)

                base_slug = slugify(subject_name)
                slug = f"{base_slug}-{slugify(level_name)}"

                # Ajustement des correspondances de nom selon cycle (ex: SVT au lycée)
                stored_name = subject_name
                if subject_name == "SVT":
                    stored_name = "SVT"
                # "Anglais (LV1)" et "Anglais" restent distincts

                Matiere.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "nom": stored_name,
                        "description": description,
                        "icone": icon,
                        "couleur": color,
                        "niveau": niveau,
                        "ordre": ordre_idx,
                        "active": True,
                    }
                )

    # Aucun contenu pour "Parent"


def reverse_func(apps, schema_editor):
    NiveauScolaire = apps.get_model('academic_structure', 'NiveauScolaire')
    Matiere = apps.get_model('academic_structure', 'Matiere')

    primaire_levels = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]
    college_levels = ["6ème", "5ème", "4ème", "3ème"]
    lycee_levels = ["2nde", "1ère", "Terminale"]

    matieres_par_niveau = {
        "Primaire": [
            "Mathématiques",
            "Sciences (SVT + Découverte du Monde)",
            "Français",
            "Anglais",
            "Histoire-Géographie",
            "Éducation Civique et Morale",
        ],
        "Collège": [
            "Français",
            "Anglais (LV1)",
            "Histoire-Géographie",
            "EDHC",
            "Mathématiques",
            "Physique-Chimie",
            "Sciences de la Vie et de la Terre (SVT)",
            "Technologies / TICE",
            "Culture générale",
        ],
        "Lycée": [
            "Français",
            "Anglais (LV1)",
            "Espagnol",
            "Allemand",
            "Mathématiques",
            "Physique-Chimie",
            "SVT",
            "Histoire-Géographie",
            "Philosophie",
        ],
    }

    cycles = [
        ("Primaire", primaire_levels),
        ("Collège", college_levels),
        ("Lycée", lycee_levels),
    ]

    # Supprimer d'abord les matières
    for _, level_names in cycles:
        for level_name in level_names:
            for subject_name in (
                matieres_par_niveau["Primaire"]
                + matieres_par_niveau["Collège"]
                + matieres_par_niveau["Lycée"]
            ):
                base_slug = slugify(subject_name)
                slug = f"{base_slug}-{slugify(level_name)}"
                Matiere.objects.filter(slug=slug).delete()

    # Puis supprimer les niveaux créés
    for nom in primaire_levels + college_levels + lycee_levels + ["Parent"]:
        NiveauScolaire.objects.filter(nom=nom).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('academic_structure', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]

 