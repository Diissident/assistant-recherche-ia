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

MD5 est utilisé ici comme simple fonction de nommage, sans enjeu de sécurité —
d'où `usedforsecurity=False`, qui l'indique explicitement (audits de sécurité,
environnements FIPS).

### `get(key: str, default=None)`
Récupère une valeur en cache si elle existe et n'a pas expiré.

- **Paramètre** `key` : identifiant unique de la donnée recherchée
- **Paramètre** `default` : valeur retournée en cas d'absence
- **Retour** : la valeur stockée (dict, list, str...), ou `default` si absente,
  expirée **ou illisible**
- **Effet de bord** : supprime le fichier s'il est expiré ou corrompu
- **Tolérance** : un JSON tronqué, un format hérité d'une version antérieure ou
  un problème de droits sont traités comme une absence de cache, jamais comme
  une erreur fatale — le cache est un accélérateur, pas une dépendance dure.

### `has(key: str) -> bool`
Indique si la clé est présente et valide.

Nécessaire parce que `None` est une valeur **stockable** : `scraper.py` mémorise
ses échecs sous cette forme, et `get` seul ne permettrait pas de distinguer
« échec déjà constaté » de « jamais essayé ».

### `set(key: str, value, ttl_hours: float | None = None) -> None`
Stocke une valeur en cache avec un horodatage.

- **Paramètre** `key` : identifiant unique
- **Paramètre** `value` : donnée sérialisable en JSON
- **Paramètre** `ttl_hours` : durée de vie propre à cette entrée ; `None`
  applique `CACHE_TTL_HOURS`. Sert par exemple à ne mémoriser un échec de
  scraping qu'une heure (`CACHE_FAILURE_TTL_HOURS`), un timeout étant souvent
  transitoire.
- **Retour** : aucun. Une valeur non sérialisable ou un disque en défaut ne
  lèvent pas : on renonce simplement au cache.

**Écriture atomique** : la valeur est écrite dans un fichier temporaire puis
déplacée sur la cible via `os.replace`. Un lecteur concurrent voit donc soit
l'ancienne entrée complète, soit la nouvelle — jamais un fichier à moitié
écrit, et un crash en cours d'écriture ne laisse rien de corrompu derrière lui.

## Limites connues
- Deux processus qui écrivent la **même clé** au même instant : le dernier
  gagne. Sans conséquence ici (les valeurs sont équivalentes), et l'atomicité
  garantit qu'aucune entrée n'est laissée dans un état intermédiaire.
- Le cache ne se purge qu'à la lecture d'une entrée expirée : les clés jamais
  relues restent sur le disque. Prévoir un nettoyage manuel de `cache_data/`
  de temps en temps, ou un script de purge si le projet grossit.
