# WEATHGARDS — Documentation d'exploitation

**Version 1.0.0**

---

## Table des matières

1. [Présentation fonctionnelle](#1-présentation-fonctionnelle)
   - 1.1 [Vue d'ensemble](#11-vue-densemble)
   - 1.2 [Cas d'usage](#12-cas-dusage)
   - 1.3 [Principe de fonctionnement](#13-principe-de-fonctionnement)
   - 1.4 [Ce que WEATHGARDS ne fait pas](#14-ce-que-weathgards-ne-fait-pas)
2. [Présentation opérationnelle](#2-présentation-opérationnelle)
   - 2.1 [Architecture générale](#21-architecture-générale)
   - 2.2 [Composants principaux](#22-composants-principaux)
   - 2.3 [Flux de données](#23-flux-de-données)
   - 2.4 [Interface cockpit](#24-interface-cockpit)
   - 2.5 [Sécurité réseau](#25-sécurité-réseau)
3. [Installation](#3-installation)
   - 3.1 [Prérequis système](#31-prérequis-système)
   - 3.2 [Installation pas à pas — Linux](#32-installation-pas-à-pas--linux)
   - 3.3 [Installation pas à pas — macOS](#33-installation-pas-à-pas--macos)
   - 3.4 [Installation pas à pas — Windows](#34-installation-pas-à-pas--windows)
   - 3.5 [Vérification de l'installation](#35-vérification-de-linstallation)
4. [Administration](#4-administration)
   - 4.1 [Démarrage et arrêt](#41-démarrage-et-arrêt)
   - 4.2 [Configuration de l'environnement](#42-configuration-de-lenvironnement)
   - 4.3 [Gestion des outils MCP](#43-gestion-des-outils-mcp)
   - 4.4 [Connexion d'un LLM distant](#44-connexion-dun-llm-distant)
   - 4.5 [Mise à jour](#45-mise-à-jour)
5. [Dépannage](#5-dépannage)
   - 5.1 [L'interface ne s'affiche pas](#51-linterface-ne-saffiche-pas)
   - 5.2 [Docker non détecté](#52-docker-non-détecté)
   - 5.3 [Le serveur MCP refuse de démarrer](#53-le-serveur-mcp-refuse-de-démarrer)
   - 5.4 [Le LLM ne peut pas se connecter](#54-le-llm-ne-peut-pas-se-connecter)
   - 5.5 [Scan retourne toujours une liste vide](#55-scan-retourne-toujours-une-liste-vide)
   - 5.6 [Erreurs de port occupé](#56-erreurs-de-port-occupé)
   - 5.7 [Problèmes de permissions](#57-problèmes-de-permissions)
6. [Nettoyage et désinstallation](#6-nettoyage-et-désinstallation)
   - 6.1 [Arrêt propre](#61-arrêt-propre)
   - 6.2 [Suppression des données de configuration](#62-suppression-des-données-de-configuration)
   - 6.3 [Désinstallation complète](#63-désinstallation-complète)

---

## 1. Présentation fonctionnelle

### 1.1 Vue d'ensemble

WEATHGARDS est une **passerelle MCP locale** qui permet à un modèle de langage (LLM) distant d'interroger l'état de la machine hôte en temps réel. Il scanne les **containers Docker**, les **processus système** et les **services OS** actifs, puis expose des outils de lecture au format **MCP (Model Context Protocol)** sur le réseau local.

L'outil est conçu pour fonctionner sans configuration complexe sur les trois principales plateformes (Linux, macOS, Windows) et fournit une interface web intégrée pour piloter l'ensemble sans ligne de commande après l'installation initiale.

```
┌─────────────────────────┐         réseau local          ┌──────────────────┐
│      MACHINE HÔTE       │  ◄────────────────────────►  │   LLM DISTANT    │
│                         │  http://192.168.x.x:9766/mcp  │  (Claude, GPT…)  │
│  ┌─────────────────┐    │                               └──────────────────┘
│  │  Scanner        │    │
│  │  ┌──────────┐   │    │         navigateur local
│  │  │ Docker   │   │    │  ◄────────────────────────►  ┌──────────────────┐
│  │  │ Processus│   │    │  http://127.0.0.1:8765        │  Cockpit UI      │
│  │  │ Services │   │    │                               │  (React/Vite)    │
│  │  └──────────┘   │    │                               └──────────────────┘
│  └─────────────────┘    │
│                         │
│  ┌─────────────────┐    │
│  │  Serveur MCP    │    │
│  │  (FastMCP)      │    │
│  └─────────────────┘    │
│                         │
│  ┌─────────────────┐    │
│  │  API FastAPI    │    │
│  └─────────────────┘    │
└─────────────────────────┘
```

### 1.2 Cas d'usage

| Scénario | Description |
|----------|-------------|
| **Supervision LLM** | Un LLM pilote une session de débogage et interroge l'état des containers ou des processus en cours d'exécution via des appels MCP. |
| **Audit automatisé** | Un agent automatique vérifie périodiquement les services critiques et notifie en cas d'anomalie. |
| **Exploration d'infrastructure** | Lors d'une prise en main d'un nouvel environnement, un LLM mappe l'infrastructure locale sans accès SSH direct. |
| **Orchestration multi-machines** | Plusieurs instances WEATHGARDS sur différentes machines exposent leurs outils à un LLM central qui agrège les données. |

### 1.3 Principe de fonctionnement

WEATHGARDS repose sur le principe **Template-First** : les outils MCP sont écrits une seule fois par les développeurs sous forme de fonctions Python paramétrées. Le scanner ne fait que découvrir des *noms de cibles* valides, et l'activation lie une cible découverte à un handler existant.

```
Étape 1 — Scan
  Le scanner interroge Docker SDK, psutil et systemd/launchd/SCM
  → Produit une liste de cibles : "nginx:8080", "postgres", "redis"…

Étape 2 — Activation
  L'opérateur choisit une cible et l'associe à un outil du catalogue
  → Exemple : ProcessLogHandler(target="nginx:8080")

Étape 3 — Exposition MCP
  Le serveur MCP démarre et expose l'outil sous un nom unique
  → Le LLM peut appeler : get_process_logs(target="nginx:8080")

Étape 4 — Exécution
  L'appel LLM déclenche le handler pré-écrit
  → Résultat structuré retourné au LLM, jamais de code généré
```

Le LLM ne génère **jamais** de code Python à l'exécution. Toute la logique d'accès est encapsulée dans des handlers statiques et audités.

### 1.4 Ce que WEATHGARDS ne fait pas

- Il ne modifie pas les containers ou processus (lecture seule).
- Il ne transmet pas le socket Docker brut sur le réseau.
- Il ne génère pas de code à la volée à partir des instructions du LLM.
- Il ne stocke pas les résultats des appels MCP dans une base de données.
- Il ne remplace pas un outil de monitoring (Prometheus, Grafana, etc.).

---

## 2. Présentation opérationnelle

### 2.1 Architecture générale

WEATHGARDS est une **application Python monoprocessus** lancée via `uv run weathgards`. Elle démarre un serveur **uvicorn/FastAPI** qui sert simultanément :

- L'**API REST interne** (`/api/*`) consommée par l'interface cockpit.
- Le **bundle React** de l'interface cockpit (`/` → fichiers statiques depuis `frontend/dist/`).
- Le **serveur MCP** (`http://<host>:<port>/mcp`), lancé à la demande comme tâche asyncio interne.

```
weathgards (processus unique)
│
├── uvicorn (port 8765 par défaut)
│   ├── FastAPI
│   │   ├── GET  /api/health
│   │   ├── GET  /api/scan
│   │   ├── GET  /api/catalog
│   │   ├── GET  /api/tools/active
│   │   ├── POST /api/activate-tool
│   │   ├── DELETE /api/tools/{id}
│   │   ├── POST /api/test-tool
│   │   ├── POST /api/mcp/start
│   │   ├── POST /api/mcp/stop
│   │   ├── GET  /api/mcp/status
│   │   ├── GET  /api/mcp/snippets
│   │   ├── GET  /api/mcp/connection-info
│   │   ├── GET  /api/settings
│   │   └── PUT  /api/settings
│   └── Static files → frontend/dist/
│
└── MCPServerManager (asyncio task, optionnel)
    └── FastMCP / uvicorn interne (port 9766 par défaut)
        └── BearerAuthMiddleware
```

### 2.2 Composants principaux

#### Scanner (`src/weathgards/scanner/`)

| Module | Rôle | Dépendance |
|--------|------|------------|
| `docker_scanner.py` | Interroge le daemon Docker pour lister containers actifs/arrêtés | `docker` SDK |
| `process_scanner.py` | Liste les processus via psutil, filtre sur critères configurables | `psutil` |
| `service_scanner.py` | Interroge systemd (Linux), launchd (macOS), SCM (Windows) | Natif OS |
| `orchestrator.py` | Agrège les résultats des trois scanners, gère les erreurs de façon isolée | — |
| `models.py` | `ScanResult` — modèle Pydantic commun à tous les scanners | — |

#### Serveur MCP (`src/weathgards/mcp_server/`)

| Module | Rôle |
|--------|------|
| `server.py` | `MCPServerManager` — cycle de vie du serveur MCP (start/stop/status), hot-reload des outils |
| `auth.py` | `BearerAuthMiddleware` — validation du token sur chaque requête `/mcp` |
| `tools/catalog.py` | Catalogue statique des outils disponibles + `HANDLER_MAP` |
| `tools/registry.py` | `ToolRegistry` — registre en mémoire des activations (outil, cible) |
| `tools/docker_tools.py` | Handlers Docker : `docker_container_status`, `docker_container_logs`, `docker_list_containers` |
| `tools/process_tools.py` | Handler processus : `process_status` (CPU, mémoire RSS, ports en écoute) |

#### API (`src/weathgards/api/`)

| Module | Rôle |
|--------|------|
| `app.py` | Factory FastAPI, CORS, lifespan |
| `routes/scan.py` | `GET /api/health`, `GET /api/scan` |
| `routes/tools.py` | Catalogue, activation, désactivation, test |
| `routes/server.py` | Contrôle du serveur MCP (start/stop/status/snippets/connection-info) |
| `routes/settings.py` | Lecture et écriture des paramètres runtime |
| `static.py` | Montage du bundle React + fallback SPA |

#### Configuration (`src/weathgards/config/settings.py`)

Deux couches distinctes :

- **`Settings`** : paramètres de démarrage, chargés depuis `.env` au lancement, **immuables** à chaud.
- **`AppSettings`** : paramètres runtime, persistés dans `<config_dir>/settings.json`, **modifiables** via l'interface sans redémarrage (sauf hôte/port MCP).

### 2.3 Flux de données

```
[Navigateur]
    │
    │  1. GET /api/health → OS, docker_available
    │  2. GET /api/scan   → liste de ScanResult[]
    │
    ▼
[API FastAPI]
    │
    │  asyncio.to_thread() → pas de blocage de l'event loop
    │
    ▼
[Scanner Orchestrator]
    ├── DockerScanner.scan()     → container[] ou [] si Docker absent
    ├── ProcessScanner.scan()    → process[]
    └── ServiceScanner.scan()   → service[]
    │
    ▼
[ScanResult[]] → sérialisé JSON → navigateur

[Navigateur clique "Activer un outil MCP"]
    │
    │  POST /api/activate-tool { tool_name, target_name }
    │
    ▼
[ToolRegistry.register()] → ActivatedTool stocké en mémoire

[Navigateur clique "Démarrer le serveur MCP"]
    │
    │  POST /api/mcp/start { host, port }
    │
    ▼
[MCPServerManager.start()]
    ├── Vérifie sécurité (token présent si réseau)
    ├── Construit FastMCP avec les outils activés
    ├── Démarre uvicorn interne en tâche asyncio
    └── Démarre watcher (hot-reload si registry change)

[LLM distant]
    │
    │  HTTP POST http://192.168.x.x:9766/mcp
    │  Authorization: Bearer <token>
    │
    ▼
[BearerAuthMiddleware] → valide token
    │
    ▼
[FastMCP dispatcher] → appelle le handler pré-écrit
    │
    ▼
[Handler Python] → lit Docker/psutil → dict → JSON → LLM
```

### 2.4 Interface cockpit

L'interface est une **Single Page Application React** servie depuis le même processus que l'API. Elle est accessible par défaut à `http://127.0.0.1:8765`.

#### Navigation principale

| Onglet | Icône | Rôle |
|--------|-------|------|
| **Dashboard** | Grille | Lancer un scan, visualiser les services détectés, activer des outils MCP par service |
| **Outils MCP** | Éclair | Consulter la liste de tous les outils activés, désactiver individuellement |
| **Serveur** | Antenne | Démarrer/arrêter le serveur MCP, configurer l'exposition réseau, copier l'URL et le token |
| **Configuration** | Engrenage | Paramètres MCP, intervalles de scan, sources actives (Docker/processus/services) |

#### Indicateurs d'état (bas de sidebar)

| Indicateur | Signification |
|------------|---------------|
| Point vert animé | API FastAPI accessible et fonctionnelle |
| Point rouge fixe | API inaccessible (process arrêté ?) |
| `WG OK` | Santé API confirmée |
| `WG ERREUR` | Problème de connexion à l'API |

### 2.5 Sécurité réseau

WEATHGARDS applique **trois couches de protection** cumulatives lorsque le serveur MCP est exposé sur le réseau local :

#### Couche 1 — Token Bearer

Le token MCP est **auto-généré** au premier démarrage avec `secrets.token_urlsafe(32)` et persisté dans `<config_dir>/mcp.token` (permissions `600`). Il est affiché une seule fois dans les logs au niveau `INFO` pour que l'opérateur puisse le copier.

Chaque requête adressée à `/mcp` doit porter l'en-tête :
```
Authorization: Bearer <token>
```
Sans ce token valide, la requête est rejetée avec HTTP 401 (comparaison en temps constant pour éviter les attaques timing). Le serveur **refuse de démarrer en mode réseau** si le token store est vide.

#### Couche 2 — Liste blanche IP (optionnelle)

La variable `WEATHGARDS_ALLOWED_CLIENTS` accepte une liste de plages CIDR. Si renseignée, les requêtes provenant d'adresses hors de ces plages sont rejetées avant même la vérification du token.

```env
# Exemple : autoriser uniquement le sous-réseau local 192.168.1.0/24
WEATHGARDS_ALLOWED_CLIENTS=192.168.1.0/24
```

#### Couche 3 — Rate limiting

`BearerAuthMiddleware` applique un compteur glissant de **60 requêtes par tranche de 60 secondes** par adresse IP cliente. Les requêtes en excès reçoivent HTTP 429 avec un en-tête `Retry-After`.

#### TLS (optionnel)

Si les fichiers `WEATHGARDS_TLS_CERT_FILE` et `WEATHGARDS_TLS_KEY_FILE` sont définis et accessibles au démarrage du serveur MCP, uvicorn démarre en HTTPS. Utiliser `scripts/generate-cert.sh <IP_LOCALE>` pour générer un certificat autosigné.

#### Principe de lecture seule

Les handlers MCP sont des fonctions Python **statiques et pré-écrites** qui effectuent uniquement des opérations de lecture (docker inspect, psutil, logs). Aucune opération d'écriture (arrêt de container, kill de processus) n'est implémentée dans le catalogue par défaut.

---

## 3. Installation

### 3.1 Prérequis système

| Prérequis | Version minimale | Obligatoire |
|-----------|-----------------|-------------|
| Python | 3.12 | Oui |
| uv (gestionnaire de paquets) | Dernière version | Oui |
| Node.js | 18 LTS | Seulement pour rebuilder le frontend |
| Docker Engine / Desktop | 24+ | Non (scan containers désactivé si absent) |

#### Vérification des prérequis

```bash
python3 --version   # → Python 3.12.x ou supérieur
uv --version        # → uv x.y.z
node --version      # → v18.x.x ou supérieur (optionnel)
docker --version    # → Docker version 24.x (optionnel)
```

### 3.2 Installation pas à pas — Linux

#### 1. Installer uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # ou ~/.zshrc selon votre shell
```

#### 2. Récupérer le projet

```bash
git clone <url-du-dépôt> weathgards
cd weathgards
```

#### 3. Installer les dépendances Python

```bash
uv sync
```

#### 4. Configurer l'environnement

```bash
cp .env.example .env
nano .env
```

Valeurs minimales à renseigner dans `.env` :

```env
# Obligatoire : token d'authentification MCP (chaîne aléatoire ≥ 32 caractères)
WEATHGARDS_MCP_TOKEN=

# Optionnel : générer un token automatiquement
# python3 -c "import secrets; print('wg-' + secrets.token_hex(32))"
```

#### 5. Construire le frontend (une seule fois)

```bash
cd frontend
npm install
npm run build
cd ..
```

#### 6. Démarrer WEATHGARDS

```bash
uv run weathgards
```

L'interface est disponible à **http://127.0.0.1:8765**.

#### 7. Permissions Docker (si Docker est installé)

```bash
# Ajouter l'utilisateur courant au groupe docker
sudo usermod -aG docker $USER
# Puis se déconnecter/reconnecter, ou :
newgrp docker
```

---

### 3.3 Installation pas à pas — macOS

#### 1. Installer les outils de base

```bash
# Homebrew (si absent)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.12+ via pyenv ou Homebrew
brew install python@3.12

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. Récupérer le projet et installer

```bash
git clone <url-du-dépôt> weathgards
cd weathgards
uv sync
```

#### 3. Configurer l'environnement

```bash
cp .env.example .env
# Éditer avec nano, vim, ou :
open -e .env
```

Renseigner `WEATHGARDS_MCP_TOKEN` avec une valeur aléatoire sécurisée.

#### 4. Construire le frontend

```bash
cd frontend && npm install && npm run build && cd ..
```

#### 5. Docker Desktop (optionnel)

Télécharger et installer **Docker Desktop pour Mac** depuis [docker.com](https://www.docker.com/products/docker-desktop/).  
Démarrer l'application (icône baleine dans la barre de menus) **avant** de lancer WEATHGARDS.

#### 6. Démarrer

```bash
uv run weathgards
```

---

### 3.4 Installation pas à pas — Windows

Toutes les commandes sont pour **PowerShell** (pas cmd).

#### 1. Installer Python 3.12+

Télécharger depuis [python.org](https://www.python.org/downloads/windows/). Cocher **"Add Python to PATH"** lors de l'installation.

#### 2. Installer uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Redémarrer PowerShell après l'installation.

#### 3. Récupérer le projet

```powershell
git clone <url-du-dépôt> weathgards
cd weathgards
uv sync
```

#### 4. Configurer l'environnement

```powershell
Copy-Item .env.example .env
notepad .env
```

Renseigner `WEATHGARDS_MCP_TOKEN`.

#### 5. Construire le frontend

```powershell
cd frontend
npm install
npm run build
cd ..
```

#### 6. Docker Desktop (optionnel)

Installer **Docker Desktop pour Windows** (WSL 2 requis). Le démarrer avant WEATHGARDS.

#### 7. Démarrer

```powershell
uv run weathgards
```

---

### 3.5 Vérification de l'installation

Après démarrage, effectuer les vérifications suivantes :

```bash
# 1. L'API répond
curl http://127.0.0.1:8765/api/health
# Réponse attendue : {"status":"ok","os":"linux","docker_available":true}

# 2. Le scan fonctionne
curl http://127.0.0.1:8765/api/scan
# Réponse attendue : liste JSON (peut être vide)

# 3. L'interface s'affiche
# Ouvrir http://127.0.0.1:8765 dans un navigateur
```

Les tests automatisés d'acceptance sont disponibles via :

```bash
uv run pytest tests/test_smoke.py --no-cov -v
```

---

## 4. Administration

### 4.1 Démarrage et arrêt

#### Démarrage standard

```bash
uv run weathgards
```

#### Démarrage avec rechargement automatique (développement)

```bash
uv run weathgards --reload
```

#### Démarrage sur un port ou hôte personnalisé

```bash
uv run weathgards --host 0.0.0.0 --port 9000
```

Les arguments de ligne de commande ont priorité sur les variables d'environnement.

#### Arrêt

`Ctrl+C` dans le terminal. WEATHGARDS effectue un arrêt propre (shutdown graceful) :
1. Arrêt du serveur MCP interne s'il est en cours d'exécution.
2. Journalisation de l'événement `weathgards.shutdown`.
3. Libération du port.

#### Démarrage en tant que service système

**Linux (systemd) :**

```ini
# /etc/systemd/system/weathgards.service
[Unit]
Description=WEATHGARDS MCP Gateway
After=network.target docker.service

[Service]
Type=simple
User=votre-utilisateur
WorkingDirectory=/opt/weathgards
EnvironmentFile=/opt/weathgards/.env
ExecStart=/opt/weathgards/.venv/bin/weathgards
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weathgards
sudo systemctl status weathgards
```

**macOS (launchd) :**

```xml
<!-- ~/Library/LaunchAgents/com.weathgards.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
  <key>Label</key>        <string>com.weathgards</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/vous/weathgards/.venv/bin/weathgards</string>
  </array>
  <key>WorkingDirectory</key> <string>/Users/vous/weathgards</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>WEATHGARDS_MCP_TOKEN</key> <string>votre-token</string>
  </dict>
  <key>RunAtLoad</key> <true/>
  <key>KeepAlive</key> <true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.weathgards.plist
```

---

### 4.2 Configuration de l'environnement

Le fichier `.env` (à la racine du projet) contrôle les paramètres de démarrage. Ces valeurs sont chargées **une seule fois** au lancement et ne peuvent pas être modifiées sans redémarrage.

| Variable | Défaut | Description |
|----------|--------|-------------|
| `WEATHGARDS_HOST` | `127.0.0.1` | Adresse d'écoute de l'interface cockpit |
| `WEATHGARDS_PORT` | `8765` | Port de l'interface cockpit |
| `WEATHGARDS_ENV` | `development` | `development` ou `production` (désactive `/docs` en prod) |
| `WEATHGARDS_MCP_TOKEN` | `CHANGE_ME` | Réservé — non utilisé à ce stade. Le token MCP est **auto-généré** au premier démarrage et stocké dans `<config_dir>/mcp.token` |
| `WEATHGARDS_ALLOWED_CLIENTS` | *(vide)* | Plages CIDR autorisées, séparées par des virgules. Vide = pas de restriction IP |
| `WEATHGARDS_DOCKER_HOST` | *(auto)* | URI du socket Docker (ex. `unix:///var/run/docker.sock`) |
| `WEATHGARDS_DOCKER_TIMEOUT` | `10` | Timeout des appels Docker en secondes |
| `WEATHGARDS_SCAN_INTERVAL` | `30` | Intervalle de scan automatique en secondes |
| `WEATHGARDS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `WEATHGARDS_LOG_FORMAT` | `console` | `console` (lisible) ou `json` (pour ingestion par ELK/Loki) |
| `WEATHGARDS_TLS_CERT_FILE` | *(vide)* | Chemin vers le certificat TLS (ex. `certs/weathgards.crt`). Si défini avec `TLS_KEY_FILE`, le serveur MCP démarre en HTTPS |
| `WEATHGARDS_TLS_KEY_FILE` | *(vide)* | Chemin vers la clé privée TLS (ex. `certs/weathgards.key`) |
| `WEATHGARDS_PROCESS_INCLUDE_PATTERNS` | *(vide)* | Patterns de noms de processus à inclure dans le scan, séparés par des virgules. Vide = tous les processus visibles |

#### Paramètres runtime (sans redémarrage)

Les paramètres suivants sont modifiables via l'onglet **Configuration** de l'interface. Ils sont persistés dans `<répertoire-config>/settings.json` :

| Paramètre | Description |
|-----------|-------------|
| Hôte MCP | Adresse d'écoute du serveur MCP (`127.0.0.1` ou `0.0.0.0`) |
| Port MCP | Port du serveur MCP (défaut : 9766) |
| Exposition réseau | Active le binding `0.0.0.0` avec auth Bearer obligatoire |
| Intervalle auto-scan | 0 = manuel uniquement, sinon en secondes |
| Sources actives | Activer/désactiver Docker, processus, services individuellement |

#### Répertoire de configuration

Les fichiers de configuration et tokens sont stockés dans :

| OS | Chemin |
|----|--------|
| Linux | `~/.local/share/weathgards/` |
| macOS | `~/Library/Application Support/weathgards/` |
| Windows | `C:\Users\<user>\AppData\Local\weathgards\weathgards\` |

---

### 4.3 Gestion des outils MCP

#### Catalogue d'outils

Le catalogue est fixe et défini dans `src/weathgards/mcp_server/tools/catalog.py`. Pour consulter les outils disponibles :

- Interface : onglet **Dashboard** → cliquer sur une carte service → volet "Outils MCP disponibles"
- API : `GET /api/catalog`

Outils disponibles dans la version actuelle :

| Nom | Cible | Description |
|-----|-------|-------------|
| `docker_container_status` | Container Docker | Statut, santé, image, code de sortie, timestamps |
| `docker_container_logs` | Container Docker | Dernières lignes de logs avec timestamps (paramètre `lines`, défaut 50, max 500) |
| `docker_list_containers` | *(aucune)* | Liste tous les containers (actifs et arrêtés) avec nom, image, statut |
| `process_status` | Processus | CPU %, mémoire RSS (Mo), ports en écoute, statut — par nom ou PID |

#### Activer un outil

1. Aller sur le **Dashboard**.
2. Cliquer sur le bouton **"Démarrer un scan"** pour détecter les services.
3. Sur une carte service, cliquer **"Activer un outil MCP"**.
4. Dans le volet latéral, choisir l'outil souhaité et cliquer **"Activer pour cette cible"**.

L'activation est **idempotente** : activer deux fois le même (outil, cible) retourne l'entrée existante.

#### Tester un outil

Depuis le volet d'activation, cliquer **"Tester maintenant"** pour exécuter le handler directement (sans passer par le LLM) et voir le résultat JSON.

#### Désactiver un outil

Aller sur l'onglet **Outils MCP** → cliquer l'icône poubelle de l'outil concerné.

> **Attention :** La désactivation prend effet dans le serveur MCP sous 5 secondes (hot-reload automatique du registre).

---

### 4.4 Connexion d'un LLM distant

#### Prérequis

- Le serveur MCP doit être **démarré** (onglet Serveur).
- Le serveur doit être exposé sur le réseau (`0.0.0.0`).
- Le token MCP doit être configuré.

#### Récupérer les informations de connexion

1. Onglet **Serveur** → démarrer le serveur avec l'option réseau activée.
2. Section **"Informations de connexion"** → copier l'URL et le token.

L'API expose également `GET /api/mcp/snippets` qui retourne des extraits de configuration prêts à l'emploi pour tous les clients supportés (Claude Desktop, OpenCode, curl), que le serveur soit démarré ou non.

#### Configuration Claude Desktop

Éditer le fichier de configuration Claude Desktop :

```json
{
  "mcpServers": {
    "weathgards": {
      "url": "http://192.168.1.42:9766/mcp",
      "headers": {
        "Authorization": "Bearer votre-token"
      }
    }
  }
}
```

> Si TLS est activé, remplacer `http://` par `https://`.

Chemins du fichier de configuration :
- **macOS** : `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** : `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux** : `~/.config/Claude/claude_desktop_config.json`

#### Configuration OpenCode

```json
{
  "mcp": {
    "weathgards": {
      "type": "remote",
      "url": "http://192.168.1.42:9766/mcp",
      "headers": {
        "Authorization": "Bearer votre-token"
      }
    }
  }
}
```

#### Test de la connexion (curl)

```bash
curl -X POST http://192.168.1.42:9766/mcp \
  -H "Authorization: Bearer votre-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

---

### 4.5 Mise à jour

```bash
# 1. Arrêter WEATHGARDS (Ctrl+C)

# 2. Récupérer les modifications
git pull origin main

# 3. Mettre à jour les dépendances Python
uv sync

# 4. Rebuilder le frontend si nécessaire
cd frontend && npm install && npm run build && cd ..

# 5. Redémarrer
uv run weathgards
```

> Les paramètres stockés dans `settings.json` et le fichier `.env` sont préservés lors d'une mise à jour.

---

## 5. Dépannage

### 5.1 L'interface ne s'affiche pas

**Symptôme :** Le navigateur affiche une erreur de connexion sur `http://127.0.0.1:8765`.

**Causes et solutions :**

| Cause | Solution |
|-------|----------|
| WEATHGARDS n'est pas démarré | Lancer `uv run weathgards` et vérifier l'absence d'erreurs dans la console |
| Le port 8765 est déjà utilisé | Changer le port : `uv run weathgards --port 8766` ou modifier `WEATHGARDS_PORT` dans `.env` |
| Le frontend n'a pas été compilé | Exécuter `cd frontend && npm run build && cd ..` |
| Accès depuis une autre machine | Par défaut WEATHGARDS n'écoute que sur `127.0.0.1`. Ajouter `WEATHGARDS_HOST=0.0.0.0` dans `.env` pour l'exposer |

**Diagnostic :**

```bash
# Vérifier si le processus tourne
ps aux | grep weathgards          # Linux/macOS
Get-Process | Where Name -like "*weathgards*"  # Windows PowerShell

# Vérifier si le port répond
curl -v http://127.0.0.1:8765/api/health
```

---

### 5.2 Docker non détecté

**Symptôme :** L'interface affiche "Docker non détecté" et la catégorie Docker est absente des résultats de scan.

**Causes et solutions :**

| OS | Cause probable | Solution |
|----|----------------|----------|
| Linux | Le daemon Docker n'est pas démarré | `sudo systemctl start docker` |
| Linux | L'utilisateur n'est pas dans le groupe docker | `sudo usermod -aG docker $USER` puis se reconnecter |
| macOS | Docker Desktop n'est pas lancé | Démarrer Docker Desktop (icône baleine dans la barre de menus) |
| Windows | Docker Desktop n'est pas lancé | Démarrer Docker Desktop depuis le menu Démarrer |
| Tous | Socket personnalisé | Définir `WEATHGARDS_DOCKER_HOST=unix:///chemin/custom/docker.sock` dans `.env` |

**Diagnostic :**

```bash
# Linux/macOS — tester l'accès au socket
ls -la /var/run/docker.sock
docker ps

# Windows PowerShell — tester le pipe
Test-Path "\\.\pipe\docker_engine"
```

---

### 5.3 Le serveur MCP refuse de démarrer

**Symptôme :** Cliquer "Démarrer le serveur MCP" retourne une erreur.

#### Erreur : "Cannot expose MCP server on the network without a configured token"

Le fichier de token `<config_dir>/mcp.token` est absent ou vide. Ce fichier est normalement **auto-généré** au premier démarrage — il ne devrait pas manquer sauf suppression manuelle.

Pour le régénérer, supprimer le fichier et redémarrer WEATHGARDS :

```bash
# Linux
rm ~/.local/share/weathgards/mcp.token

# macOS
rm ~/Library/Application\ Support/weathgards/mcp.token

# Windows PowerShell
Remove-Item "$env:LOCALAPPDATA\weathgards\weathgards\mcp.token"
```

Le nouveau token sera affiché dans les logs au niveau `INFO` au prochain démarrage.

#### Erreur : "Port is already in use" / code 503

Le port MCP (9766 par défaut) est déjà occupé.

```bash
# Linux/macOS — identifier le processus
lsof -i :9766

# Windows PowerShell
netstat -ano | findstr :9766
```

Changer le port dans l'onglet **Configuration** ou dans `settings.json`.

---

### 5.4 Le LLM ne peut pas se connecter

**Symptôme :** Le LLM reçoit une erreur de connexion ou HTTP 401/403.

**Étapes de diagnostic :**

```bash
# 1. Vérifier que le serveur MCP est démarré
curl http://127.0.0.1:8765/api/mcp/status

# 2. Tester la connexion depuis la machine hôte
curl -X POST http://127.0.0.1:9766/mcp \
  -H "Authorization: Bearer votre-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# 3. Tester depuis le réseau local (remplacer l'IP)
curl -X POST http://192.168.1.42:9766/mcp \
  -H "Authorization: Bearer votre-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Connection refused` | Serveur MCP non démarré ou bind sur 127.0.0.1 | Démarrer avec l'option "Exposer sur le réseau" |
| HTTP 401 | Token incorrect ou absent | Vérifier que le token dans la config LLM correspond exactement à `WEATHGARDS_MCP_TOKEN` |
| HTTP 403 | IP non dans la liste blanche | Ajouter l'IP du client LLM à `WEATHGARDS_ALLOWED_CLIENTS` |
| `Network unreachable` | Pare-feu bloquant le port 9766 | Ouvrir le port dans le pare-feu système |

**Pare-feu :**

```bash
# Linux (ufw)
sudo ufw allow 9766/tcp

# Linux (firewalld)
sudo firewall-cmd --add-port=9766/tcp --permanent && sudo firewall-cmd --reload

# Windows PowerShell
New-NetFirewallRule -DisplayName "WEATHGARDS MCP" -Direction Inbound -Protocol TCP -LocalPort 9766 -Action Allow
```

---

### 5.5 Scan retourne toujours une liste vide

**Causes et solutions :**

| Cause | Solution |
|-------|----------|
| Toutes les sources désactivées dans Configuration | Ré-activer au moins une source dans l'onglet Configuration |
| Aucun processus ne correspond aux filtres | Vider `WEATHGARDS_PROCESS_INCLUDE_PATTERNS` dans `.env` |
| Permissions insuffisantes sur les processus | Lancer WEATHGARDS avec les droits nécessaires (non-root recommandé sauf nécessité) |
| systemd/launchd non disponible | Normal sur certains environnements conteneurisés ou minimaux |

---

### 5.6 Erreurs de port occupé

```bash
# Identifier quel processus utilise le port 8765 (cockpit)
# Linux/macOS
lsof -i :8765 -t | xargs kill -9   # force kill du processus occupant

# Windows PowerShell
$pid = (netstat -ano | Select-String ":8765").Line.Split()[-1]
Stop-Process -Id $pid -Force
```

---

### 5.7 Problèmes de permissions

**Linux — permission refusée sur le socket Docker :**

```bash
sudo chmod 666 /var/run/docker.sock  # solution temporaire
# Solution permanente :
sudo usermod -aG docker $USER && newgrp docker
```

**Linux — processus non visibles dans le scan :**

Certains processus système ne sont visibles que par root. WEATHGARDS fonctionne en tant qu'utilisateur normal et filtre automatiquement les processus inaccessibles. C'est le comportement attendu.

**macOS — "Operation not permitted" lors du scan de processus :**

Accorder les droits **"Accès au disque complet"** à Terminal (ou à l'application de votre choix) dans :  
`Préférences Système → Sécurité et confidentialité → Confidentialité → Accès au disque complet`

---

## 6. Nettoyage et désinstallation

### 6.1 Arrêt propre

Avant toute opération de nettoyage, arrêter proprement le service :

```bash
# Si lancé en premier plan : Ctrl+C

# Si lancé en service systemd (Linux) :
sudo systemctl stop weathgards
sudo systemctl disable weathgards

# Si lancé en launchd (macOS) :
launchctl unload ~/Library/LaunchAgents/com.weathgards.plist
```

Vérifier que plus aucun port n'est occupé :

```bash
# Linux/macOS
lsof -i :8765 -i :9766

# Windows PowerShell
netstat -ano | findstr "8765\|9766"
```

---

### 6.2 Suppression des données de configuration

Les fichiers de configuration persistée (token MCP, `settings.json`) sont stockés en dehors du répertoire du projet.

**Linux :**
```bash
rm -rf ~/.local/share/weathgards/
```

**macOS :**
```bash
rm -rf ~/Library/Application\ Support/weathgards/
```

**Windows (PowerShell) :**
```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\weathgards"
```

> Ces répertoires contiennent le **token MCP généré automatiquement** et le fichier `settings.json`. Leur suppression réinitialise complètement la configuration runtime.

---

### 6.3 Désinstallation complète

#### Étape 1 — Supprimer le répertoire projet

```bash
# Linux/macOS
rm -rf /chemin/vers/weathgards/

# Windows PowerShell
Remove-Item -Recurse -Force C:\chemin\vers\weathgards\
```

Cela supprime :
- Le code source
- L'environnement virtuel Python (`.venv/`)
- Le bundle frontend compilé (`frontend/dist/`)
- Le fichier `.env` et ses secrets
- Les caches Python et pytest

#### Étape 2 — Supprimer les données de configuration

Voir [section 6.2](#62-suppression-des-données-de-configuration).

#### Étape 3 — Supprimer les règles de pare-feu (si créées)

**Linux (ufw) :**
```bash
sudo ufw delete allow 9766/tcp
```

**Linux (firewalld) :**
```bash
sudo firewall-cmd --remove-port=9766/tcp --permanent && sudo firewall-cmd --reload
```

**Windows (PowerShell) :**
```powershell
Remove-NetFirewallRule -DisplayName "WEATHGARDS MCP"
```

#### Étape 4 — Supprimer le fichier de service système (si créé)

**Linux (systemd) :**
```bash
sudo systemctl disable weathgards
sudo rm /etc/systemd/system/weathgards.service
sudo systemctl daemon-reload
```

**macOS (launchd) :**
```bash
launchctl unload ~/Library/LaunchAgents/com.weathgards.plist
rm ~/Library/LaunchAgents/com.weathgards.plist
```

#### Étape 5 — Supprimer la configuration du client LLM

Retirer le bloc `"weathgards"` du fichier de configuration de votre client LLM (Claude Desktop, etc.) pour éviter des erreurs de connexion au prochain démarrage.

#### Vérification finale

```bash
# Aucun processus ne doit subsister
ps aux | grep weathgards          # Linux/macOS
Get-Process | Where Name -like "*weathgards*"  # Windows

# Aucun port ne doit être occupé
lsof -i :8765 -i :9766            # Linux/macOS
netstat -ano | findstr "8765\|9766"  # Windows
```

---

*WEATHGARDS v1.0.0*
