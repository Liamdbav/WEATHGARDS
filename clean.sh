#!/usr/bin/env bash
# clean.sh — supprime les résidus d'une installation/utilisation de WEATHGARDS
#
# Ce script n'efface JAMAIS les fichiers sources du projet.
# Il cible uniquement les artefacts générés à l'installation ou à l'exécution :
#   • environnement Python (.venv)
#   • build frontend (frontend/dist, frontend/node_modules)
#   • configuration (.env, .env.bak)
#   • certificats TLS (certs/*.crt, certs/*.key)
#   • données runtime (config_dir : mcp.token, settings.json)
#   • caches Python (__pycache__, .pytest_cache, .ruff_cache, .mypy_cache)
#   • logs temporaires (/tmp/weathgards_*.log)
#   • service système (systemd / launchd) — optionnel, demande sudo
#
# Usage : ./clean.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Couleurs ANSI — désactivées si la sortie n'est pas un TTY
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    C_RESET="\033[0m"  C_BOLD="\033[1m"   C_DIM="\033[2m"
    C_CYAN="\033[36m"  C_GREEN="\033[32m" C_YELLOW="\033[33m"
    C_RED="\033[31m"   C_MAGENTA="\033[35m"
else
    C_RESET="" C_BOLD="" C_DIM="" C_CYAN="" C_GREEN="" C_YELLOW="" C_RED="" C_MAGENTA=""
fi

# ---------------------------------------------------------------------------
# Helpers d'affichage
# ---------------------------------------------------------------------------
step_header() { echo ""; echo -e "${C_CYAN}${C_BOLD}━━━  $1  ━━━${C_RESET}"; }
info()    { echo -e "  ${C_DIM}→${C_RESET} $*"; }
success() { echo -e "  ${C_GREEN}✓${C_RESET} $*"; }
warn()    { echo -e "  ${C_YELLOW}⚠${C_RESET} $*"; }
skip()    { echo -e "  ${C_DIM}–${C_RESET} $*"; }

ask_yn() {
    local prompt="$1" default="${2:-n}"
    local choices; [ "$default" = "y" ] && choices="[O/n]" || choices="[o/N]"
    echo -en "  ${C_BOLD}$prompt${C_RESET} $choices : "
    read -r REPLY
    REPLY="${REPLY:-$default}"
    case "${REPLY,,}" in o|y|oui|yes) return 0 ;; *) return 1 ;; esac
}

# Affiche la taille d'un répertoire ou fichier s'il existe, sinon "(absent)"
_size() {
    local target="$1"
    if [ -e "$target" ]; then
        du -sh "$target" 2>/dev/null | cut -f1
    else
        echo "(absent)"
    fi
}

# Supprime un chemin en loggant le résultat. $1 = chemin, $2 = label
_remove() {
    local target="$1" label="$2"
    if [ -e "$target" ]; then
        rm -rf "$target"
        success "${label} supprimé."
    else
        skip "${label} — déjà absent."
    fi
}

# ---------------------------------------------------------------------------
# Se placer à la racine du projet (là où se trouve ce script)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Compteurs pour le récapitulatif
# ---------------------------------------------------------------------------
CLEANED=0     # catégories nettoyées
SKIPPED=0     # catégories ignorées par l'utilisateur
ALREADY=0     # catégories déjà absentes

# ===========================================================================
# Bannière
# ===========================================================================
clear 2>/dev/null || true

echo -e "${C_CYAN}${C_BOLD}"
cat << 'BANNER'
  ╔═══════════════════════════════════════════════════════╗
  ║                                                       ║
  ║   WEATHGARDS — Nettoyage de l'installation            ║
  ║                                                       ║
  ║   Les fichiers sources du projet ne sont jamais       ║
  ║   supprimés. Seuls les artefacts générés le sont.     ║
  ║                                                       ║
  ╚═══════════════════════════════════════════════════════╝
BANNER
echo -e "${C_RESET}"

# ===========================================================================
# Détection de l'OS (même logique que deploy.sh)
# ===========================================================================
RAW_OS="$(uname -s 2>/dev/null || echo "Unknown")"
case "$RAW_OS" in
    Linux*)
        OS_TYPE="linux"
        CONFIG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/weathgards"
        SERVICE_FILE="/etc/systemd/system/weathgards.service"
        ;;
    Darwin*)
        OS_TYPE="macos"
        CONFIG_DIR="$HOME/Library/Application Support/weathgards"
        PLIST_FILE="$HOME/Library/LaunchAgents/com.weathgards.plist"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OS_TYPE="windows"
        CONFIG_DIR="${LOCALAPPDATA:-$HOME/AppData/Local}/weathgards/weathgards"
        ;;
    *)
        OS_TYPE="unknown"
        CONFIG_DIR="$HOME/.local/share/weathgards"
        ;;
esac

# ===========================================================================
# Inventaire — ce qui est présent sur le disque
# ===========================================================================
step_header "Inventaire des artefacts détectés"
echo ""
printf "  %-40s %s\n" "Artefact" "Taille / État"
echo "  ──────────────────────────────────────────────────────────"
printf "  %-40s %s\n" "Environnement Python  (.venv/)"          "$(_size .venv)"
printf "  %-40s %s\n" "Build frontend        (frontend/dist/)"  "$(_size frontend/dist)"
printf "  %-40s %s\n" "Dépendances npm       (node_modules/)"   "$(_size frontend/node_modules)"
printf "  %-40s %s\n" "Configuration         (.env)"            "$(_size .env)"
printf "  %-40s %s\n" "Configuration sauveg. (.env.bak)"        "$(_size .env.bak)"
printf "  %-40s %s\n" "Certificats TLS       (certs/)"          \
    "$(ls certs/*.crt certs/*.key 2>/dev/null | wc -l | tr -d ' ') fichier(s)"
printf "  %-40s %s\n" "Données runtime       (config_dir)"      "$(_size "$CONFIG_DIR")"
printf "  %-40s %s\n" "Caches Python"                           \
    "$(find . -not -path './.venv/*' -not -path './frontend/node_modules/*' \
        \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o -name '.mypy_cache' \) \
        2>/dev/null | wc -l | tr -d ' ') répertoire(s)"
printf "  %-40s %s\n" "Logs temporaires      (/tmp/weathgards*)" \
    "$(ls /tmp/weathgards_*.log 2>/dev/null | wc -l | tr -d ' ') fichier(s)"

if [ "$OS_TYPE" = "linux" ]; then
    printf "  %-40s %s\n" "Service systemd" \
        "$([ -f "$SERVICE_FILE" ] && echo 'présent' || echo 'absent')"
elif [ "$OS_TYPE" = "macos" ]; then
    printf "  %-40s %s\n" "Service launchd" \
        "$([ -f "$PLIST_FILE" ] && echo 'présent' || echo 'absent')"
fi
echo ""

# ===========================================================================
# Sélection du mode
# ===========================================================================
echo -e "  ${C_BOLD}Mode de nettoyage :${C_RESET}"
echo "    [T] Tout nettoyer d'un coup (recommandé pour une réinstallation propre)"
echo "    [S] Sélectif — choisir catégorie par catégorie"
echo ""
echo -en "  ${C_BOLD}Votre choix${C_RESET} ${C_DIM}[T/s]${C_RESET} : "
read -r MODE_REPLY
MODE_REPLY="${MODE_REPLY:-t}"

case "${MODE_REPLY,,}" in
    s|selectif|sélectif) MODE="selective" ;;
    *)                   MODE="all" ;;
esac

if [ "$MODE" = "all" ]; then
    echo ""
    warn "Tout nettoyer supprimera les artefacts listés ci-dessus."
    warn "Les fichiers sources du projet (.py, .tsx, pyproject.toml, etc.) ne sont JAMAIS touchés."
    echo ""
    if ! ask_yn "Confirmer le nettoyage complet ?" "n"; then
        echo ""
        info "Nettoyage annulé."
        exit 0
    fi
fi

# Fonction de décision : en mode "all" on nettoie sans redemander,
# en mode "selective" on pose la question pour chaque catégorie.
_should_clean() {
    local label="$1"
    if [ "$MODE" = "all" ]; then
        return 0
    else
        echo ""
        ask_yn "Nettoyer : ${label} ?" "n"
        return $?
    fi
}

# ===========================================================================
# 1 — Environnement Python (.venv)
# ===========================================================================
step_header "1 — Environnement Python"

if _should_clean ".venv/ ($(  _size .venv))"; then
    _remove ".venv" "Environnement Python .venv"
    ((CLEANED++)) || true
else
    skip ".venv conservé."
    ((SKIPPED++)) || true
fi

# ===========================================================================
# 2 — Build frontend et dépendances npm
# ===========================================================================
step_header "2 — Build frontend et dépendances npm"

_fe_present=false
[ -d "frontend/dist" ] && _fe_present=true
[ -d "frontend/node_modules" ] && _fe_present=true

if $_fe_present; then
    if _should_clean "frontend/dist/ + frontend/node_modules/"; then
        _remove "frontend/dist"         "frontend/dist"
        _remove "frontend/node_modules" "frontend/node_modules"
        ((CLEANED++)) || true
    else
        skip "Build frontend conservé."
        ((SKIPPED++)) || true
    fi
else
    skip "Aucun build frontend ni node_modules présent."
    ((ALREADY++)) || true
fi

# ===========================================================================
# 3 — Fichiers de configuration (.env, .env.bak)
# ===========================================================================
step_header "3 — Configuration (.env)"

_env_present=false
[ -f ".env" ] && _env_present=true
[ -f ".env.bak" ] && _env_present=true

if $_env_present; then
    if _should_clean ".env et .env.bak (token MCP inclus)"; then
        _remove ".env"     ".env"
        _remove ".env.bak" ".env.bak"
        ((CLEANED++)) || true
    else
        skip ".env conservé."
        ((SKIPPED++)) || true
    fi
else
    skip "Aucun fichier .env présent."
    ((ALREADY++)) || true
fi

# ===========================================================================
# 4 — Certificats TLS (certs/*.crt, certs/*.key)
# ===========================================================================
step_header "4 — Certificats TLS"

_cert_files=()
while IFS= read -r -d '' f; do
    _cert_files+=("$f")
done < <(find certs \( -name '*.crt' -o -name '*.key' \) -print0 2>/dev/null)

if [ ${#_cert_files[@]} -gt 0 ]; then
    if _should_clean "certificats TLS (${#_cert_files[@]} fichier(s) dans certs/)"; then
        for f in "${_cert_files[@]}"; do
            rm -f "$f"
            success "Supprimé : $f"
        done
        ((CLEANED++)) || true
        # .gitkeep est intentionnellement conservé
    else
        skip "Certificats conservés."
        ((SKIPPED++)) || true
    fi
else
    skip "Aucun certificat TLS présent."
    ((ALREADY++)) || true
fi

# ===========================================================================
# 5 — Données runtime (config_dir : mcp.token, settings.json)
# ===========================================================================
step_header "5 — Données runtime (config_dir)"

if [ -d "$CONFIG_DIR" ]; then
    _runtime_files=()
    for f in "$CONFIG_DIR/mcp.token" "$CONFIG_DIR/settings.json"; do
        [ -f "$f" ] && _runtime_files+=("$f")
    done

    if [ ${#_runtime_files[@]} -gt 0 ]; then
        if _should_clean "données runtime dans $CONFIG_DIR"; then
            for f in "${_runtime_files[@]}"; do
                rm -f "$f"
                success "Supprimé : $f"
            done
            # Supprimer le répertoire s'il est vide (hors fichiers cachés)
            if [ -z "$(ls -A "$CONFIG_DIR" 2>/dev/null)" ]; then
                rmdir "$CONFIG_DIR" 2>/dev/null && info "Répertoire $CONFIG_DIR supprimé (vide)."
            fi
            ((CLEANED++)) || true
        else
            skip "Données runtime conservées."
            ((SKIPPED++)) || true
        fi
    else
        skip "config_dir présent mais vide."
        ((ALREADY++)) || true
    fi
else
    skip "config_dir absent ($CONFIG_DIR)."
    ((ALREADY++)) || true
fi

# ===========================================================================
# 6 — Caches Python (__pycache__, .pytest_cache, .ruff_cache, .mypy_cache)
# ===========================================================================
step_header "6 — Caches Python"

_cache_dirs=()
while IFS= read -r -d '' d; do
    _cache_dirs+=("$d")
done < <(find . \
    -not -path './.venv/*' \
    -not -path './frontend/node_modules/*' \
    \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o -name '.mypy_cache' \) \
    -print0 2>/dev/null)

if [ ${#_cache_dirs[@]} -gt 0 ]; then
    if _should_clean "caches Python (${#_cache_dirs[@]} répertoire(s))"; then
        for d in "${_cache_dirs[@]}"; do
            rm -rf "$d"
        done
        success "${#_cache_dirs[@]} répertoire(s) de cache supprimé(s)."
        ((CLEANED++)) || true
    else
        skip "Caches Python conservés."
        ((SKIPPED++)) || true
    fi
else
    skip "Aucun cache Python présent."
    ((ALREADY++)) || true
fi

# ===========================================================================
# 7 — Logs temporaires (/tmp/weathgards_*.log)
# ===========================================================================
step_header "7 — Logs temporaires"

_tmp_logs=()
for f in /tmp/weathgards_*.log; do
    [ -f "$f" ] && _tmp_logs+=("$f")
done

if [ ${#_tmp_logs[@]} -gt 0 ]; then
    if _should_clean "logs temporaires (${#_tmp_logs[@]} fichier(s) dans /tmp/)"; then
        for f in "${_tmp_logs[@]}"; do
            rm -f "$f"
            success "Supprimé : $f"
        done
        ((CLEANED++)) || true
    else
        skip "Logs temporaires conservés."
        ((SKIPPED++)) || true
    fi
else
    skip "Aucun log temporaire présent."
    ((ALREADY++)) || true
fi

# ===========================================================================
# 8 — Service système (optionnel, sudo requis)
# ===========================================================================
step_header "8 — Service système"

_service_present=false
_service_label=""

if [ "$OS_TYPE" = "linux" ] && [ -f "$SERVICE_FILE" ]; then
    _service_present=true
    _service_label="systemd : $SERVICE_FILE"
elif [ "$OS_TYPE" = "macos" ] && [ -f "${PLIST_FILE:-}" ]; then
    _service_present=true
    _service_label="launchd : $PLIST_FILE"
fi

if $_service_present; then
    echo ""
    warn "Un service système est installé : ${_service_label}"
    echo ""
    if _should_clean "service système (nécessite sudo ou launchctl)"; then
        if [ "$OS_TYPE" = "linux" ]; then
            # Arrêter et désactiver le service avant de supprimer le fichier
            if systemctl is-active --quiet weathgards 2>/dev/null; then
                info "Arrêt du service weathgards …"
                sudo systemctl stop weathgards
            fi
            if systemctl is-enabled --quiet weathgards 2>/dev/null; then
                sudo systemctl disable weathgards
            fi
            sudo rm -f "$SERVICE_FILE"
            sudo systemctl daemon-reload
            success "Service systemd weathgards supprimé."
        elif [ "$OS_TYPE" = "macos" ]; then
            if launchctl list 2>/dev/null | grep -q "com.weathgards"; then
                launchctl unload "$PLIST_FILE" 2>/dev/null || true
                info "Service launchd déchargé."
            fi
            rm -f "$PLIST_FILE"
            success "Plist launchd supprimé : $PLIST_FILE"
        fi
        ((CLEANED++)) || true
    else
        skip "Service système conservé."
        ((SKIPPED++)) || true
    fi
else
    skip "Aucun service système installé."
    ((ALREADY++)) || true
fi

# ===========================================================================
# Récapitulatif final
# ===========================================================================
step_header "Récapitulatif"
echo ""
echo -e "  ${C_BOLD}Résultat du nettoyage :${C_RESET}"
echo "  ┌──────────────────────────────────────────────────┐"
printf "  │  %-20s  %-27s│\n" "Nettoyées"   "${CLEANED} catégorie(s)"
printf "  │  %-20s  %-27s│\n" "Ignorées"    "${SKIPPED} catégorie(s)"
printf "  │  %-20s  %-27s│\n" "Déjà absentes" "${ALREADY} catégorie(s)"
echo "  └──────────────────────────────────────────────────┘"
echo ""

if [ "$CLEANED" -gt 0 ]; then
    echo -e "  ${C_GREEN}${C_BOLD}Nettoyage terminé.${C_RESET}"
    echo ""
    echo "  Pour réinstaller proprement :"
    echo -e "  ${C_CYAN}  ./deploy.sh${C_RESET}"
else
    echo -e "  ${C_DIM}Rien n'a été supprimé.${C_RESET}"
fi
echo ""
