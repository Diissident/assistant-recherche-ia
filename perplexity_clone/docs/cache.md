# cache.py — Documentation

## Rôle
Cache disque minimal (fichiers JSON) pour éviter de refaire une recherche
web ou un scraping identique à court terme. Pas de dépendance externe
(pas de Redis, pas de base de données) — tout reste gratuit et simple.

## Fonctions

### `_key_to_path(key: str) -> str`
Fonction interne (préfixe `_`, non destinée à un usage externe).
Transforme une clé texte en un nom de fichier unique via un hash MD5,
pour éviter les problèmes de caractères spéciaux dans un nom de fichier.

- **Paramètre** `key` : la chaîne à hasher (ex: une requête de recherche)
- **Retour** : chemin complet du fichier de cache correspondant

### `get(key: str)`
Récupère une valeur en cache si elle existe et n'a pas expiré.

- **Paramètre** `key` : identifiant unique de la donnée recherchée
- **Retour** : la valeur stockée (dict, list, str...), ou `None` si absente
  ou expirée (durée définie par `CACHE_TTL_HOURS` dans `config.py`)
- **Effet de bord** : supprime automatiquement le fichier si expiré

### `set(key: str, value) -> None`
Stocke une valeur en cache avec un horodatage.

- **Paramètre** `key` : identifiant unique
- **Paramètre** `value` : donnée sérialisable en JSON
- **Retour** : aucun

## Limites connues
- Pas de gestion de concurrence (deux processus qui écrivent en même
  temps sur la même clé peuvent se marcher dessus). Sans conséquence
  pour un usage personnel mono-utilisateur.
- Le cache grossit indéfiniment ; prévoir un nettoyage manuel du dossier
  `cache_data/` de temps en temps, ou ajouter un script de purge si le
  projet grossit.
