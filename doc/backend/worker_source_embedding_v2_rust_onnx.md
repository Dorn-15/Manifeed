# worker_source_embedding v2 (Rust + ONNX)

## Objectif

Remplacer `worker-source-embedding` Python/Torch par un binaire Rust natif, tres simple, qui:

- tourne sans Docker
- n'utilise plus PyTorch ni Transformers au runtime
- utilise toujours `intfloat/multilingual-e5-large`
- choisit automatiquement GPU si disponible, sinon CPU
- ne fait que:
  - recevoir une tache
  - executer l'embedding
  - renvoyer le resultat

Le monitoring detaille doit etre retire du flux principal.

## Principe de simplification

Le worker v2 ne doit plus faire:

- heartbeat
- reporting `runtime_kind`
- reporting `metric_payload`
- selection dynamique de modele
- batching inter-taches
- logique CPU/GPU/NPU complexe

Le worker v2 doit seulement faire:

1. authentification
2. claim d'une tache
3. inference ONNX
4. `complete` ou `fail`
5. nouvelle tache

## Choix d'architecture

Je recommande un seul crate Rust, pas un workspace.

Structure minimale:

- `main.rs`
- `config.rs`
- `auth.rs`
- `api.rs`
- `onnx.rs`
- `worker.rs`
- `error.rs`

Pourquoi un seul crate:

- moins de plomberie
- moins de types dupliques
- plus facile a packager
- plus facile a maintenir

## Modele impose

Le worker v2 est fixe sur:

- `intfloat/multilingual-e5-large`

Consequence:

- supprimer `EMBEDDING_MODEL_NAME`
- supprimer la validation de `model_name` dans la boucle worker
- ne plus envoyer `model_name` dans les payloads de claim si le backend est dedie a cette version

Si on veut garder une compatibilite transitoire, le backend peut encore stocker `model_name = intfloat/multilingual-e5-large`, mais le worker ne doit plus avoir de branchement autour de ca.

## ONNX au lieu de Torch

## Artifacts a livrer

Je recommande de preparer les artefacts ONNX une fois, hors runtime:

- `model.onnx`
- `tokenizer.json`
- `tokenizer_config.json`
- `special_tokens_map.json`
- `config.json`

Le binaire charge ces fichiers localement. Il ne doit pas telecharger le modele a chaud depuis Hugging Face.

Ca evite:

- le poids de Python
- les installs CUDA/Torch fragiles
- les temps de warmup longs
- les ecarts de runtime entre machines

## Inference pipeline

Pipeline minimal:

1. construire l'entree E5 pour chaque source
2. tokenizer via `tokenizers`
3. inference ONNX
4. mean pooling avec `attention_mask`
5. normalisation L2
6. renvoi des vecteurs

Le comportement fonctionnel reste equivalent a l'actuel, mais avec une implementation plus compacte.

## Choix automatique CPU / GPU

## Regle produit

Le worker prefere toujours le GPU si un provider ONNX GPU est disponible et chargeable.

Sinon il bascule en CPU.

## Regle technique simple

Je recommande une logique de selection tres courte:

### Linux

- essayer `CUDAExecutionProvider`
- sinon `CPUExecutionProvider`

### Windows

- essayer `CUDAExecutionProvider`
- sinon `DmlExecutionProvider`
- sinon `CPUExecutionProvider`

### macOS

- essayer `CoreMLExecutionProvider`
- sinon `CPUExecutionProvider`

On ne gere pas `npu`, `xpu`, `mps`, `rocm` dans la v1.

Ca tient la promesse fonctionnelle:

- GPU si possible
- CPU sinon

Sans reintroduire la complexite du worker actuel.

## Fallback runtime

Au demarrage:

1. tenter de creer la session ONNX avec le premier provider GPU compatible
2. si echec, logguer la raison
3. recreer une session CPU
4. continuer

Option recommandee:

- si une inference GPU echoue avec une erreur provider, recreer une seule fois la session en CPU puis continuer

Ca garde un comportement robuste sans machine d'etat compliquee.

## Protocole backend minimal

Le protocole cible doit etre reduit a:

- `POST /internal/workers/embedding/claim`
- `POST /internal/workers/embedding/complete`
- `POST /internal/workers/embedding/fail`

L'authentification peut reutiliser le mecanisme par cle publique / cle privee propose pour le worker RSS v2.

## Ce qui doit disparaitre du protocole

- `POST /internal/workers/embedding/heartbeat`
- `runtime_kind` dans les payloads worker
- `metric_payload` dans `complete`
- les rapports de perf du worker

## Payload minimal recommande

### Claim response

Une tache d'embedding doit contenir uniquement:

- `task_id`
- `execution_id`
- `sources`

Chaque source:

- `id`
- `title`
- `summary`
- `url`

Le `model_name` peut etre retire du payload si le backend passe officiellement en mode modele fixe.

### Complete request

Le `complete` minimal:

- `task_id`
- `execution_id`
- `result_payload`

Avec:

- `sources[].id`
- `sources[].embedding`

### Fail request

Le `fail` minimal:

- `task_id`
- `execution_id`
- `error_message`

Le `error_payload` detaille devient optionnel ou peut etre supprime si on veut aller au maximum de la simplification.

## Simplification backend necessaire

## A retirer

- `EmbeddingWorkerHeartbeatRequestSchema`
- `touch_embedding_heartbeat`
- `runtime_kind` sur le chemin embedding
- `EmbeddingPerformanceMetricSchema`
- `metric_payload` dans `EmbeddingTaskCompleteRequestSchema`
- `list_source_embedding_performance`
- l'affichage admin du throughput embedding

## A conserver

- les tables de taches `source_embedding_tasks`
- les items de taches
- les executions
- le stockage final dans `rss_source_embeddings`
- les endpoints claim / complete / fail

## Ajustements backend recommandes

### `EmbeddingTaskCompleteRequestSchema`

Le schema devient:

- `task_id`
- `execution_id`
- `result_payload`

Plus de `metric_payload`.

### `complete_embedding_task`

Le backend:

1. valide le payload de resultat
2. ecrit les embeddings
3. marque les items en succes
4. ferme l'execution en succes
5. recalcule le statut du job

Sans statistiques de runtime.

### `worker_instances`

Pour le worker embedding, on peut completement arreter d'utiliser `worker_instances` si on assume qu'il n'y a plus de monitoring live.

Alternative conservative:

- garder l'upsert seulement au `claim`
- ne plus exposer ces donnees dans l'admin

La version la plus simple est de sortir le worker embedding du monitoring temps reel.

## Boucle worker recommandee

Je recommande une boucle volontairement stricte:

1. authentification
2. claim de `1` tache
3. si aucune tache:
   - sleep
   - recommencer
4. executer les embeddings de cette tache
5. `complete`
6. en cas d'erreur, `fail`
7. recommencer

## Taille de lot

Pour simplifier fortement le code, le worker doit garder:

- `queue_read_count = 1`

Le batching se fait uniquement a l'interieur de la tache, sur les `sources` deja incluses dans son payload.

Il ne faut plus fusionner plusieurs taches en une seule inference.

Le backend doit donc controler la taille d'une tache au moment de l'enqueue.

Recommendation simple:

- 8 a 32 sources par tache selon la taille memoire cible

## Crates Rust recommandees

- `tokio`
- `reqwest`
- `serde`
- `serde_json`
- `thiserror`
- `tracing`
- `tracing-subscriber`
- `ort`
- `tokenizers`
- `ndarray`

Si l'auth v2 par cles est reprise:

- `ed25519-dalek`
- `uuid`
- `directories`
- `keyring`

## Configuration cible

Configuration minimale en constantes dans `config.rs`:

- `API_URL`
- `POLL_SECONDS`
- `LEASE_SECONDS`
- `MODEL_DIR`
- `ENROLLMENT_TOKEN`
- `IDENTITY_DIR`

Variables a supprimer:

- `EMBEDDING_MODEL_NAME`
- `EMBEDDING_DEVICE`
- `EMBEDDING_TORCH_VERSION`
- `EMBEDDING_TORCH_INDEX_URL`
- `HF_HUB_DISABLE_XET`
- `WORKER_QUEUE_READ_COUNT`

## Packaging

Sorties cibles:

- `x86_64-pc-windows-msvc`
- `x86_64-unknown-linux-gnu`
- `aarch64-apple-darwin`
- `x86_64-apple-darwin`

Chaque package embarque:

- le binaire
- les fichiers ONNX du modele

## Decision recommandee

Pour une v2 simple et solide:

1. worker embedding en un seul binaire Rust
2. modele fixe `intfloat/multilingual-e5-large`
3. inference ONNX seulement
4. auto-selection GPU avec fallback CPU
5. protocole backend reduit a `claim / complete / fail`
6. suppression du monitoring embedding temps reel

## Risque principal

Le vrai point delicat n'est pas la boucle worker, mais la distribution ONNX par OS et provider GPU.

Il faut donc figer une politique simple:

- Linux: CUDA ou CPU
- Windows: CUDA, sinon DirectML, sinon CPU
- macOS: CoreML, sinon CPU

Si cette politique est acceptee, l'implementation devient nettement plus simple que l'existant Python/Torch.
