#!/usr/bin/env bash
#
# activate-cli.sh - Expose les commandes publiques de l'ecosysteme morfSystem
# dans ~/.local/bin, sans jamais deplacer les scripts hors de leur projet.
#
# ---------------------------------------------------------------------------
# CE QUE FAIT CE SCRIPT (et surtout ce qu'il ne fait PAS)
# ---------------------------------------------------------------------------
# morfSystem est un ensemble de projets FRERES poses cote a cote dans une meme
# racine de travail. Selon la machine, cette racine peut s'appeler autrement :
#
#     /home/user/01-Travail/          ou      /home/user/morfSystem/
#     |-- morfTools/                          |-- morfTools/
#     |-- morfDashboard/                      |-- morfDashboard/
#     `-- ...                                 `-- ...
#
# Certains projets fournissent de vraies commandes utilisateur (morf, screenctl).
# On veut pouvoir les appeler depuis n'importe ou, sans se deplacer dans leur
# dossier. Ce script cree pour cela des entrees dans ~/.local/bin :
#
#   - mode "direct"  : un LIEN SYMBOLIQUE vers le script d'origine. Reserve aux
#                      scripts dont le comportement NE depend PAS du repertoire
#                      courant (ils trouvent leurs ressources via leur propre
#                      emplacement, p. ex. __file__ en Python).
#   - mode "project" : un petit LANCEUR qui entre dans le projet avant d'executer
#                      le script. Pour les scripts qui ont besoin d'etre lances
#                      depuis leur propre dossier (assets, chemins relatifs...).
#
# Le mode est TOUJOURS declare explicitement par le projet (voir cli.manifest) :
# ce script ne le devine jamais en analysant le code.
#
# ACTIVATION VOLONTAIRE. Ce script ne fait PAS partie de l'installation du parc.
# Il n'est jamais appele par `morf install` / `morf update`. Il ne touche a aucun
# service, a aucun fichier sous /opt, /etc ou /var/lib, ne compile rien, ne
# deploie rien. Il ne modifie QUE ~/.local/bin (l'environnement de l'utilisateur).
#
# COHERENCE D'ESPACE. Une activation designe UN espace de travail : la racine
# est le dossier PARENT de cette copie de morfTools. Toutes les commandes
# exposees proviennent alors de cette meme racine -- jamais un melange de deux
# espaces. Pour basculer, l'utilisateur relance ce script depuis l'autre copie.
#
# Usage :
#     ./activate-cli.sh            active l'espace de CETTE copie de morfTools
#     ./activate-cli.sh --dry-run  montre ce qui changerait, sans rien modifier
#     ./activate-cli.sh --status   etat courant (espace actif, commandes gerees)
#     ./activate-cli.sh --deactivate  retire toutes les commandes gerees
#     ./activate-cli.sh --help
#
# Variables d'environnement (surtout pour les tests) :
#     MORF_CLI_BIN   dossier cible au lieu de ~/.local/bin
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Reperage : racine de travail et dossier des commandes
# ---------------------------------------------------------------------------
# On resout le chemin reel de CE script (en suivant un eventuel lien), puis la
# racine de travail est le parent de morfTools. Aucun chemin n'est code en dur :
# la meme copie dans 01-Travail ou dans morfSystem donne la bonne racine.
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [ "${SOURCE:0:1}" = "/" ] || SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"   # dossier morfTools
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"             # racine de l'espace de travail

# Dossier ou publier les commandes. Surchageable pour les tests.
BIN_DIR="${MORF_CLI_BIN:-$HOME/.local/bin}"

# Registre des commandes que NOUS avons creees : il permet, a la prochaine
# activation, de savoir quelles entrees peuvent legitimement etre remplacees ou
# retirees (notamment en changeant d'espace), sans jamais toucher a un fichier
# etranger. C'est un fichier cache a cote des commandes.
REGISTRY="$BIN_DIR/.morfsystem-cli"

# Marqueur inscrit dans les lanceurs "project", pour les reconnaitre a coup sur.
WRAPPER_MARK="morfsystem-cli-wrapper/1"

# Nom du fichier de declaration cherche a la racine de chaque projet.
MANIFEST_NAME="cli.manifest"

# ---------------------------------------------------------------------------
# Sortie : couleurs si le terminal les accepte, sinon texte nu
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_OFF=""
fi
info()  { printf '%s\n' "$*"; }
ok()    { printf '  %sOK%s   %s\n'   "$C_OK"   "$C_OFF" "$*"; }
warn()  { printf '  %s!!%s   %s\n'   "$C_WARN" "$C_OFF" "$*" >&2; }
err()   { printf '  %sX%s    %s\n'   "$C_ERR"  "$C_OFF" "$*" >&2; }
dim()   { printf '       %s%s%s\n'   "$C_DIM"  "$*" "$C_OFF"; }

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
DRY_RUN=0
ACTION="activate"
while [ $# -gt 0 ]; do
  case "$1" in
    -n|--dry-run) DRY_RUN=1 ;;
    --status)     ACTION="status" ;;
    --deactivate) ACTION="deactivate" ;;
    -h|--help)
      sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      err "option inconnue : $1"
      info "Essayer : $0 --help"
      exit 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Aides bas niveau
# ---------------------------------------------------------------------------

# Retire un eventuel retour chariot Windows en fin de champ (fichiers CRLF).
strip_cr() { printf '%s' "${1%$'\r'}"; }

# Un fichier de ~/.local/bin est-il un LANCEUR que nous avons genere ?
# On le reconnait a son marqueur ; aucune heuristique sur le nom.
is_our_wrapper() {
  local f="$1"
  [ -f "$f" ] && grep -q "$WRAPPER_MARK" "$f" 2>/dev/null
}

# Un fichier est-il un LIEN que nous gerons pour cette commande ?
# Vrai si c'est un lien symbolique dont la cible se termine par "/<projet>/<script>"
# de la commande consideree : cela couvre le cas du changement d'espace (l'ancien
# lien pointait vers l'autre racine, meme projet/scripts), sans jamais confondre
# avec un lien etranger vers un tout autre programme.
is_our_symlink_for() {
  local f="$1" tail="$2"     # tail = "morfDashboard/screenctl.py"
  [ -L "$f" ] || return 1
  local target; target="$(readlink "$f" 2>/dev/null || true)"
  case "$target" in
    */"$tail") return 0 ;;
    *)         return 1 ;;
  esac
}

# Une entree de ~/.local/bin est-elle geree par morfSystem (donc remplacable) ?
# Vrai si le registre la connait, si c'est un de nos lanceurs, ou un lien vers le
# meme projet/scripts. Faux pour tout fichier etranger : on n'y touchera pas.
is_managed() {
  local f="$1" cmd="$2" tail="$3"
  is_our_wrapper "$f" && return 0
  is_our_symlink_for "$f" "$tail" && return 0
  # Dernier recours : le registre atteste que nous l'avons cree.
  [ -f "$REGISTRY" ] && grep -q "^${cmd}"$'\t' "$REGISTRY" && [ -L "$f" ] && return 0
  return 1
}

# ---------------------------------------------------------------------------
# Lecture des declarations : un cli.manifest par projet
# ---------------------------------------------------------------------------
# Chaque projet proprietaire declare SES commandes dans <projet>/cli.manifest.
# Format, une commande par ligne (colonnes separees par des espaces) :
#
#     # commentaire (ignore)
#     <nom-public>   <mode>   <script-relatif-au-projet>
#     morf           direct   morf.py
#     build-dashboard project  build.py
#
# Le projet est IMPLICITE : c'est le dossier qui contient le manifeste. On ne
# balaye jamais les scripts au hasard ; seule cette liste fait foi.
#
# On remplit quatre tableaux paralleles : nom, mode, projet, script.
declare -a CMD_NAME=() CMD_MODE=() CMD_PROJ=() CMD_SCRIPT=()
declare -A SEEN=()     # detection des doublons de nom entre projets

load_manifests() {
  local manifest project line name mode script
  # `nullglob` pour que l'absence de manifeste ne laisse pas un motif litteral.
  shopt -s nullglob
  for manifest in "$WORKSPACE_ROOT"/*/"$MANIFEST_NAME"; do
    project="$(basename "$(dirname "$manifest")")"
    while IFS= read -r line || [ -n "$line" ]; do
      line="$(strip_cr "$line")"
      # Ignorer commentaires et lignes vides.
      case "$line" in ''|'#'*) continue ;; esac
      # Decouper en (au plus) trois champs : nom, mode, script.
      read -r name mode script _ <<<"$line"
      if [ -z "$name" ] || [ -z "$mode" ] || [ -z "$script" ]; then
        warn "$project/$MANIFEST_NAME : ligne mal formee, ignoree : $line"
        continue
      fi
      if [ "$mode" != "direct" ] && [ "$mode" != "project" ]; then
        warn "$project/$MANIFEST_NAME : mode inconnu '$mode' pour '$name' (attendu direct|project), ignore"
        continue
      fi
      if [ -n "${SEEN[$name]:-}" ]; then
        warn "commande '$name' declaree deux fois (${SEEN[$name]} et $project) : seconde ignoree"
        continue
      fi
      SEEN[$name]="$project"
      CMD_NAME+=("$name"); CMD_MODE+=("$mode"); CMD_PROJ+=("$project"); CMD_SCRIPT+=("$script")
    done < "$manifest"
  done
  shopt -u nullglob
}

# ---------------------------------------------------------------------------
# Action : --status
# ---------------------------------------------------------------------------
if [ "$ACTION" = "status" ]; then
  info "Espace de travail de cette copie de morfTools :"
  dim "$WORKSPACE_ROOT"
  info "Dossier des commandes : $BIN_DIR"
  if [ -f "$REGISTRY" ]; then
    info ""
    info "Commandes actuellement gerees par morfSystem :"
    # Colonnes : commande, mode, source. On montre aussi si la cible existe.
    while IFS=$'\t' read -r cmd mode source workspace; do
      case "$cmd" in ''|'#'*) continue ;; esac
      state="$C_OK""presente""$C_OFF"
      [ -e "$BIN_DIR/$cmd" ] || state="$C_ERR""absente""$C_OFF"
      printf '  %-18s %-8s %s  %s\n' "$cmd" "$mode" "$source" "$state"
    done < "$REGISTRY"
  else
    info ""
    dim "Aucune activation morfSystem enregistree dans $BIN_DIR."
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# Action : --deactivate
# ---------------------------------------------------------------------------
if [ "$ACTION" = "deactivate" ]; then
  if [ ! -f "$REGISTRY" ]; then
    info "Rien a desactiver : aucune activation enregistree dans $BIN_DIR."
    exit 0
  fi
  removed=0
  while IFS=$'\t' read -r cmd mode source workspace; do
    case "$cmd" in ''|'#'*) continue ;; esac
    tail=""
    # tail = "<projet>/<script>" reconstruit depuis la source enregistree.
    tail="$(basename "$(dirname "$source")")/$(basename "$source")"
    f="$BIN_DIR/$cmd"
    if [ ! -e "$f" ] && [ ! -L "$f" ]; then
      continue
    fi
    if is_managed "$f" "$cmd" "$tail"; then
      if [ "$DRY_RUN" = 1 ]; then
        info "  [dry-run] retirerait $cmd"
      else
        rm -f "$f"; ok "retire $cmd"
      fi
      removed=$((removed+1))
    else
      warn "$cmd n'est plus reconnu comme gere par morfSystem : laisse en place"
    fi
  done < "$REGISTRY"
  if [ "$DRY_RUN" = 1 ]; then
    info "[dry-run] $removed commande(s) seraient retiree(s). Registre conserve."
  else
    rm -f "$REGISTRY"
    info "Desactivation terminee : $removed commande(s) retiree(s)."
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# Action par defaut : activation
# ---------------------------------------------------------------------------
info "Activation des commandes morfSystem"
dim "espace   : $WORKSPACE_ROOT"
dim "commandes: $BIN_DIR"

load_manifests
if [ "${#CMD_NAME[@]}" -eq 0 ]; then
  warn "aucune commande declaree (aucun $MANIFEST_NAME sous $WORKSPACE_ROOT/*/)."
  exit 0
fi

# On prepare le dossier cible (sans jamais suivre plus loin : c'est ~/.local/bin).
if [ "$DRY_RUN" = 0 ]; then
  mkdir -p "$BIN_DIR"
fi

# Nouveau registre construit au fil de l'eau ; on ne remplace l'ancien qu'a la fin.
NEW_REGISTRY_LINES=()

created=0; updated=0; skipped=0

for i in "${!CMD_NAME[@]}"; do
  name="${CMD_NAME[$i]}"; mode="${CMD_MODE[$i]}"
  project="${CMD_PROJ[$i]}"; script="${CMD_SCRIPT[$i]}"
  proj_dir="$WORKSPACE_ROOT/$project"
  src="$proj_dir/$script"
  tail="$project/$script"
  dest="$BIN_DIR/$name"

  # --- Verifications prealables (une declaration invalide n'arrete pas les autres)
  if [ ! -d "$proj_dir" ]; then
    err "$name : projet absent dans l'espace actif ($proj_dir). Commande ignoree."
    skipped=$((skipped+1)); continue
  fi
  if [ ! -f "$src" ]; then
    err "$name : script introuvable ($src). Commande ignoree."
    skipped=$((skipped+1)); continue
  fi

  # --- Conflit : un fichier existe deja et n'est pas a nous -> on n'y touche pas.
  if { [ -e "$dest" ] || [ -L "$dest" ]; } && ! is_managed "$dest" "$name" "$tail"; then
    warn "$name existe deja dans $BIN_DIR et n'est pas gere par morfSystem."
    dim "aucune modification pour cette commande (securite)."
    skipped=$((skipped+1)); continue
  fi

  # --- Distinguer creation et mise a jour (pour un compte-rendu honnete).
  verb="cree"; former=""
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    verb="mis a jour"
    if [ -L "$dest" ]; then former="$(readlink "$dest" 2>/dev/null || true)"; fi
  fi

  if [ "$mode" = "direct" ]; then
    # -------- Mode direct : lien symbolique vers le script d'origine ----------
    # Le script doit pouvoir s'executer seul : shebang recommande, bit +x requis.
    if ! head -n1 "$src" | grep -q '^#!'; then
      warn "$name : $script n'a pas de shebang (#!) ; le lien pourrait ne pas s'executer."
    fi
    if [ "$DRY_RUN" = 1 ]; then
      info "  [dry-run] $name -> $src  (direct)"
    else
      chmod +x "$src" 2>/dev/null || true   # rendre la CLI executable (sa propre source)
      ln -sfn "$src" "$dest"
      if [ "$verb" = "cree" ]; then ok "$name -> $src"; else
        ok "$name -> $src (mis a jour)"; [ -n "$former" ] && [ "$former" != "$src" ] && dim "ancien : $former"
      fi
    fi
    NEW_REGISTRY_LINES+=("$name"$'\t'"direct"$'\t'"$src"$'\t'"$WORKSPACE_ROOT")

  else
    # -------- Mode project : lanceur qui entre dans le projet ------------------
    if [ "$DRY_RUN" = 1 ]; then
      info "  [dry-run] $name -> lanceur vers $src  (cwd=$proj_dir)"
    else
      # Rendre le script cible executable, puis ecrire le lanceur. Le lanceur ne
      # contient AUCUNE logique metier : il rejoint le projet et exec le script,
      # en transmettant tous les arguments tels quels ("$@") et en conservant le
      # code retour (exec).
      chmod +x "$src" 2>/dev/null || true
      cat > "$dest" <<EOF
#!/usr/bin/env bash
# $WRAPPER_MARK
# Genere par morfTools activate-cli.sh - NE PAS EDITER.
# Workspace : $WORKSPACE_ROOT
# Project   : $project
# Source    : $script
# Command   : $name
#
# Ce lanceur rejoint le projet proprietaire puis execute son script, pour
# respecter sa dependance a son propre repertoire. Regenere a chaque activation.
cd "$proj_dir" || exit 1
exec "./$script" "\$@"
EOF
      chmod +x "$dest"
      if [ "$verb" = "cree" ]; then ok "$name -> lanceur ($proj_dir)"; else
        ok "$name -> lanceur ($proj_dir) (mis a jour)"; fi
    fi
    NEW_REGISTRY_LINES+=("$name"$'\t'"project"$'\t'"$src"$'\t'"$WORKSPACE_ROOT")
  fi

  if [ "$verb" = "cree" ]; then created=$((created+1)); else updated=$((updated+1)); fi
done

# ---------------------------------------------------------------------------
# Nettoyage : retirer les commandes que NOUS gerions et qui ne sont plus declarees
# (par exemple apres avoir bascule d'espace, ou apres suppression d'une commande).
# On ne retire jamais un fichier etranger.
# ---------------------------------------------------------------------------
if [ -f "$REGISTRY" ]; then
  while IFS=$'\t' read -r old_cmd old_mode old_src old_ws; do
    case "$old_cmd" in ''|'#'*) continue ;; esac
    # Toujours declaree ? alors deja traitee ci-dessus.
    if [ -n "${SEEN[$old_cmd]:-}" ]; then continue; fi
    f="$BIN_DIR/$old_cmd"
    [ -e "$f" ] || [ -L "$f" ] || continue
    old_tail="$(basename "$(dirname "$old_src")")/$(basename "$old_src")"
    if is_managed "$f" "$old_cmd" "$old_tail"; then
      if [ "$DRY_RUN" = 1 ]; then
        info "  [dry-run] retirerait $old_cmd (n'est plus declaree)"
      else
        rm -f "$f"; ok "retire $old_cmd (n'est plus declaree)"
      fi
    fi
  done < "$REGISTRY"
fi

# ---------------------------------------------------------------------------
# Ecriture du nouveau registre (sauf en dry-run)
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = 0 ]; then
  {
    printf '# morfsystem-cli - registre des commandes gerees par activate-cli.sh.\n'
    printf '# Ne pas editer a la main. <commande>\\t<mode>\\t<source>\\t<workspace>\n'
    for l in "${NEW_REGISTRY_LINES[@]}"; do printf '%s\n' "$l"; done
  } > "$REGISTRY"
fi

# ---------------------------------------------------------------------------
# Bilan + rappel PATH
# ---------------------------------------------------------------------------
info ""
if [ "$DRY_RUN" = 1 ]; then
  info "Dry-run : aucun changement applique."
else
  info "Termine : $created creee(s), $updated mise(s) a jour, $skipped ignoree(s)."
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *)
    warn "$BIN_DIR n'est pas dans votre PATH."
    dim "Ajouter a votre ~/.bashrc :  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac
