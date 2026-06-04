#!/usr/bin/env bash
# deploy.sh — installateur interactif WEATHGARDS v1.0.0
#
# Usage : ./deploy.sh
# Rend l'installation complète sans éditer aucun fichier manuellement.
#
# Compatibilité : Linux, macOS, Windows (Git Bash / WSL uniquement).
# Ne contient aucune ligne PowerShell ; les utilisateurs Windows hors Git Bash
# ou WSL sont redirigés vers la procédure PowerShell de la documentation.

set -euo pipefail

# ---------------------------------------------------------------------------
# Couleurs ANSI — désactivées automatiquement si la sortie n'est pas un TTY.
# Cela évite des séquences d'échappement parasites dans les logs CI/CD.
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_CYAN="\033[36m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_RED="\033[31m"
    C_DIM="\033[2m"
    C_MAGENTA="\033[35m"
else
    C_RESET="" C_BOLD="" C_CYAN="" C_GREEN="" C_YELLOW="" C_RED="" C_DIM="" C_MAGENTA=""
fi

# ---------------------------------------------------------------------------
# Variables globales d'état (renseignées au fil des étapes)
# ---------------------------------------------------------------------------
STEP_NAME=""          # nom de l'étape courante pour le trap d'erreur
WG_HOST=""            # valeur finale de WEATHGARDS_HOST
WG_PORT=""            # valeur finale de WEATHGARDS_PORT
WG_TOKEN=""           # valeur finale de WEATHGARDS_MCP_TOKEN (masquée à l'affichage)
NODE_AVAILABLE=false  # Node.js >= 18 détecté
DOCKER_AVAILABLE=false
EXPOSE_NETWORK=false  # true si HOST = 0.0.0.0
SERVICE_INSTALLED=false

# ---------------------------------------------------------------------------
# Trap d'erreur — affiché dès qu'une commande échoue (set -e).
# Indique l'étape échouée et comment reprendre.
# ---------------------------------------------------------------------------
trap 'on_error $LINENO' ERR

on_error() {
    local line="$1"
    echo ""
    echo -e "${C_RED}${C_BOLD}✗ Erreur à la ligne ${line} — étape : ${STEP_NAME:-inconnue}${C_RESET}"
    echo -e "${C_YELLOW}  Pour reprendre, relancez simplement :  ./deploy.sh${C_RESET}"
    echo -e "${C_DIM}  Le script est idempotent et reprendra en proposant de réutiliser${C_RESET}"
    echo -e "${C_DIM}  ce qui a déjà été installé (.venv, frontend/dist, .env).${C_RESET}"
    echo ""
    exit 1
}

# ---------------------------------------------------------------------------
# Helpers d'affichage
# ---------------------------------------------------------------------------
step_header() {
    echo ""
    echo -e "${C_CYAN}${C_BOLD}━━━  $1  ━━━${C_RESET}"
}

info()    { echo -e "  ${C_DIM}→${C_RESET} $*"; }
success() { echo -e "  ${C_GREEN}✓${C_RESET} $*"; }
warn()    { echo -e "  ${C_YELLOW}⚠${C_RESET} $*"; }
error()   { echo -e "  ${C_RED}✗${C_RESET} $*"; }

ask() {
    # ask "Question" "défaut" → stocke la réponse dans $REPLY
    local prompt="$1" default="$2"
    if [ -n "$default" ]; then
        echo -en "  ${C_BOLD}$prompt${C_RESET} ${C_DIM}[$default]${C_RESET} : "
    else
        echo -en "  ${C_BOLD}$prompt${C_RESET} : "
    fi
    read -r REPLY
    if [ -z "$REPLY" ] && [ -n "$default" ]; then
        REPLY="$default"
    fi
}

ask_yn() {
    # ask_yn "Question" → retourne 0 (oui) ou 1 (non)
    local prompt="$1" default="${2:-n}"
    local choices
    if [ "$default" = "y" ]; then choices="[O/n]"; else choices="[o/N]"; fi
    echo -en "  ${C_BOLD}$prompt${C_RESET} $choices : "
    read -r REPLY
    REPLY="${REPLY:-$default}"
    case "${REPLY,,}" in
        o|y|oui|yes) return 0 ;;
        *)            return 1 ;;
    esac
}

mask_token() {
    # Affiche les 6 premiers caractères puis ****
    local tok="$1"
    echo "${tok:0:6}****${tok: -4}"
}

# ---------------------------------------------------------------------------
# Se placer dans le répertoire du script, quel que soit le cwd d'appel.
# Cela garantit que tous les chemins relatifs (.env, .venv, frontend/) sont
# résolus par rapport à la racine du projet WEATHGARDS.
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ===========================================================================
# ÉTAPE 0 — Bannière & détection environnement
# ===========================================================================
STEP_NAME="0 — Bannière & détection environnement"

clear 2>/dev/null || true

echo -e "${C_CYAN}${C_BOLD}"
cat << 'BANNER'
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   ██╗    ██╗███████╗ █████╗ ████████╗██╗  ██╗           ║
  ║   ██║    ██║██╔════╝██╔══██╗╚══██╔══╝██║  ██║           ║
  ║   ██║ █╗ ██║█████╗  ███████║   ██║   ███████║           ║
  ║   ██║███╗██║██╔══╝  ██╔══██║   ██║   ██╔══██║           ║
  ║   ╚███╔███╔╝███████╗██║  ██║   ██║   ██║  ██║           ║
  ║    ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝           ║
  ║                                                          ║
  ║    ██████╗  █████╗ ██████╗ ██████╗ ███████╗             ║
  ║   ██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██╔════╝             ║
  ║   ██║  ███╗███████║██████╔╝██║  ██║███████╗             ║
  ║   ██║   ██║██╔══██║██╔══██╗██║  ██║╚════██║             ║
  ║   ╚██████╔╝██║  ██║██║  ██║██████╔╝███████║             ║
  ║    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝             ║
  ║                                                          ║
  ║         Passerelle MCP locale · v1.0.0                  ║
  ║      Docker · Processus · Services → LLM                ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
BANNER
echo -e "${C_RESET}"

echo -e "  Ce script installe et configure WEATHGARDS de A à Z."
echo -e "  Chaque étape est expliquée avant exécution."
echo -e "  Entrée vide = valeur par défaut entre crochets."
echo ""

# Détection OS via uname (POSIX, fonctionne dans Git Bash et WSL)
RAW_OS="$(uname -s 2>/dev/null || echo "Unknown")"
ARCH="$(uname -m 2>/dev/null || echo "unknown")"

case "$RAW_OS" in
    Linux*)
        # Distinguer WSL de Linux natif (informatif seulement)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            OS_LABEL="Linux (WSL)"
        else
            OS_LABEL="Linux"
        fi
        OS_TYPE="linux"
        CONFIG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/weathgards"
        ;;
    Darwin*)
        OS_LABEL="macOS"
        OS_TYPE="macos"
        CONFIG_DIR="$HOME/Library/Application Support/weathgards"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OS_LABEL="Windows (Git Bash)"
        OS_TYPE="windows"
        # $LOCALAPPDATA est défini par Windows et disponible dans Git Bash
        CONFIG_DIR="${LOCALAPPDATA:-$HOME/AppData/Local}/weathgards/weathgards"
        ;;
    *)
        # Si l'OS n'est ni Linux, ni macOS, ni Git Bash/WSL, guider l'utilisateur.
        echo -e "${C_RED}${C_BOLD}"
        echo "  OS non supporté par ce script Bash : $RAW_OS"
        echo ""
        echo "  Si vous êtes sous Windows, utilisez :"
        echo "    • Git Bash (recommandé) : lancez Git Bash depuis le menu Démarrer"
        echo "    • WSL                   : ouvrez un terminal WSL Ubuntu"
        echo ""
        echo "  Pour une installation PowerShell native (Windows uniquement),"
        echo "  consultez la section 3.4 de DOCUMENTATION.md."
        echo -e "${C_RESET}"
        exit 1
        ;;
esac

CURRENT_SHELL="${SHELL:-bash}"
echo -e "  ${C_BOLD}Environnement détecté${C_RESET}"
echo -e "  ┌─────────────────────────────────────────────┐"
echo -e "  │  OS          : ${C_CYAN}${OS_LABEL}${C_RESET} (${ARCH})"
echo -e "  │  Shell       : ${CURRENT_SHELL}"
echo -e "  │  Répertoire  : ${SCRIPT_DIR}"
echo -e "  │  Config dir  : ${CONFIG_DIR}"
echo -e "  └─────────────────────────────────────────────┘"
echo ""

# ===========================================================================
# ÉTAPE 1 — Vérification des prérequis
# ===========================================================================
STEP_NAME="1 — Vérification des prérequis"
step_header "ÉTAPE 1 — Vérification des prérequis"

echo ""
echo "  Nous vérifions que tous les outils nécessaires sont disponibles."
echo "  Python et uv sont obligatoires. Node.js est requis seulement pour"
echo "  (re)construire le frontend. Docker est optionnel."
echo ""

# ── Python ≥ 3.12 ──────────────────────────────────────────────────────────
PYTHON_OK=false
PYTHON_BIN=""

# Chercher python3 ou python selon l'OS
for candidate in python3 python python3.12 python3.13; do
    if command -v "$candidate" &>/dev/null; then
        ver_str="$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+'| head -1)"
        major="${ver_str%%.*}"
        minor="${ver_str##*.}"
        if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 12 ]; then
            PYTHON_OK=true
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if $PYTHON_OK; then
    PY_VERSION="$($PYTHON_BIN --version 2>&1)"
    success "Python    : ${PY_VERSION}  (${PYTHON_BIN})"
else
    error "Python    : MANQUANT ou < 3.12"
    echo ""
    echo -e "  ${C_RED}${C_BOLD}Python 3.12+ est obligatoire.${C_RESET}"
    echo "  Instructions d'installation :"
    echo "    • Linux  : sudo apt install python3.12  (Debian/Ubuntu)"
    echo "               sudo dnf install python3.12  (Fedora/RHEL)"
    echo "    • macOS  : brew install python@3.12"
    echo "    • Toutes : https://www.python.org/downloads/"
    echo ""
    exit 1
fi

# ── uv ─────────────────────────────────────────────────────────────────────
UV_OK=false
if command -v uv &>/dev/null; then
    UV_VERSION="$(uv --version 2>&1 | head -1)"
    UV_OK=true
    success "uv        : ${UV_VERSION}"
else
    warn "uv        : MANQUANT"
    echo ""
    echo "  uv est le gestionnaire de paquets Python requis par WEATHGARDS."
    echo "  Il est plus rapide que pip et gère automatiquement le venv."
    echo ""
    if ask_yn "Installer uv automatiquement via le script officiel ?" "y"; then
        echo ""
        info "Téléchargement et installation de uv depuis https://astral.sh/uv/install.sh …"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Recharger le PATH pour trouver uv immédiatement
        # (le script d'install ajoute ~/.cargo/bin ou ~/.local/bin selon l'OS)
        export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
        if command -v uv &>/dev/null; then
            UV_VERSION="$(uv --version 2>&1 | head -1)"
            UV_OK=true
            success "uv installé : ${UV_VERSION}"
        else
            error "uv installé mais introuvable dans le PATH."
            echo "  Fermez ce terminal, rouvrez-en un, et relancez ./deploy.sh"
            exit 1
        fi
    else
        echo ""
        error "uv est obligatoire. Installation abandonnée."
        echo "  Pour l'installer manuellement :"
        echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

# ── Node.js ≥ 18 ───────────────────────────────────────────────────────────
NODE_OK=false
if command -v node &>/dev/null; then
    NODE_RAW="$(node --version 2>&1 | grep -oE '[0-9]+'| head -1)"
    if [ "${NODE_RAW:-0}" -ge 18 ]; then
        NODE_OK=true
        NODE_AVAILABLE=true
        success "Node.js   : $(node --version)  (npm $(npm --version 2>/dev/null || echo '?'))"
    else
        warn "Node.js   : $(node --version) — VERSION < 18 (build frontend impossible)"
    fi
else
    warn "Node.js   : MANQUANT"
fi

if ! $NODE_OK; then
    echo ""
    echo -e "  ${C_YELLOW}Node.js ≥ 18 est requis pour compiler le frontend React.${C_RESET}"
    echo "  Si frontend/dist/ existe déjà (build précédent), le cockpit"
    echo "  fonctionnera quand même sans recompiler."
    echo ""
    if [ -f "frontend/dist/index.html" ]; then
        warn "Un build frontend existant a été détecté — il sera réutilisé."
    else
        warn "Aucun build frontend détecté. Le cockpit sera inaccessible."
        echo "  Installez Node.js 18 LTS depuis https://nodejs.org/ puis relancez."
    fi
    echo ""
    if ! ask_yn "Continuer quand même sans Node.js ?" "y"; then
        echo ""
        info "Installation interrompue à la demande."
        exit 0
    fi
fi

# ── Docker (optionnel) ─────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
    DOCKER_VERSION="$(docker --version 2>&1 | head -1)"
    # Tester l'accès effectif au daemon (sans sudo)
    if docker info &>/dev/null 2>&1; then
        DOCKER_AVAILABLE=true
        success "Docker    : ${DOCKER_VERSION}  (daemon accessible)"
    else
        warn "Docker    : ${DOCKER_VERSION}  — daemon inaccessible (permissions ?)"
        info "Le scan Docker sera désactivé jusqu'à résolution (étape 5)."
    fi
else
    info "Docker    : non installé (optionnel — scan containers désactivé)"
fi

# ── Récapitulatif ──────────────────────────────────────────────────────────
echo ""
echo -e "  ${C_BOLD}Récapitulatif des prérequis :${C_RESET}"
echo "  ┌──────────────┬──────────────────────────────────────────────┐"
printf "  │ %-12s │ %-44s │\n" "Python 3.12+" "$( $PYTHON_OK && echo "✓ OK — $($PYTHON_BIN --version 2>&1)" || echo "✗ MANQUANT")"
printf "  │ %-12s │ %-44s │\n" "uv" "$( $UV_OK && echo "✓ OK" || echo "✗ MANQUANT")"
printf "  │ %-12s │ %-44s │\n" "Node.js ≥18" "$( $NODE_OK && echo "✓ OK" || echo "⚠ ABSENT/OLD (frontend)")"
printf "  │ %-12s │ %-44s │\n" "Docker" "$( $DOCKER_AVAILABLE && echo "✓ OK" || echo "○ OPTIONNEL — scan containers off")"
echo "  └──────────────┴──────────────────────────────────────────────┘"
echo ""

# ===========================================================================
# ÉTAPE 2 — Dépendances Python
# ===========================================================================
STEP_NAME="2 — Dépendances Python"
step_header "ÉTAPE 2 — Dépendances Python"
echo ""
echo "  'uv sync' lit pyproject.toml et uv.lock pour installer exactement"
echo "  les versions testées de toutes les dépendances Python dans .venv/."
echo "  Cette étape est idempotente : si .venv est déjà à jour, elle est quasi-instantanée."
echo ""
info "Lancement de : uv sync"
uv sync
success "Dépendances Python installées."

# ===========================================================================
# ÉTAPE 3 — Configuration interactive du fichier .env
# ===========================================================================
STEP_NAME="3 — Configuration .env"
step_header "ÉTAPE 3 — Configuration du fichier .env"
echo ""
echo "  Le fichier .env contrôle tous les paramètres de démarrage de WEATHGARDS."
echo "  Il est chargé au lancement et est le seul endroit à modifier pour reconfigurer."
echo ""

ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

# -- Gestion du .env existant -----------------------------------------------
EXISTING_ENV=false
ENV_ACTION="write"   # write | keep | modify

if [ -f "$ENV_FILE" ]; then
    EXISTING_ENV=true
    echo -e "  ${C_YELLOW}Un fichier .env existe déjà.${C_RESET}  Voici ses valeurs actuelles :"
    echo ""

    # Afficher les valeurs actuelles en masquant le token
    while IFS= read -r line || [ -n "$line" ]; do
        # Ignorer les commentaires et les lignes vides
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// /}" ]] && continue
        key="${line%%=*}"
        val="${line#*=}"
        if [[ "$key" == *TOKEN* ]]; then
            echo "    ${key}=$(mask_token "$val")"
        else
            echo "    ${line}"
        fi
    done < "$ENV_FILE"

    echo ""
    echo "  Options :"
    echo "    [G] Garder tel quel (ignorer cette étape)"
    echo "    [R] Réécrire entièrement (sauvegarde en .env.bak)"
    echo "    [M] Modifier valeur par valeur"
    echo ""
    ask "Votre choix" "G"
    case "${REPLY^^}" in
        G) ENV_ACTION="keep" ;;
        R) ENV_ACTION="write" ;;
        M) ENV_ACTION="modify" ;;
        *) ENV_ACTION="keep" ;;
    esac

    if [ "$ENV_ACTION" != "keep" ]; then
        cp "$ENV_FILE" "${ENV_FILE}.bak"
        info "Sauvegarde de l'ancien .env dans .env.bak"
    fi
fi

if [ "$ENV_ACTION" = "keep" ]; then
    success ".env conservé tel quel."
    # Lire les valeurs pour les utiliser dans les étapes suivantes
    _load_env_values() {
        local key val
        while IFS= read -r line || [ -n "$line" ]; do
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// /}" ]] && continue
            key="${line%%=*}"; val="${line#*=}"
            case "$key" in
                WEATHGARDS_HOST) WG_HOST="$val" ;;
                WEATHGARDS_PORT) WG_PORT="$val" ;;
                WEATHGARDS_MCP_TOKEN) WG_TOKEN="$val" ;;
            esac
        done < "$ENV_FILE"
    }
    _load_env_values
    WG_HOST="${WG_HOST:-127.0.0.1}"
    WG_PORT="${WG_PORT:-8765}"
    # "" (vide) se comporte comme 0.0.0.0 dans uvicorn — traiter les deux cas.
    if [ "$WG_HOST" = "0.0.0.0" ] || [ -z "$WG_HOST" ]; then EXPOSE_NETWORK=true; fi
else
    # ── Collecte interactive des valeurs ─────────────────────────────────
    echo ""

    # Charger les valeurs existantes comme défauts si mode "modify"
    declare -A CUR
    if [ "$ENV_ACTION" = "modify" ] && $EXISTING_ENV; then
        while IFS= read -r line || [ -n "$line" ]; do
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// /}" ]] && continue
            key="${line%%=*}"; val="${line#*=}"
            CUR["$key"]="$val"
        done < "${ENV_FILE}.bak"
    fi

    # Retourne la valeur actuelle si la clé existe dans CUR, exit 1 sinon.
    # Sans ce test -v, echo "" sort avec 0 et le fallback "|| echo default"
    # ne se déclenche jamais → les valeurs par défaut sont perdues en mode write.
    get_cur() { [[ -v "CUR[$1]" ]] && echo "${CUR[$1]}" || return 1; }

    # ── WEATHGARDS_HOST ───────────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_HOST${C_RESET}"
    echo "  Adresse IP sur laquelle le cockpit (interface web) écoutera."
    echo "  127.0.0.1 = accessible uniquement en local (recommandé)."
    echo "  0.0.0.0   = accessible depuis n'importe quelle interface réseau."
    ask "WEATHGARDS_HOST" "$(get_cur WEATHGARDS_HOST || echo 127.0.0.1)"
    WG_HOST="$REPLY"
    echo ""

    if [ "$WG_HOST" = "0.0.0.0" ]; then
        EXPOSE_NETWORK=true
        warn "Exposition réseau activée (0.0.0.0)."
        echo "    Le token MCP sera généré automatiquement si vide (obligatoire)."
        echo "    Pensez aussi à renseigner WEATHGARDS_ALLOWED_CLIENTS ci-dessous."
        echo ""
    fi

    # ── WEATHGARDS_PORT ───────────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_PORT${C_RESET}"
    echo "  Port TCP sur lequel le cockpit écoute (8765 par défaut)."
    echo "  Choisissez un port libre entre 1024 et 65535."
    while true; do
        ask "WEATHGARDS_PORT" "$(get_cur WEATHGARDS_PORT || echo 8765)"
        WG_PORT="$REPLY"
        if [[ "$WG_PORT" =~ ^[0-9]+$ ]] && [ "$WG_PORT" -ge 1 ] && [ "$WG_PORT" -le 65535 ]; then
            break
        fi
        warn "Port invalide : saisissez un entier entre 1 et 65535."
    done
    echo ""

    # ── WEATHGARDS_ENV ────────────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_ENV${C_RESET}"
    echo "  Mode d'exécution. 'production' désactive l'endpoint /docs (Swagger)."
    echo "  Utilisez 'development' uniquement si vous développez ou déboguez."
    while true; do
        ask "WEATHGARDS_ENV  [development|production]" "$(get_cur WEATHGARDS_ENV || echo production)"
        WG_ENV="$REPLY"
        case "$WG_ENV" in
            development|production) break ;;
            *) warn "Valeur invalide. Choisissez 'development' ou 'production'." ;;
        esac
    done
    echo ""

    # ── WEATHGARDS_MCP_TOKEN ──────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_MCP_TOKEN${C_RESET}"
    echo "  Token Bearer que le LLM distant doit envoyer dans chaque requête MCP."
    echo "  Format recommandé : wg-<64 caractères hex> (généré automatiquement)."
    echo "  Ne jamais laisser vide ni à 'CHANGE_ME' : le serveur MCP refusera de démarrer"
    echo "  en mode réseau sans token valide."
    echo ""

    EXISTING_TOKEN="$(get_cur WEATHGARDS_MCP_TOKEN)"
    if [ -n "$EXISTING_TOKEN" ] && [ "$EXISTING_TOKEN" != "CHANGE_ME" ]; then
        echo "  Token actuel : $(mask_token "$EXISTING_TOKEN")"
        ask "Nouveau token (Entrée = conserver l'actuel)" ""
    else
        ask "Token MCP (Entrée = générer automatiquement)" ""
    fi

    if [ -z "$REPLY" ]; then
        if [ -n "$EXISTING_TOKEN" ] && [ "$EXISTING_TOKEN" != "CHANGE_ME" ]; then
            WG_TOKEN="$EXISTING_TOKEN"
            info "Token existant conservé."
        else
            WG_TOKEN="$($PYTHON_BIN -c "import secrets; print('wg-' + secrets.token_hex(32))")"
            success "Token généré automatiquement : ${C_CYAN}$(mask_token "$WG_TOKEN")${C_RESET}"
            echo ""
            echo -e "  ${C_YELLOW}${C_BOLD}Important :${C_RESET} notez ce token, vous en aurez besoin pour configurer"
            echo "  votre LLM (Claude Desktop, etc.). Il sera aussi visible dans .env."
        fi
    elif [ "$REPLY" = "CHANGE_ME" ] || [ ${#REPLY} -lt 16 ]; then
        warn "Valeur trop courte ou invalide. Génération automatique."
        WG_TOKEN="$($PYTHON_BIN -c "import secrets; print('wg-' + secrets.token_hex(32))")"
        success "Token généré : $(mask_token "$WG_TOKEN")"
    else
        WG_TOKEN="$REPLY"
    fi
    echo ""

    # ── WEATHGARDS_ALLOWED_CLIENTS ────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_ALLOWED_CLIENTS${C_RESET}"
    echo "  Plages CIDR autorisées à contacter le serveur MCP (ex: 192.168.1.0/24)."
    echo "  Vide = pas de restriction IP (le token reste la seule protection)."
    if $EXPOSE_NETWORK; then
        echo -e "  ${C_YELLOW}Recommandé${C_RESET} : renseignez votre sous-réseau local pour une sécurité accrue."
    fi
    ask "WEATHGARDS_ALLOWED_CLIENTS" "$(get_cur WEATHGARDS_ALLOWED_CLIENTS || echo '')"
    WG_ALLOWED_CLIENTS="$REPLY"
    echo ""

    # ── WEATHGARDS_DOCKER_HOST ────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_DOCKER_HOST${C_RESET}"
    echo "  URI du socket Docker. Vide = détection automatique."
    echo "  Exemples : unix:///var/run/docker.sock  ou  npipe:////./pipe/docker_engine"
    ask "WEATHGARDS_DOCKER_HOST" "$(get_cur WEATHGARDS_DOCKER_HOST || echo '')"
    WG_DOCKER_HOST="$REPLY"
    echo ""

    # ── WEATHGARDS_DOCKER_TIMEOUT ─────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_DOCKER_TIMEOUT${C_RESET}"
    echo "  Timeout (secondes) pour les appels au daemon Docker."
    while true; do
        ask "WEATHGARDS_DOCKER_TIMEOUT" "$(get_cur WEATHGARDS_DOCKER_TIMEOUT || echo 10)"
        WG_DOCKER_TIMEOUT="$REPLY"
        if [[ "$WG_DOCKER_TIMEOUT" =~ ^[0-9]+$ ]] && [ "$WG_DOCKER_TIMEOUT" -ge 1 ]; then
            break
        fi
        warn "Saisissez un entier positif."
    done
    echo ""

    # ── WEATHGARDS_SCAN_INTERVAL ──────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_SCAN_INTERVAL${C_RESET}"
    echo "  Intervalle en secondes entre deux scans automatiques (0 = manuel uniquement)."
    while true; do
        ask "WEATHGARDS_SCAN_INTERVAL" "$(get_cur WEATHGARDS_SCAN_INTERVAL || echo 30)"
        WG_SCAN_INTERVAL="$REPLY"
        if [[ "$WG_SCAN_INTERVAL" =~ ^[0-9]+$ ]]; then
            break
        fi
        warn "Saisissez un entier positif ou 0."
    done
    echo ""

    # ── WEATHGARDS_LOG_LEVEL ──────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_LOG_LEVEL${C_RESET}"
    echo "  Niveau de verbosité des logs."
    echo "  DEBUG = très verbeux (développement), INFO = normal, WARNING/ERROR = silencieux."
    while true; do
        ask "WEATHGARDS_LOG_LEVEL  [DEBUG|INFO|WARNING|ERROR|CRITICAL]" \
            "$(get_cur WEATHGARDS_LOG_LEVEL || echo INFO)"
        WG_LOG_LEVEL="${REPLY^^}"
        case "$WG_LOG_LEVEL" in
            DEBUG|INFO|WARNING|ERROR|CRITICAL) break ;;
            *) warn "Valeur invalide. Choisissez parmi : DEBUG INFO WARNING ERROR CRITICAL" ;;
        esac
    done
    echo ""

    # ── WEATHGARDS_LOG_FORMAT ─────────────────────────────────────────────
    echo -e "  ${C_BOLD}WEATHGARDS_LOG_FORMAT${C_RESET}"
    echo "  Format des logs. 'console' = lisible humainement,"
    echo "  'json' = structuré pour ingestion par ELK, Loki, etc."
    while true; do
        ask "WEATHGARDS_LOG_FORMAT  [console|json]" \
            "$(get_cur WEATHGARDS_LOG_FORMAT || echo console)"
        WG_LOG_FORMAT="$REPLY"
        case "$WG_LOG_FORMAT" in
            console|json) break ;;
            *) warn "Valeur invalide. Choisissez 'console' ou 'json'." ;;
        esac
    done
    echo ""

    # ── Écriture du .env final ────────────────────────────────────────────
    STEP_NAME="3b — Écriture du .env"
    info "Écriture de .env …"

    cat > "$ENV_FILE" << EOF
# WEATHGARDS — Fichier de configuration d'environnement
# Généré par deploy.sh le $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# IMPORTANT : redémarrez WEATHGARDS après toute modification.

# Adresse d'écoute du cockpit (127.0.0.1 = local seulement, 0.0.0.0 = réseau)
WEATHGARDS_HOST=${WG_HOST}

# Port du cockpit
WEATHGARDS_PORT=${WG_PORT}

# Mode d'exécution : development (active /docs) ou production
WEATHGARDS_ENV=${WG_ENV}

# Token Bearer pour le serveur MCP — NE PAS PARTAGER, NE PAS VERSIONNER
WEATHGARDS_MCP_TOKEN=${WG_TOKEN}

# Plages CIDR autorisées (vide = pas de restriction IP, token-only)
WEATHGARDS_ALLOWED_CLIENTS=${WG_ALLOWED_CLIENTS}

# URI du socket Docker (vide = détection automatique par OS)
WEATHGARDS_DOCKER_HOST=${WG_DOCKER_HOST}

# Timeout (secondes) des appels Docker
WEATHGARDS_DOCKER_TIMEOUT=${WG_DOCKER_TIMEOUT}

# Intervalle de scan automatique en secondes (0 = manuel uniquement)
WEATHGARDS_SCAN_INTERVAL=${WG_SCAN_INTERVAL}

# Niveau de log : DEBUG | INFO | WARNING | ERROR | CRITICAL
WEATHGARDS_LOG_LEVEL=${WG_LOG_LEVEL}

# Format des logs : console (humain) | json (ELK/Loki)
WEATHGARDS_LOG_FORMAT=${WG_LOG_FORMAT}
EOF

    success ".env écrit avec succès."
fi

# ===========================================================================
# ÉTAPE 3b — Configuration TLS (optionnel)
# ===========================================================================
STEP_NAME="3b — Configuration TLS"
step_header "ÉTAPE 3b — Chiffrement TLS pour le serveur MCP (optionnel)"
echo ""
echo "  Le serveur MCP (port 9766) peut être sécurisé en HTTPS via un certificat"
echo "  autosigné. Recommandé si vous exposez WEATHGARDS sur le réseau local."
echo "  Le cockpit (port ${WG_PORT}) reste toujours en HTTP (accès local uniquement)."
echo ""

# Lire les chemins TLS actuels depuis .env si disponibles
TLS_CERT_CURRENT=""
TLS_KEY_CURRENT=""
if [ -f "$ENV_FILE" ]; then
    TLS_CERT_CURRENT="$(grep '^WEATHGARDS_TLS_CERT_FILE=' "$ENV_FILE" | cut -d= -f2- || echo '')"
    TLS_KEY_CURRENT="$(grep '^WEATHGARDS_TLS_KEY_FILE=' "$ENV_FILE" | cut -d= -f2- || echo '')"
fi

if [ -n "$TLS_CERT_CURRENT" ] && [ -f "$TLS_CERT_CURRENT" ]; then
    info "Certificat TLS déjà configuré : ${TLS_CERT_CURRENT}"
    if ask_yn "Reconfigurer / régénérer le certificat ?" "n"; then
        TLS_RECONFIGURE=true
    else
        TLS_RECONFIGURE=false
        success "Configuration TLS conservée."
    fi
else
    TLS_RECONFIGURE=true
fi

if $TLS_RECONFIGURE; then
    if ask_yn "Générer un certificat TLS autosigné maintenant ?" "n"; then
        # Vérifier que openssl est disponible
        if ! command -v openssl &>/dev/null; then
            warn "openssl est introuvable. Impossible de générer le certificat."
            echo "  Installez openssl puis relancez deploy.sh, ou générez-le manuellement :"
            echo "    ./scripts/generate-cert.sh <VOTRE_IP_LAN>"
        else
            echo ""
            echo "  Le certificat sera valable pour l'IP et le nom DNS indiqués."
            echo "  Utilisez l'IP de cette machine sur le réseau local (ex: 192.168.1.42)."
            echo "  Entrée vide = 127.0.0.1 (localhost uniquement)."
            echo ""
            # Détecter l'IP LAN pour le proposer comme défaut
            _TLS_LAN_IP=""
            if command -v ip &>/dev/null; then
                _TLS_LAN_IP="$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[\d.]+' | head -1 || echo '')"
            fi
            if [ -z "$_TLS_LAN_IP" ] && command -v ifconfig &>/dev/null; then
                _TLS_LAN_IP="$(ifconfig 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | head -1 | sed 's/addr://' || echo '')"
            fi
            _TLS_DEFAULT="${_TLS_LAN_IP:-127.0.0.1}"

            ask "IP à inclure dans le certificat" "$_TLS_DEFAULT"
            TLS_IP="$REPLY"

            info "Génération du certificat pour IP : ${TLS_IP} …"
            if bash "$SCRIPT_DIR/scripts/generate-cert.sh" "$TLS_IP"; then
                TLS_CERT_PATH="certs/weathgards.crt"
                TLS_KEY_PATH="certs/weathgards.key"
                success "Certificat généré : certs/weathgards.crt  |  certs/weathgards.key"

                # Écrire ou remplacer les vars TLS dans .env
                _set_env_var() {
                    local key="$1" val="$2" file="$3"
                    if grep -q "^${key}=" "$file" 2>/dev/null; then
                        sed -i "s|^${key}=.*|${key}=${val}|" "$file"
                    else
                        printf '\n# Certificat TLS (généré par deploy.sh)\n%s=%s\n' "$key" "$val" >> "$file"
                    fi
                }
                _set_env_var "WEATHGARDS_TLS_CERT_FILE" "$TLS_CERT_PATH" "$ENV_FILE"
                _set_env_var "WEATHGARDS_TLS_KEY_FILE"  "$TLS_KEY_PATH"  "$ENV_FILE"
                success "Variables TLS ajoutées dans .env."

                echo ""
                echo -e "  ${C_BOLD}${C_YELLOW}Important — confiance client :${C_RESET}"
                echo "  Distribuez certs/weathgards.crt à chaque machine cliente et"
                echo "  importez-le dans le trust store OS pour que Claude Desktop"
                echo "  et les autres clients acceptent la connexion HTTPS."
                echo ""
                echo "  Commandes d'import (sur la machine cliente) :"
                echo "    Linux (Debian/Ubuntu) :"
                echo "      sudo cp weathgards.crt /usr/local/share/ca-certificates/"
                echo "      sudo update-ca-certificates"
                echo "    macOS :"
                echo "      sudo security add-trusted-cert -d -r trustRoot \\"
                echo "        -k /Library/Keychains/System.keychain weathgards.crt"
                echo "    Windows (PowerShell, admin) :"
                echo "      Import-Certificate -FilePath .\\weathgards.crt \\"
                echo "        -CertStoreLocation Cert:\\LocalMachine\\Root"
            else
                warn "La génération du certificat a échoué."
                echo "  Vous pouvez relancer manuellement : ./scripts/generate-cert.sh ${TLS_IP:-127.0.0.1}"
            fi
        fi
    else
        info "TLS ignoré. Le serveur MCP démarrera en HTTP."
        info "Pour activer TLS plus tard : ./scripts/generate-cert.sh <IP>"
        info "puis renseignez WEATHGARDS_TLS_CERT_FILE et WEATHGARDS_TLS_KEY_FILE dans .env."
    fi
fi

# ===========================================================================
# ÉTAPE 4 — Build du frontend
# ===========================================================================
STEP_NAME="4 — Build frontend"
step_header "ÉTAPE 4 — Build du frontend React"
echo ""
echo "  Le frontend React (cockpit) doit être compilé en fichiers statiques"
echo "  avant d'être servi par FastAPI. Cette étape est à refaire seulement"
echo "  après une mise à jour du code source frontend."
echo ""

FRONTEND_BUILT=false
if [ -f "frontend/dist/index.html" ]; then
    FRONTEND_BUILT=true
    warn "Un build frontend existe déjà (frontend/dist/index.html)."
    if ask_yn "Réutiliser ce build existant ?" "y"; then
        success "Build frontend réutilisé."
    else
        FRONTEND_BUILT=false
    fi
fi

if ! $FRONTEND_BUILT; then
    if ! $NODE_OK; then
        warn "Node.js absent — build frontend ignoré."
        echo "  Le cockpit sera inaccessible tant que frontend/dist/ n'existe pas."
        echo "  Installez Node.js ≥ 18 et relancez deploy.sh pour corriger cela."
    else
        info "Installation des dépendances npm …"
        (cd frontend && npm install)
        info "Compilation du bundle React/Vite …"
        (cd frontend && npm run build)
        if [ -f "frontend/dist/index.html" ]; then
            success "Frontend compilé : frontend/dist/index.html"
        else
            error "Compilation terminée mais frontend/dist/index.html introuvable."
            echo "  Vérifiez les erreurs npm ci-dessus."
            exit 1
        fi
    fi
fi

# ===========================================================================
# ÉTAPE 5 — Permissions Docker (Linux uniquement)
# ===========================================================================
STEP_NAME="5 — Permissions Docker"

if [ "$OS_TYPE" = "linux" ] && command -v docker &>/dev/null; then
    step_header "ÉTAPE 5 — Permissions Docker (Linux)"
    echo ""
    echo "  Sur Linux, le socket Docker (/var/run/docker.sock) n'est accessible"
    echo "  qu'à root et aux membres du groupe 'docker'. Nous vérifions votre accès."
    echo ""

    DOCKER_ACCESS=false
    if docker info &>/dev/null 2>&1; then
        DOCKER_ACCESS=true
        success "Accès Docker : OK (socket accessible sans sudo)."
    else
        warn "Accès Docker : REFUSÉ pour l'utilisateur courant ($USER)."
        echo ""
        echo "  La solution recommandée est d'ajouter votre utilisateur au groupe docker :"
        echo "    sudo usermod -aG docker $USER"
        echo ""
        echo -e "  Cette commande nécessite un sudo. Elle est ${C_YELLOW}permanente${C_RESET} (solution propre)."
        echo "  Une déconnexion/reconnexion est requise pour que le groupe soit pris en compte."
        echo ""
        echo -e "  ${C_BOLD}IMPORTANT :${C_RESET} ${C_RED}Ne jamais faire chmod 666 /var/run/docker.sock${C_RESET} en production."
        echo "  C'est une faille de sécurité connue (accès root effectif via Docker)."
        echo "  Cela n'est mentionné dans la doc qu'en tant que contournement temporaire."
        echo ""
        if ask_yn "Exécuter : sudo usermod -aG docker $USER ?" "n"; then
            echo ""
            info "Demande du mot de passe sudo …"
            sudo usermod -aG docker "$USER"
            success "Utilisateur $USER ajouté au groupe docker."
            warn "Déconnectez-vous et reconnectez-vous (ou lancez 'newgrp docker')"
            warn "pour que le changement de groupe prenne effet."
        else
            info "Permission Docker non modifiée. Vous pourrez relancer deploy.sh plus tard."
        fi
    fi
else
    STEP_NAME="5 — Permissions Docker"
    if [ "$OS_TYPE" != "linux" ]; then
        info "Étape 5 : non applicable (OS = ${OS_LABEL}). Ignorée."
    fi
fi

# ===========================================================================
# ÉTAPE 6 — Pare-feu (si exposition réseau)
# ===========================================================================
STEP_NAME="6 — Pare-feu"

if $EXPOSE_NETWORK && [ "$OS_TYPE" = "linux" ]; then
    step_header "ÉTAPE 6 — Règle de pare-feu"
    echo ""
    echo "  Vous avez choisi d'exposer WEATHGARDS sur le réseau (HOST=0.0.0.0)."
    echo "  Le serveur MCP écoute sur le port 9766. Sans règle pare-feu,"
    echo "  les connexions réseau seront bloquées sur de nombreuses installations Linux."
    echo ""

    UFW_AVAILABLE=false
    FIREWALLD_AVAILABLE=false
    command -v ufw &>/dev/null && UFW_AVAILABLE=true
    command -v firewall-cmd &>/dev/null && FIREWALLD_AVAILABLE=true

    if $UFW_AVAILABLE; then
        echo -e "  Outil détecté : ${C_BOLD}ufw${C_RESET}"
        echo "  Commande qui sera exécutée : sudo ufw allow 9766/tcp"
        echo ""
        if ask_yn "Ouvrir le port 9766/tcp via ufw ?" "n"; then
            info "Demande du mot de passe sudo …"
            sudo ufw allow 9766/tcp
            success "Règle ufw ajoutée : 9766/tcp autorisé."
        else
            info "Règle pare-feu ignorée. À faire manuellement si besoin :"
            info "  sudo ufw allow 9766/tcp"
        fi
    elif $FIREWALLD_AVAILABLE; then
        echo -e "  Outil détecté : ${C_BOLD}firewalld${C_RESET}"
        echo "  Commandes qui seront exécutées :"
        echo "    sudo firewall-cmd --add-port=9766/tcp --permanent"
        echo "    sudo firewall-cmd --reload"
        echo ""
        if ask_yn "Ouvrir le port 9766/tcp via firewalld ?" "n"; then
            info "Demande du mot de passe sudo …"
            sudo firewall-cmd --add-port=9766/tcp --permanent
            sudo firewall-cmd --reload
            success "Règle firewalld ajoutée : 9766/tcp autorisé (permanent)."
        else
            info "Règle pare-feu ignorée. À faire manuellement si besoin."
        fi
    else
        info "Aucun outil de pare-feu connu détecté (ni ufw ni firewalld)."
        info "Si vous avez iptables ou nftables, ouvrez manuellement le port 9766/tcp."
    fi
elif $EXPOSE_NETWORK && [ "$OS_TYPE" = "macos" ]; then
    step_header "ÉTAPE 6 — Pare-feu macOS"
    echo ""
    echo "  Vous avez choisi l'exposition réseau. Le pare-feu macOS peut bloquer"
    echo "  les connexions entrantes sur le port 9766."
    echo "  Si un LLM distant ne peut pas se connecter, allez dans :"
    echo "  Préférences Système → Sécurité → Pare-feu → Autoriser les connexions"
    echo "  entrantes pour 'weathgards' (ou désactivez temporairement le pare-feu)."
    echo ""
else
    info "Étape 6 : pas d'exposition réseau configurée. Ignorée."
fi

# ===========================================================================
# ÉTAPE 7 — Smoke test (vérification de l'installation)
# ===========================================================================
STEP_NAME="7 — Smoke test"
step_header "ÉTAPE 7 — Vérification de l'installation"
echo ""
echo "  Nous lançons WEATHGARDS en arrière-plan le temps de vérifier que l'API"
echo "  répond correctement sur le port ${WG_PORT}. Le processus sera arrêté proprement"
echo "  à la fin du test."
echo ""

SMOKE_OK=true
TEST_PID=""

# Démarrer WEATHGARDS en arrière-plan
info "Démarrage de WEATHGARDS en arrière-plan …"
WEATHGARDS_HOST="$WG_HOST" WEATHGARDS_PORT="$WG_PORT" \
    uv run weathgards > /tmp/weathgards_smoke.log 2>&1 &
TEST_PID=$!

# Utiliser 127.0.0.1 pour les tests même si le bind est 0.0.0.0
TEST_HOST="127.0.0.1"
HEALTH_URL="http://${TEST_HOST}:${WG_PORT}/api/health"
SCAN_URL="http://${TEST_HOST}:${WG_PORT}/api/scan"

# Attendre que le port réponde (max 30 secondes)
info "Attente de la disponibilité de l'API (max 30 s) …"
WAIT_OK=false
for i in $(seq 1 30); do
    if curl -sf "$HEALTH_URL" -o /dev/null 2>/dev/null; then
        WAIT_OK=true
        break
    fi
    sleep 1
done

if ! $WAIT_OK; then
    SMOKE_OK=false
    warn "L'API n'a pas répondu dans les 30 secondes."
    echo ""
    echo "  Diagnostics possibles :"
    echo "  • Port ${WG_PORT} déjà utilisé :"
    echo "      lsof -i :${WG_PORT}    (Linux/macOS)"
    echo "  • Erreur au démarrage — consultez les logs :"
    echo "      cat /tmp/weathgards_smoke.log"
    echo ""
    echo "  Dernières lignes du log :"
    tail -20 /tmp/weathgards_smoke.log 2>/dev/null || true
else
    # Test /api/health
    HEALTH_RESP="$(curl -sf "$HEALTH_URL" 2>/dev/null || echo '{}')"
    HEALTH_STATUS="$(echo "$HEALTH_RESP" | $PYTHON_BIN -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo '?')"
    HEALTH_OS="$(echo "$HEALTH_RESP" | $PYTHON_BIN -c "import sys,json; d=json.load(sys.stdin); print(d.get('os','?'))" 2>/dev/null || echo '?')"
    HEALTH_DOCKER="$(echo "$HEALTH_RESP" | $PYTHON_BIN -c "import sys,json; d=json.load(sys.stdin); print(d.get('docker_available','?'))" 2>/dev/null || echo '?')"

    if [ "$HEALTH_STATUS" = "ok" ]; then
        success "/api/health : status=${HEALTH_STATUS}  os=${HEALTH_OS}  docker_available=${HEALTH_DOCKER}"
    else
        warn "/api/health : réponse inattendue → ${HEALTH_RESP}"
        SMOKE_OK=false
    fi

    # Test /api/scan
    SCAN_RESP="$(curl -sf "$SCAN_URL" 2>/dev/null || echo 'ERROR')"
    if echo "$SCAN_RESP" | $PYTHON_BIN -c "import sys,json; l=json.load(sys.stdin); assert isinstance(l, list)" 2>/dev/null; then
        SCAN_COUNT="$(echo "$SCAN_RESP" | $PYTHON_BIN -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo '?')"
        success "/api/scan  : OK (${SCAN_COUNT} cibles détectées)"
    else
        warn "/api/scan  : réponse inattendue"
        SMOKE_OK=false
    fi

    # Tests pytest si présents et si pytest est installé (dépendances dev)
    if [ -f "tests/test_smoke.py" ]; then
        if uv run python -c "import pytest" &>/dev/null 2>&1; then
            info "Lancement de uv run pytest tests/test_smoke.py --no-cov -q …"
            if uv run pytest tests/test_smoke.py --no-cov -q 2>&1 | tail -5; then
                success "Tests smoke : PASSED"
            else
                warn "Tests smoke : certains tests ont échoué (voir sortie ci-dessus)"
                SMOKE_OK=false
            fi
        else
            info "pytest absent (deps dev non installées) — tests smoke ignorés."
            info "Pour les activer : uv sync --extra dev"
        fi
    fi
fi

# Arrêt propre du processus de test
if [ -n "$TEST_PID" ]; then
    info "Arrêt du processus de test (PID ${TEST_PID}) …"
    kill "$TEST_PID" 2>/dev/null || true
    # Laisser quelques secondes pour le shutdown graceful
    sleep 2
    kill -0 "$TEST_PID" 2>/dev/null && kill -9 "$TEST_PID" 2>/dev/null || true
fi

if $SMOKE_OK; then
    success "Vérification de l'installation : RÉUSSIE"
else
    warn "Certaines vérifications ont échoué. Consultez les messages ci-dessus."
    echo "  L'installation reste fonctionnelle — les erreurs sont souvent des"
    echo "  avertissements non bloquants (permissions Docker, frontend absent, etc.)."
fi

# ===========================================================================
# ÉTAPE 8 — Service système (optionnel)
# ===========================================================================
STEP_NAME="8 — Service système"
step_header "ÉTAPE 8 — Installation en service système (optionnel)"
echo ""
echo "  Un service système permet à WEATHGARDS de démarrer automatiquement"
echo "  au démarrage de la machine, sans intervention manuelle."
echo ""

if ask_yn "Installer WEATHGARDS comme service système ?" "n"; then
    PROJECT_ABS="$SCRIPT_DIR"
    VENV_BIN="${PROJECT_ABS}/.venv/bin/weathgards"
    ENV_FILE_ABS="${PROJECT_ABS}/.env"

    # Résoudre le vrai interpréteur Python (suit les symlinks du venv → /usr/bin/python3.x).
    # Sur SELinux (Fedora/RHEL), le shebang du script weathgards pointe vers un chemin
    # user_home_t que init_t ne peut pas traverser → 203/EXEC. En invoquant directement
    # le binaire Python système (bin_t) avec PYTHONPATH pointant vers le venv, on contourne
    # le problème : init_t peut exec bin_t, et après la transition SELinux le processus
    # tourne en unconfined_t et accède librement aux fichiers user_home_t.
    REAL_PYTHON="$(readlink -f "${PROJECT_ABS}/.venv/bin/python" 2>/dev/null || command -v python3)"
    VENV_LIB_DIR="$(ls -d "${PROJECT_ABS}/.venv/lib/python"* 2>/dev/null | head -1)"
    VENV_SITE_PACKAGES="${VENV_LIB_DIR}/site-packages"
    # src/ doit précéder site-packages : le stub d'install éditable dans site-packages
    # est un répertoire weathgards/ sans __main__.py. En mettant src/ en premier,
    # Python trouve src/weathgards/ (avec __main__.py) avant le stub.
    VENV_PYTHONPATH="${PROJECT_ABS}/src:${VENV_SITE_PACKAGES}"

    # Demander le nom d'utilisateur pour le service
    ask "Utilisateur pour le service" "$USER"
    SERVICE_USER="$REPLY"

    if [ "$OS_TYPE" = "linux" ]; then
        # ── systemd ──────────────────────────────────────────────────────
        SERVICE_FILE="/etc/systemd/system/weathgards.service"
        echo ""
        echo "  Fichier de service qui sera créé : ${SERVICE_FILE}"
        echo "  Contenu :"
        echo "  ─────────────────────────────────────────────────────────"
        cat << SERVICE_CONTENT
  [Unit]
  Description=WEATHGARDS MCP Gateway
  After=network.target docker.service

  [Service]
  Type=simple
  User=${SERVICE_USER}
  WorkingDirectory=${PROJECT_ABS}
  EnvironmentFile=${ENV_FILE_ABS}
  Environment=PYTHONPATH=${VENV_PYTHONPATH}
  ExecStart=${REAL_PYTHON} -m weathgards
  Restart=on-failure
  RestartSec=5s

  [Install]
  WantedBy=multi-user.target
SERVICE_CONTENT
        echo "  ─────────────────────────────────────────────────────────"
        echo ""
        if ask_yn "Créer ce fichier et activer le service maintenant ?" "n"; then
            info "Demande du mot de passe sudo …"
            sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=WEATHGARDS MCP Gateway
After=network.target docker.service

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${PROJECT_ABS}
EnvironmentFile=${ENV_FILE_ABS}
Environment=PYTHONPATH=${VENV_SITE_PACKAGES}
ExecStart=${REAL_PYTHON} -m weathgards
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF
            # Sur Fedora/RHEL, SELinux interdit à systemd de lire un EnvironmentFile
            # étiqueté user_home_t. chcon -t etc_t lui donne le contexte de fichier de
            # configuration attendu. Le binaire Python (/usr/bin/python3.x) est bin_t
            # nativement — aucun chcon supplémentaire n'est nécessaire pour ExecStart.
            if command -v getenforce &>/dev/null && [ "$(getenforce 2>/dev/null)" = "Enforcing" ]; then
                if sudo chcon -t etc_t "$ENV_FILE_ABS" 2>/dev/null; then
                    info "Contexte SELinux de .env ajusté (etc_t) pour systemd."
                else
                    warn "Impossible d'ajuster le contexte SELinux de .env."
                    warn "Si le service ne démarre pas, exécutez :"
                    warn "  sudo chcon -t etc_t ${ENV_FILE_ABS}"
                fi
            fi

            sudo systemctl daemon-reload
            sudo systemctl enable weathgards
            SERVICE_INSTALLED=true
            if sudo systemctl start weathgards; then
                success "Service systemd weathgards activé et démarré."
            else
                warn "Service activé mais démarrage échoué."
                warn "Diagnostiquez avec : sudo systemctl status weathgards"
                warn "              ou  : journalctl -xeu weathgards.service"
            fi
            info "Statut : sudo systemctl status weathgards"
        else
            info "Service non installé. Pour le faire manuellement plus tard :"
            info "  Créez ${SERVICE_FILE} avec le contenu affiché ci-dessus"
            info "  puis : sudo systemctl daemon-reload && sudo systemctl enable --now weathgards"
        fi

    elif [ "$OS_TYPE" = "macos" ]; then
        # ── launchd ──────────────────────────────────────────────────────
        PLIST_FILE="$HOME/Library/LaunchAgents/com.weathgards.plist"
        mkdir -p "$HOME/Library/LaunchAgents"
        echo ""
        echo "  Fichier plist qui sera créé : ${PLIST_FILE}"
        echo "  ─────────────────────────────────────────────────────────"

        # Lire le token depuis .env pour l'injecter dans le plist
        PLIST_TOKEN="$(grep '^WEATHGARDS_MCP_TOKEN=' "$ENV_FILE_ABS" | cut -d= -f2- || echo '')"

        cat << PLIST_PREVIEW
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
    <key>Label</key>            <string>com.weathgards</string>
    <key>ProgramArguments</key>
    <array>
      <string>${VENV_BIN}</string>
    </array>
    <key>WorkingDirectory</key> <string>${PROJECT_ABS}</string>
    <key>EnvironmentVariables</key>
    <dict>
      <key>WEATHGARDS_MCP_TOKEN</key>
      <string>$(mask_token "$PLIST_TOKEN")</string>
    </dict>
    <key>RunAtLoad</key>  <true/>
    <key>KeepAlive</key>  <true/>
  </dict>
  </plist>
PLIST_PREVIEW
        echo "  ─────────────────────────────────────────────────────────"
        echo ""
        if ask_yn "Créer ce plist et charger le service launchd maintenant ?" "n"; then
            cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>            <string>com.weathgards</string>
  <key>ProgramArguments</key>
  <array>
    <string>${VENV_BIN}</string>
  </array>
  <key>WorkingDirectory</key> <string>${PROJECT_ABS}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>WEATHGARDS_MCP_TOKEN</key>
    <string>${PLIST_TOKEN}</string>
  </dict>
  <key>RunAtLoad</key>  <true/>
  <key>KeepAlive</key>  <true/>
</dict>
</plist>
EOF
            launchctl load "$PLIST_FILE"
            SERVICE_INSTALLED=true
            success "Service launchd com.weathgards chargé."
            info "Pour vérifier : launchctl list | grep weathgards"
        else
            info "Service non installé. Pour le faire manuellement plus tard :"
            info "  Créez ${PLIST_FILE} avec le contenu affiché ci-dessus"
            info "  puis : launchctl load ${PLIST_FILE}"
        fi

    else
        info "Installation de service non supportée sous ${OS_LABEL} via ce script."
        info "Consultez DOCUMENTATION.md section 4.1 pour la procédure Windows."
    fi
else
    info "Service système ignoré. Démarrez WEATHGARDS manuellement : uv run weathgards"
fi

# ===========================================================================
# ÉTAPE 9 — Récapitulatif final
# ===========================================================================
STEP_NAME="9 — Récapitulatif final"
step_header "ÉTAPE 9 — Récapitulatif final"

# Déterminer l'IP LAN pour le bloc de config Claude Desktop
LAN_IP=""
if $EXPOSE_NETWORK; then
    # Tente de détecter l'IP LAN de façon portable (Linux + macOS)
    if command -v ip &>/dev/null; then
        LAN_IP="$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[\d.]+' | head -1 || echo '')"
    fi
    if [ -z "$LAN_IP" ] && command -v ifconfig &>/dev/null; then
        LAN_IP="$(ifconfig 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | head -1 | sed 's/addr://' || echo '')"
    fi
    if [ -z "$LAN_IP" ]; then
        LAN_IP="<VOTRE_IP_LAN>"
    fi
    MCP_HOST_DISPLAY="$LAN_IP"
else
    MCP_HOST_DISPLAY="127.0.0.1"
fi

MCP_URL="http://${MCP_HOST_DISPLAY}:9766/mcp"
COCKPIT_URL="http://${WG_HOST}:${WG_PORT}"

echo ""
echo -e "${C_BOLD}${C_GREEN}"
echo "  ╔═══════════════════════════════════════════════════════════════╗"
echo "  ║               WEATHGARDS est prêt !                          ║"
echo "  ╚═══════════════════════════════════════════════════════════════╝"
echo -e "${C_RESET}"

echo "  ┌─────────────────────────────────────────────────────────────┐"
printf "  │  %-20s  %-39s│\n" "Interface cockpit" "$COCKPIT_URL"
printf "  │  %-20s  %-39s│\n" "Token MCP" "$(mask_token "$WG_TOKEN")  (→ .env)"
printf "  │  %-20s  %-39s│\n" "Répertoire config" "${CONFIG_DIR:0:50}"
printf "  │  %-20s  %-39s│\n" "Docker" "$( $DOCKER_AVAILABLE && echo "disponible" || echo "non disponible")"
printf "  │  %-20s  %-39s│\n" "Service système" "$( $SERVICE_INSTALLED && echo "installé et actif" || echo "non installé")"
echo "  └─────────────────────────────────────────────────────────────┘"

echo ""
echo -e "  ${C_BOLD}${C_CYAN}Bloc de configuration Claude Desktop${C_RESET}"
echo "  Copiez ce bloc dans votre fichier claude_desktop_config.json :"
echo ""
echo -e "  ${C_DIM}┌─────────────────────────────────────────────────────────────┐${C_RESET}"
cat << CLAUDE_BLOCK
  {
    "mcpServers": {
      "weathgards": {
        "url": "${MCP_URL}",
        "headers": {
          "Authorization": "Bearer ${WG_TOKEN}"
        }
      }
    }
  }
CLAUDE_BLOCK
echo -e "  ${C_DIM}└─────────────────────────────────────────────────────────────┘${C_RESET}"

echo ""
echo -e "  ${C_BOLD}Emplacement du fichier claude_desktop_config.json${C_RESET}"
echo "    macOS   : ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "    Windows : %APPDATA%\\Claude\\claude_desktop_config.json"
echo "    Linux   : ~/.config/Claude/claude_desktop_config.json"

if $EXPOSE_NETWORK && [ "$MCP_HOST_DISPLAY" = "<VOTRE_IP_LAN>" ]; then
    echo ""
    warn "L'IP LAN n'a pas pu être détectée automatiquement."
    echo "    Remplacez <VOTRE_IP_LAN> par votre adresse IP locale."
    echo "    Commande pour la trouver : ip a  (Linux) | ifconfig (macOS)"
fi

echo ""
echo -e "  ${C_BOLD}Commande de démarrage${C_RESET}"
echo -e "  ${C_CYAN}  uv run weathgards${C_RESET}"

if $SERVICE_INSTALLED; then
    echo ""
    if [ "$OS_TYPE" = "linux" ]; then
        info "Le service systemd démarre automatiquement au boot."
        info "  sudo systemctl status weathgards"
        info "  sudo systemctl stop weathgards"
    elif [ "$OS_TYPE" = "macos" ]; then
        info "Le service launchd démarre automatiquement à la connexion."
        info "  launchctl list | grep weathgards"
        info "  launchctl unload ~/Library/LaunchAgents/com.weathgards.plist"
    fi
fi

echo ""
echo -e "  ${C_DIM}Token complet disponible dans : ${ENV_FILE_ABS}${C_RESET}"
echo -e "  ${C_DIM}Documentation complète       : ${SCRIPT_DIR}/DOCUMENTATION.md${C_RESET}"
echo ""
echo -e "${C_GREEN}${C_BOLD}  Installation terminée.${C_RESET}"
echo ""
