# WEATHGARDS

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Linux](https://img.shields.io/badge/Linux-supporté-FCC624?logo=linux&logoColor=black)](#prérequis)
[![macOS](https://img.shields.io/badge/macOS-supporté-000000?logo=apple&logoColor=white)](#prérequis)
[![Windows](https://img.shields.io/badge/Windows-supporté-0078D6?logo=windows&logoColor=white)](#prérequis)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-00D4FF)](https://modelcontextprotocol.io)
[![Version](https://img.shields.io/badge/version-1.0.0-7B2FBE)]()

**Passerelle MCP locale cross-OS pour containers Docker, processus et services.**

WEATHGARDS scanne votre machine (containers Docker, processus OS, services système), puis expose des outils MCP pré-écrits sur un endpoint réseau sécurisé. Un LLM distant (Claude, GPT-4, etc.) peut ainsi interroger votre environnement en temps réel — sans générer aucun code à l'exécution.

---

## Architecture en deux ports

| Composant | Port | Protocole | Usage |
|---|---|---|---|
| **Cockpit** (interface web + API REST) | `8765` | HTTP | Administration locale uniquement |
| **Serveur MCP** | `9766` | HTTP ou HTTPS | Connexion LLM, exposable sur le réseau |

Le cockpit reste toujours en HTTP car il est destiné à un accès local (`127.0.0.1`). Le serveur MCP peut être sécurisé en HTTPS via certificat autosigné lorsqu'il est exposé sur le réseau local.

---

## Prérequis

### Docker (optionnel)

WEATHGARDS fonctionne sans Docker ; le scan de containers est simplement désactivé si le daemon est inaccessible.

| OS | Installation |
|----|---------|
| **Linux** | `sudo apt install docker.io` (Debian/Ubuntu) ou [docs.docker.com](https://docs.docker.com/engine/install/). Ajoutez votre utilisateur au groupe docker : `sudo usermod -aG docker $USER` puis reconnectez-vous. |
| **macOS** | [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/). Démarrez l'application et attendez l'icône baleine dans la barre de menus. |
| **Windows** | [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) (nécessite WSL 2 ou Hyper-V). Démarrez Docker Desktop avant WEATHGARDS. |

### Python 3.12+

```bash
# Linux / macOS
python3 --version   # doit être ≥ 3.12

# Windows (PowerShell)
python --version
```

Installez [uv](https://docs.astral.sh/uv/getting-started/installation/) — le gestionnaire de paquets utilisé :

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Installation rapide

```bash
# 1. Cloner
git clone https://github.com/your-org/weathgards.git
cd weathgards

# 2. Installer les dépendances Python
uv sync

# 3. Configurer l'environnement (méthode interactive recommandée)
./deploy.sh

# ou manuellement :
cp .env.example .env   # Linux / macOS
# éditez .env — au minimum WEATHGARDS_MCP_TOKEN

# 4. Compiler le frontend (nécessite Node.js 18+, à faire une seule fois)
cd frontend && npm install && npm run build && cd ..

# 5. Démarrer WEATHGARDS
uv run weathgards
```

Ouvrez **http://127.0.0.1:8765** dans votre navigateur.

---

## Référence rapide par OS

### Linux

```bash
uv sync
cp .env.example .env
# nano .env  →  définissez WEATHGARDS_MCP_TOKEN
uv run weathgards
```

Socket Docker sur `/var/run/docker.sock`. Si absent, le scan containers est ignoré automatiquement.

### macOS

```bash
uv sync
cp .env.example .env
# open -e .env  →  définissez WEATHGARDS_MCP_TOKEN
uv run weathgards
```

Docker Desktop doit être démarré avant WEATHGARDS. Le socket est détecté automatiquement sous `/var/run/docker.sock` et le chemin Docker Desktop.

### Windows (PowerShell)

```powershell
uv sync
Copy-Item .env.example .env
# notepad .env  →  définissez WEATHGARDS_MCP_TOKEN
uv run weathgards
```

Docker Desktop doit être démarré. Le named pipe `\\.\pipe\docker_engine` est vérifié automatiquement. Aucun privilège administrateur requis.

---

## Connecter un LLM distant

Une fois WEATHGARDS démarré avec l'exposition réseau activée, votre client LLM a besoin de trois informations : l'**URL de l'endpoint**, le **token Bearer**, et le **snippet de configuration MCP**.

### Étape 1 — Activer l'exposition réseau

Dans l'onglet **Serveur** du cockpit :
1. Activez le toggle **"Exposer sur le réseau local"**
2. Cliquez **"Démarrer le serveur MCP"**

Ou configurez-le de façon persistante dans `.env` avant le démarrage :

```env
WEATHGARDS_MCP_TOKEN=votre-token-secret-ici
WEATHGARDS_HOST=0.0.0.0
```

### Étape 2 — Récupérer l'endpoint et le token

La section **Informations de connexion** affiche les valeurs en direct :

```
Endpoint MCP : http://192.168.1.42:9766/mcp
Token        : wg-xxxxxxxxxxxxxxxxxxxx
```

Si TLS est activé, l'URL sera `https://`.

### Étape 3 — Configurer votre client MCP

Collez le snippet JSON généré (bouton "Copier") dans la config de Claude Desktop / votre client MCP :

```json
{
  "mcpServers": {
    "weathgards": {
      "url": "http://192.168.1.42:9766/mcp",
      "headers": {
        "Authorization": "Bearer wg-xxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

> **Emplacement du fichier de config Claude Desktop :**
> - macOS : `~/Library/Application Support/Claude/claude_desktop_config.json`
> - Windows : `%APPDATA%\Claude\claude_desktop_config.json`
> - Linux : `~/.config/Claude/claude_desktop_config.json`

---

## TLS / HTTPS pour le serveur MCP

Le serveur MCP (port 9766) peut être sécurisé en HTTPS via un certificat autosigné. Cette option est recommandée dès que le serveur est exposé sur le réseau local.

> Le cockpit (port 8765) reste en HTTP — il est accessible localement uniquement et ne nécessite pas TLS.

### Générer le certificat

```bash
# Remplacez l'IP par celle de votre machine sur le réseau local
./scripts/generate-cert.sh 192.168.1.42
```

Le script génère deux fichiers dans `certs/` :
- `certs/weathgards.crt` — certificat public (à distribuer aux clients)
- `certs/weathgards.key` — clé privée (ne jamais partager)

Le certificat est valide 397 jours (limite imposée par Apple/iOS depuis 2020).

### Activer TLS dans `.env`

```env
WEATHGARDS_TLS_CERT_FILE=certs/weathgards.crt
WEATHGARDS_TLS_KEY_FILE=certs/weathgards.key
```

Redémarrez WEATHGARDS — le log de démarrage confirme :
```
mcp_server.tls_active  Serveur MCP démarré en HTTPS (TLS activé)
```

Le cockpit affiche alors `https://` dans la section **Informations de connexion**, et les snippets générés (Claude Desktop, opencode, curl) utilisent automatiquement le bon schéma.

### Faire confiance au certificat autosigné côté client

Un certificat autosigné est rejeté par défaut. Selon votre client :

**curl / test manuel :**
```bash
curl --cacert certs/weathgards.crt \
  -X POST https://192.168.1.42:9766/mcp \
  -H "Authorization: Bearer wg-xxx" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

**Claude Desktop (et clients HTTP système) :**
Ajoutez le certificat au trust store OS de la machine cliente :

```bash
# Linux (Debian/Ubuntu)
sudo cp certs/weathgards.crt /usr/local/share/ca-certificates/weathgards.crt
sudo update-ca-certificates

# macOS
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain certs/weathgards.crt

# Windows (PowerShell, en tant qu'administrateur)
Import-Certificate -FilePath .\certs\weathgards.crt `
  -CertStoreLocation Cert:\LocalMachine\Root
```

### Renouveler le certificat

Le certificat expire après 397 jours. Pour le renouveler :

```bash
# Régénérer (écrase l'ancien)
./scripts/generate-cert.sh 192.168.1.42

# Redémarrer le serveur MCP depuis le cockpit ou :
# Ctrl+C puis uv run weathgards
```

Le certificat renouvelé doit être redistribué aux machines clientes et re-importé dans leur trust store.

---

## Sécurité

> **L'exposition réseau exige une authentification — sans exception.**

Lier le serveur MCP à `0.0.0.0` le rend accessible à chaque appareil du réseau local. WEATHGARDS enforce un token Bearer sur chaque requête `/mcp` et **refuse de démarrer en mode réseau sans token configuré**.

**Durcissement recommandé :**

- Définissez `WEATHGARDS_MCP_TOKEN` avec une chaîne aléatoire longue (≥ 32 caractères) :
  ```bash
  python3 -c "import secrets; print('wg-' + secrets.token_hex(32))"
  ```
- Restreignez l'accès à un sous-réseau précis via `WEATHGARDS_ALLOWED_CLIENTS=192.168.1.0/24` dans `.env`.
- Activez TLS (voir section ci-dessus) pour chiffrer le trafic sur le réseau local.
- Ne committez jamais votre fichier `.env` — il est déjà dans `.gitignore`.
- N'exposez pas WEATHGARDS sur un réseau public. Il est conçu pour un sous-réseau local de confiance uniquement.

**Couches de protection actives :**

| Couche | Mécanisme |
|---|---|
| Authentification | Bearer token, comparaison en temps constant (anti timing-oracle) |
| Rate limiting | 60 requêtes / 60 secondes par IP cliente, retourne 429 + `Retry-After` |
| IP allowlist | Filtre CIDR optionnel appliqué avant l'auth (`WEATHGARDS_ALLOWED_CLIENTS`) |
| Chiffrement réseau | TLS optionnel via certificat autosigné (port MCP uniquement) |
| Protection DNS rebinding | Désactivée pour le bind réseau (le token est la protection) ; activée pour localhost |

---

## Développement

```bash
# Installer avec les extras dev
uv sync --extra dev

# Démarrer avec auto-reload
uv run weathgards --reload

# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests

# Vérification des types
uv run mypy src

# Tests (avec couverture)
uv run pytest

# Tests — rapides, sans couverture
uv run pytest --no-cov

# Smoke tests uniquement
uv run pytest tests/test_smoke.py --no-cov -v

# Compiler le frontend
cd frontend && npm run build
```

---

## Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `WEATHGARDS_HOST` | `127.0.0.1` | Adresse d'écoute du cockpit. `0.0.0.0` = toutes les interfaces. |
| `WEATHGARDS_PORT` | `8765` | Port du cockpit. |
| `WEATHGARDS_ENV` | `development` | `production` désactive `/docs` (Swagger). |
| `WEATHGARDS_MCP_TOKEN` | `CHANGE_ME` | Token Bearer du serveur MCP. Obligatoire en mode réseau. |
| `WEATHGARDS_ALLOWED_CLIENTS` | _(vide)_ | CIDRs autorisés, séparés par virgule. Vide = token-only. |
| `WEATHGARDS_TLS_CERT_FILE` | _(vide)_ | Chemin vers le certificat TLS (`.crt`). TLS désactivé si vide. |
| `WEATHGARDS_TLS_KEY_FILE` | _(vide)_ | Chemin vers la clé privée TLS (`.key`). TLS désactivé si vide. |
| `WEATHGARDS_DOCKER_HOST` | _(auto)_ | URI du socket Docker. Vide = détection automatique par OS. |
| `WEATHGARDS_DOCKER_TIMEOUT` | `10` | Timeout (secondes) des appels au daemon Docker. |
| `WEATHGARDS_SCAN_INTERVAL` | `30` | Intervalle de scan automatique en secondes. `0` = manuel uniquement. |
| `WEATHGARDS_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `WEATHGARDS_LOG_FORMAT` | `console` | `console` (lisible) ou `json` (ELK/Loki). |
