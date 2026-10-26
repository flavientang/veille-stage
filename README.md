# Veille stage

Moteur de la veille quotidienne d'offres de stage (vente B2B tech, Europe hors France).

- `scan.py` : lit les pages carrière publiques (Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Recruitee) et Built In.
- `nouveaux.py` : ne garde que les offres jamais montrées (empreintes stockées dans Notion, page « Déjà vus »).
- `prefiltre.py` : écarte d'office les cas évidents et extrait les signaux (contrat, durée, langues).
- `companies.json`, `europe.regex` : sources et zone géographique.
- `regles.md` : copie des règles (la source de vérité est la page Notion « Règles »).
- `prompt_tache.md` : texte de la tâche planifiée quotidienne.
