# worker_rss_scrapper v2 (Rust desktop)

## Objectif

Remplacer `worker-rss-scrapper` Python/Docker par un binaire desktop Rust natif:

- Windows
- macOS
- Linux

Le worker v2 doit:

- tourner sans Docker
- parler uniquement au `backend`
- generer une paire de cles publique/privee au premier lancement
- s'authentifier avec cette identite machine
- exposer une mini interface locale
- afficher l'etat de connexion backend
- permettre un `on/off` du worker
- afficher la tache en cours si une tache est executee

## Choix d'architecture

Je recommande un projet Rust en workspace avec 3 crates:

1. `worker-rss-core`
2. `worker-rss-api`
3. `worker-rss-desktop`

### `worker-rss-core`

Responsabilites:

- boucle worker
- machine d'etat locale
- parsing RSS/Atom
- rate limit par company/feed
- heartbeat
- reprise sur erreur
- publication d'evenements d'etat a l'UI

Etat local minimal:

- `Stopped`
- `Starting`
- `Authenticating`
- `Idle`
- `Claiming`
- `Processing`
- `Paused`
- `BackendDisconnected`
- `AuthRejected`
- `Error`

### `worker-rss-api`

Responsabilites:

- client HTTP `reqwest`
- protocoles d'enrollement et d'auth
- claim / complete / fail / heartbeat
- retries reseau
- refresh du token de session

### `worker-rss-desktop`

Je recommande `egui/eframe` plutot que Tauri pour cette v1:

- 100% Rust
- packaging simple
- pas de dependance WebView
- bon fit pour une UI minuscule

UI tres compacte:

- switch `Worker ON / OFF`
- pastille `Backend: connected / disconnected`
- pastille `Auth: enrolled / pending / rejected`
- texte `Etat: idle / processing / paused / error`
- bloc `Tache en cours`
- bouton `Reconnect`
- bouton `Copier l'identite`

## Authentification v2

## Principe

On remplace `worker_id + worker_secret` par une identite asymetrique:

- cle privee Ed25519 generee au premier lancement
- cle publique enregistree cote backend
- le backend delivre ensuite un token court de session

Pourquoi Ed25519:

- simple
- rapide
- signatures petites
- support mature en Rust

## Identite locale

Au premier lancement, le binaire cree:

- `device_id` stable de type UUID
- `keypair` Ed25519
- `install_id` optionnel pour distinguer une reinstallation

Stockage recommande:

- cle privee dans le keychain OS si possible
- sinon fichier local protege dans un dossier app

Chemins locaux:

- Linux: `~/.config/manifeed/worker-rss/`
- macOS: `~/Library/Application Support/manifeed/worker-rss/`
- Windows: `%AppData%\\manifeed\\worker-rss\\`

Fichiers:

- `config.json`
- `public_identity.json`
- `worker.log`

La cle privee ne doit pas etre affichee ni exportee par defaut.

## Enrollement

Il manque aujourd'hui un mecanisme de confiance initiale. Je recommande:

1. l'admin cree un `enrollment_token` depuis le backend admin
2. le worker v2 envoie:
   - `worker_type`
   - `device_id`
   - `public_key`
   - `hostname`
   - `platform`
   - `worker_version`
   - `enrollment_token`
3. le backend cree ou approuve l'identite
4. le backend retourne un challenge
5. le worker signe le challenge avec la cle privee
6. le backend verifie et emet un `access_token` court

Ensuite, toutes les authentifications se font par challenge signe.

## Flux d'auth recommande

### Premier lancement

1. generation de la paire de cles
2. saisie ou collage du `enrollment_token`
3. appel `POST /internal/workers/enroll`
4. signature du challenge
5. emission d'un `access_token` court et d'un `refresh_nonce`

### Lancements suivants

1. appel `POST /internal/workers/auth/challenge`
2. signature locale du challenge
3. appel `POST /internal/workers/auth/verify`
4. recuperation d'un JWT worker court

Le JWT reste utile pour ne pas signer chaque requete metier.

## Evolution backend necessaire

## Nouvelles tables

Ajouter une table dediee plutot que de surcharger `worker_instances`.

### `worker_identities`

Champs recommandes:

- `id`
- `worker_kind`
- `device_id`
- `public_key`
- `fingerprint`
- `display_name`
- `hostname`
- `platform`
- `arch`
- `worker_version`
- `enrollment_status`
- `last_enrolled_at`
- `last_auth_at`
- `created_at`
- `updated_at`

Contraintes:

- unique `(worker_kind, device_id)`
- unique `fingerprint`

### Evolution de `worker_instances`

Ajouter:

- `identity_id`
- `connection_state`
- `current_task_id`
- `current_execution_id`
- `current_task_label`
- `last_error`
- `last_heartbeat_at`
- `desired_state`

Objectif:

- distinguer l'identite machine de l'instance runtime
- afficher la tache en cours dans l'admin
- garder un etat exploitable pour l'UI et le support

## Nouveaux endpoints backend

Je recommande:

- `POST /internal/workers/enroll`
- `POST /internal/workers/auth/challenge`
- `POST /internal/workers/auth/verify`
- `POST /internal/workers/rss/state`
- `GET /internal/workers/me`

### `POST /internal/workers/enroll`

Entree:

- `worker_type`
- `device_id`
- `public_key`
- `hostname`
- `platform`
- `arch`
- `worker_version`
- `enrollment_token`

Sortie:

- `identity_id`
- `challenge_id`
- `challenge`

### `POST /internal/workers/auth/challenge`

Entree:

- `worker_type`
- `device_id`

Sortie:

- `challenge_id`
- `challenge`

### `POST /internal/workers/auth/verify`

Entree:

- `device_id`
- `challenge_id`
- `signature`

Sortie:

- `access_token`
- `expires_at`
- `worker_profile`

### `POST /internal/workers/rss/state`

Appel periodique plus riche qu'un simple heartbeat.

Entree:

- `active`
- `connection_state`
- `pending_tasks`
- `current_task_id`
- `current_execution_id`
- `current_task_label`
- `current_feed_id`
- `current_feed_url`
- `last_error`

Ce endpoint peut remplacer `rss/heartbeat`.

## Etat metier du worker

Le worker ne doit pas seulement envoyer `active/pending_tasks`.

Evenements internes utiles:

- `worker_started`
- `worker_paused`
- `auth_in_progress`
- `auth_ok`
- `backend_unreachable`
- `task_claimed`
- `task_started`
- `task_completed`
- `task_failed`

Ces evenements alimentent:

- l'UI locale
- le logging
- l'endpoint `rss/state`

## UI locale minimale

## Ecran unique

Contenu:

- titre `Manifeed RSS Worker`
- switch principal `ON / OFF`
- statut backend avec couleur
- statut auth avec couleur
- ligne `Dernier contact backend`
- ligne `Version worker`
- bloc `Tache en cours`
- bloc `Derniere erreur`

Exemple d'affichage:

- `Worker: ON`
- `Backend: connected`
- `Auth: enrolled`
- `Etat: Processing`
- `Tache: feed 1824 - https://example.com/rss.xml`

## Comportement du bouton ON/OFF

`OFF` ne tue pas l'application.

`OFF`:

- arrete le polling
- termine la boucle apres la tache courante
- publie `desired_state = paused`

`ON`:

- relance auth si necessaire
- relance claim/poll

Ce comportement est plus propre qu'un kill brutal en pleine execution.

## Moteur de taches

Le worker RSS v1 traite une seule tache a la fois. Je recommande de garder ce comportement en v2 au debut:

- plus simple pour la stabilite
- plus simple pour l'UI
- plus simple pour les reprises

On garde:

- `queue_read_count = 1`
- boucle stricte `claim -> process -> complete/fail -> claim`

## Crates Rust recommandees

- `tokio`
- `reqwest`
- `serde`
- `serde_json`
- `tracing`
- `tracing-subscriber`
- `thiserror`
- `uuid`
- `ed25519-dalek`
- `sha2`
- `directories`
- `keyring`
- `rss`
- `atom_syndication`
- `chrono`
- `egui`
- `eframe`

## Packaging desktop

Sorties cibles:

- `x86_64-pc-windows-msvc`
- `x86_64-unknown-linux-gnu`
- `aarch64-unknown-linux-gnu`
- `x86_64-apple-darwin`
- `aarch64-apple-darwin`

Packaging:

- Windows: `.msi`
- macOS: `.dmg`
- Linux: `.AppImage` ou `.deb`

CI:

- GitHub Actions avec matrice par OS
- signature des artefacts plus tard si necessaire

## Compatibilite et migration

Je recommande une migration en 3 etapes.

### Etape 1

Backend compatible double mode:

- auth v1 `worker_id + worker_secret`
- auth v2 par challenge signe

### Etape 2

Sortie du worker Rust v2 sur un petit lot de machines.

### Etape 3

Suppression de l'auth v1 pour le worker RSS quand la v2 est stable.

## Decoupage implementation

### Lot A - backend

- table `worker_identities`
- endpoints enroll/challenge/verify
- JWT v2
- enrichissement `worker_instances`
- endpoint `rss/state`

### Lot B - moteur Rust

- client backend
- auth par cles
- boucle claim/process/complete/fail
- publication d'etat interne

### Lot C - UI desktop

- fenetre minimale
- bouton on/off
- statut backend
- statut auth
- tache en cours
- logs d'erreur courts

### Lot D - packaging

- builds multiplateformes
- auto-update plus tard seulement

## Decision recommandee

Pour une v2 propre et livrable vite:

1. backend FastAPI conserve tel quel pour la queue et les jobs
2. nouveau worker RSS en Rust
3. UI desktop en `egui/eframe`
4. auth par challenge Ed25519 + JWT court
5. endpoint `rss/state` pour afficher la tache en cours

Cette approche limite le risque:

- pas de DB directe depuis le poste client
- pas de secret partage a distribuer
- binaire natif sur tous les OS desktop
- UX suffisante pour l'operateur

## Point important

Sans `enrollment_token` ou autre bootstrap de confiance, n'importe quel binaire pourrait enregistrer une cle publique. Il faut donc absolument garder une etape d'approbation ou un token d'enrollement cote backend.
