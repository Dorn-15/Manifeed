# RSS Scraper Scaling Analysis

Date: 2026-03-11

## Scope

Ce document couvre deux analyses:

1. les points de blocage entre le worker RSS et le backend
2. les points de blocage dans l'ingestion SQL et les raisons pour lesquelles `/internal/workers/rss/complete` devient lent

Objectif produit:

- permettre a un grand nombre de workers RSS de se connecter au backend
- garder les workers focalises sur le fetch/parsing
- rendre le backend et PostgreSQL capables d'absorber des dizaines de milliers de flux RSS sans transformer `complete`, `claim` et `state` en goulots d'etranglement

## Analyse 1: blocages worker <-> backend

### Constat principal

Le chemin critique du worker n'est pas seulement le fetch RSS. Il est fortement couple a des endpoints backend synchrones qui ecrivent dans PostgreSQL dans des transactions longues.

Les symptomes observes sont coherents avec le code:

- les `return <task_id>` arrivent tard, car ils ne sont logges qu'apres l'ack backend
- des pauses apparaissent apres `claim`, car le worker attend encore des appels backend de monitoring
- les appels `complete`, `claim` et `state` se bloquent entre eux via la meme ligne `worker_instances`

### Cause technique la plus visible

Dans `workers-rust/worker-rss/src/worker/runtime.rs`:

- apres un `claim`, le worker appelle `update_state(processing_state(...))`
- cet `await` est avant le lancement des nouveaux fetchs
- si le backend bloque cet endpoint, les fetchs suivants ne demarrent pas

Dans `backend/app/services/internal/rss_worker_task_service.py`:

- `complete_scrape_task(...)` commence par `upsert_worker_instance_state(...)`
- `update_worker_state(...)` fait lui aussi `upsert_worker_instance_state(...)`
- `claim_scrape_tasks(...)` fait lui aussi `upsert_worker_instance_state(...)`

Dans `backend/app/clients/database/worker_queue_db_client.py`:

- `upsert_worker_instance_state(...)` fait un `INSERT ... ON CONFLICT (worker_kind, worker_name) DO UPDATE`
- ce pattern prend un verrou sur la ligne `worker_instances` du worker courant
- comme `complete_scrape_task(...)` garde sa transaction ouverte jusqu'au `commit()` final, les autres appels qui veulent mettre a jour `worker_instances` peuvent attendre la fin de `complete`

### Consequence pratique

Le backend utilise la table `worker_instances` comme point central pour:

- le heartbeat
- l'etat courant
- le claim
- la completion

Cette ligne devient un hot row lock par worker. Plus les transactions `complete` sont longues, plus:

- `state` attend
- `claim` attend
- les fetchs paraissent "arretes"

### Conclusion de l'analyse 1

Le monitoring worker (`worker_instances`) est actuellement dans le chemin critique du scraping. Ce design empeche une bonne montee en charge.

## Analyse 2: pourquoi l'ingestion SQL prend autant de temps

### Constat principal

`/internal/workers/rss/complete` fait trop de travail dans une seule transaction synchrone avant de renvoyer `ok=true`.

Le service `backend/app/services/internal/rss_worker_task_service.py::complete_scrape_task` fait, dans le meme `db.commit()`:

- validation Pydantic de chaque resultat worker
- verification de coherence `job_id`, `feed_id`, doublons, feeds manquants
- `UPDATE` de `rss_scrape_task_items`
- `upsert_feed_scraping_state(...)`
- `upsert_sources_for_feed(...)` pour chaque resultat `success`
- recalcul du resume de la task
- recalcul du resume du job
- `UPDATE` de `rss_scrape_task_executions`

Tant que tout cela n'est pas termine, le worker n'obtient pas sa reponse HTTP.

### Goulot 1: ingestion source par source, sans batch

Dans `backend/app/clients/database/source_ingest_db_client.py`, `upsert_sources_for_feed(...)` est un pattern N+1 tres net:

- 1 lecture du nom de company par feed
- puis, pour chaque source:
  - recherche par URL
  - sinon recherche par titre + company
  - insertion ou update de `rss_sources`
  - insertion ou update de `rss_source_contents`
  - insertion de `rss_source_feeds`

Pour un feed qui retourne 50 articles, cela peut produire plusieurs centaines de round-trips SQL.

Si une task contient plusieurs feeds, le cout explose lineairement.

### Goulot 2: recherche par titre/company potentiellement tres couteuse

Le fallback `_find_existing_source_by_title_and_company(...)` est particulierement cher:

- il joint `rss_sources`, `rss_source_contents`, `rss_source_feeds`, `rss_feeds`, `rss_company`
- il filtre avec `WHERE lower(content.title) = lower(:title)`
- il n'y a pas d'index visible sur `lower(title)` ni sur une colonne normalisee de deduplication
- il charge toutes les lignes candidates puis refait une normalisation Python avec `normalize_article_identity_text(...)`

Sur une base qui grossit, cette requete devient de plus en plus mauvaise:

- scan large
- pas de cle de dedup explicite exploitable par l'index
- cout CPU Python en plus du cout SQL

### Goulot 3: recalculs aggreges a chaque completion

La completion ne fait pas qu'ecrire des resultats. Elle recalcule aussi des compteurs:

- `_refresh_rss_task_summary(...)` recompte les items de la task
- `refresh_rss_scrape_job_status(...)` recompte tasks et items du job

Ces compteurs sont recalcules par requetes `COUNT(*)` a chaque task terminee.

Plus les jobs sont gros, plus ce recalcul devient cher. Cela cree un cout proportionnel a la taille historique du job, pas juste a la taille du delta courant.

### Goulot 4: `claim` recalcule aussi de la donnee derivee couteuse

Dans `claim_scrape_tasks(...)`, la CTE `latest_source` recalcule:

- `MAX(source.published_at)` par `feed_id`
- a partir de `rss_source_feeds` et `rss_sources`

Cette aggregation est executee a chaque claim. Avec beaucoup de sources historiques, le cout des claims augmente avec la taille totale de la base.

Cette information devrait etre materialisee ou tenue incrementale par feed, pas recalculee a chaud pour chaque claim.

### Goulot 5: payload `complete` trop riche

Le payload `complete` embarque:

- les metadonnees du resultat
- toute la liste `sources`
- pour chaque source: `title`, `url`, `summary`, `author`, `published_at`, `image_url`

Donc le backend paie:

- le cout reseau
- le cout JSON
- le cout de validation Pydantic
- le cout SQL d'ingestion

sur la meme requete synchrone.

### Goulot 6: pool SQLAlchemy probablement trop petit

`backend/database.py` utilise:

- `create_engine(DATABASE_URL, pool_pre_ping=True)`

avec les valeurs par defaut SQLAlchemy. En pratique, cela veut souvent dire un pool limite pour un backend qui doit servir:

- UI admin
- claims workers
- complete workers
- state workers
- auth workers

Avec beaucoup de workers, le backend va vite faire la queue sur le pool SQL avant meme de parler de CPU ou de locks.

### Goulot 7: routes FastAPI synchrones + transactions longues

Les routes workers sont definies en `def`, pas en `async def`, et executent des acces DB synchrones. Ce n'est pas un probleme en soi, mais combine a:

- transactions longues
- pool DB potentiellement limite
- contention sur `worker_instances`

cela cree un backend tres sensible a la congestion.

## Pourquoi cela scale mal pour des dizaines de milliers de flux

Le design actuel melange dans la meme requete HTTP:

- orchestration worker
- monitoring worker
- persistance runtime feed
- deduplication source
- ingestion source
- recalcul de compteurs

Cela produit un effet de cascade:

1. le worker termine une task
2. `complete` ouvre une longue transaction
3. cette transaction tient des verrous et un slot DB
4. `state` et `claim` attendent
5. le worker parait bloque
6. plus il y a de workers, plus la contention augmente
7. plus il y a de donnees historiques, plus chaque `claim` et chaque `complete` coutent cher

Ce n'est pas seulement un probleme de parallelisme worker. C'est surtout un probleme de couplage entre orchestration temps reel et ingestion SQL lourde.

## Recommandations prioritaires

### P0: sortir `worker_instances` du chemin critique

Actions recommandees:

- ne plus appeler `upsert_worker_instance_state(...)` au debut de `complete_scrape_task(...)`
- ne plus appeler `update_state(...)` de facon bloquante dans la boucle critique du worker
- garder `state` comme heartbeat best effort, pas comme precondition au scraping

Effet attendu:

- `claim`, `state` et `complete` cessent de se bloquer sur la meme ligne worker

### P0: separer ACK rapide et ingestion lourde

Architecture recommandee:

1. `/internal/workers/rss/complete` devient un endpoint d'ack rapide
2. le backend stocke un payload brut en table de staging ou outbox
3. un process dedie consomme cette file et fait l'ingestion SQL lourde

Le endpoint `complete` devrait idealement faire seulement:

- validation minimale du couple `task_id` / `execution_id`
- marquage "result received"
- persistance brute du payload
- commit rapide
- reponse `ok=true`

Puis un pipeline separe fait:

- `rss_feed_runtime`
- dedup source
- `rss_source_contents`
- `rss_source_feeds`
- compteurs job/task

Effet attendu:

- les workers restent rapides
- le backend d'orchestration reste leger
- l'ingestion peut etre parallelisee et profilee separement

### P0: supprimer le recalcul `latest_source` a chaque claim

Remplacer la CTE `latest_source` par une valeur incrementalement maintenue:

- soit dans `rss_feed_runtime`
- soit dans une table projection par feed

Effet attendu:

- `claim` devient quasi O(nombre de tasks claim) au lieu d'etre sensible a la taille historique des sources

### P1: rendre la dedup source indexable

Le fallback par titre/company doit sortir du `scan + normalisation Python`.

Piste recommandee:

- ajouter une cle de dedup normalisee stockee, par exemple `dedup_key`
- construire cette cle une fois
- indexer cette cle
- faire la recherche SQL directement sur cette cle

Exemple conceptuel:

- `dedup_key = hash(normalized_company + '|' + normalized_title + '|' + normalized_published_bucket)`

Effet attendu:

- plus de requete `lower(title)` + joins larges + post-filtrage Python

### P1: batcher l'ingestion SQL

Aujourd'hui l'ingestion est ligne par ligne. Il faut passer a des operations bulk:

- bulk insert/upsert de `rss_sources`
- bulk insert/upsert de `rss_source_contents`
- bulk insert `rss_source_feeds`

Avec staging temporaire si necessaire.

Effet attendu:

- reduction massive des round-trips
- meilleur debit sous charge

### P1: remplacer les recomptes par des compteurs incrementaux

Au lieu de recalculer `COUNT(*)` a chaque completion:

- incrementer `feeds_processed`, `feeds_success`, `feeds_error` au fil de l'eau
- faire la meme chose pour `worker_jobs`

Effet attendu:

- `complete` ne depend plus de la taille totale du job

### P1: dimensionner explicitement le pool DB

Configurer explicitement:

- `pool_size`
- `max_overflow`
- `pool_timeout`

et ajuster selon:

- nombre de workers RSS
- nombre de workers embedding
- trafic UI/admin

Sans cela, les workers concurrents vont se battre pour trop peu de connexions.

## Architecture cible recommandee

Pour tenir des dizaines de milliers de flux RSS, il faut separer 3 plans:

### 1. plan orchestration

Responsable de:

- auth worker
- claim
- ack fast complete/fail
- heartbeat/state best effort

Doit rester leger et a faible latence.

### 2. plan ingestion

Responsable de:

- runtime feed
- dedup source
- insert/update SQL lourds

Doit etre asynchrone, batchable et observable.

### 3. plan projection / monitoring

Responsable de:

- compteurs jobs
- vues admin
- etat des workers

Doit etre eventual consistency acceptable, pas bloquant pour le scrape.

## Roadmap d'optimisation concrete

### Etape 1: gains rapides

- rendre `state` non bloquant cote worker
- enlever `worker_instances` du debut de `complete`
- augmenter le pool SQLAlchemy
- mesurer le temps de `claim`, `state`, `complete`, `db.commit()`

### Etape 2: gros gain structurel

- transformer `complete` en ACK rapide + table de staging
- ajouter un consumer d'ingestion dedie

### Etape 3: gros gain base de donnees

- materialiser `last_db_article_published_at` par feed
- ajouter une vraie cle de dedup source indexee
- batcher les upserts source/content/feed
- remplacer les recomptes par des increments

## Metriques a instrumenter en priorite

Pour piloter les optimisations, il faut mesurer:

- latence worker -> `/rss/claim`
- latence worker -> `/rss/state`
- latence worker -> `/rss/complete`
- temps backend passe dans:
  - validation payload
  - `upsert_feed_scraping_state`
  - `upsert_sources_for_feed`
  - `_refresh_rss_task_summary`
  - `refresh_rss_scrape_job_status`
  - `db.commit()`
- taille moyenne des payloads `complete`
- nombre moyen de `sources` par `feed`
- temps des requetes `_find_existing_source_by_title_and_company`
- taux d'attente sur le pool SQLAlchemy
- temps d'attente sur les verrous PostgreSQL

## Synthese

Le probleme principal n'est pas le fetch RSS en lui-meme. Le vrai goulot est le backend qui traite `claim`, `state`, `complete` et l'ingestion SQL lourde dans des chemins trop couples et trop synchrones.

Si le but est de faire tourner un grand nombre de workers sur des dizaines de milliers de flux:

- il faut un backend d'orchestration leger
- il faut une ingestion SQL asynchrone et batchable
- il faut supprimer les recalculs et scans globaux du chemin chaud
- il faut enlever les hot row locks sur `worker_instances`

Sans cette separation, ajouter des workers finira surtout par augmenter la contention et la latence, pas le debit reel.
