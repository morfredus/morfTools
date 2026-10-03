#!/usr/bin/env bash
# publish-releases.sh - enchaine la publication des releases du parc (Linux/Pi).
#
# Un seul point d'entree pour la chaine que je lancais commande par commande.
# Chaque etape depend de la precedente : au moindre echec on s'arrete (set -e),
# pour ne jamais publier des assets construits a partir d'un build incomplet.
#
# A lancer sur CHAQUE machine qui produit des livrables : cette version pour le
# Pi/Linux, publish-releases.ps1 sous Windows. package-all.py --sync recupere au
# passage les assets deja publies de l'autre plateforme, si bien que la release
# finit complete quelle que soit la machine qui termine en dernier.
set -euo pipefail

# Option : --with-arm64-cross ajoute, en plus des livrables natifs, la
# cross-compilation Linux arm64 (utile sous WSL x86_64 avec un sysroot prepare,
# MORF_SYSROOT). package-all.py garde ce drapeau sans effet sur tout autre hote,
# donc l'invocation reste sure partout. Repli propre sur toute autre option.
#
# Option : --only NOM limite toute la chaine a UN projet (nom canonique exact,
# casse comprise : SiteWatch, pas sitewatch). Les etapes 4 et 5 l'exigent telle
# quelle ; morf dev pull/build, lui, ignore la casse.
EXTRA_PACKAGE_ARGS=()
WITH_ARM64_CROSS=0
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-arm64-cross) EXTRA_PACKAGE_ARGS+=(--with-arm64-cross); WITH_ARM64_CROSS=1 ;;
    --only)
      [ $# -ge 2 ] || { printf '%s\n' '--only attend un nom de projet.' >&2; exit 2; }
      ONLY="$2"; shift ;;
    --only=*) ONLY="${1#--only=}" ;;
    *) printf 'Option inconnue ignoree : %s\n' "$1" >&2 ;;
  esac
  shift
done
if [ -n "$ONLY" ]; then
  MORF_ONLY=(--only "$ONLY")          # morf dev pull / build
  SOURCE_SCOPE=(--only "$ONLY")       # create-source-releases.py (remplace --all)
  EXTRA_PACKAGE_ARGS+=(--only "$ONLY")
else
  MORF_ONLY=()
  SOURCE_SCOPE=(--all)
fi

# Toujours travailler depuis la racine de morfTools : create-source-releases.py,
# package-all.py et ../dist sont references en relatif.
cd "$(dirname "$0")"

# Pas de pre-vol "appli ouverte" ici : sous Linux, relinker un executable en
# cours d'execution ne le verrouille pas (l'ancien inode reste valide). Ce verrou
# est un piege Windows, traite dans publish-releases.ps1.

CURRENT_STEP=""
step() { CURRENT_STEP="$1"; printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

# La chaine est en set -e : la moindre etape qui echoue arrete tout, pour ne
# jamais publier a partir d'un build incomplet. Sans repere, cet arret se perd
# dans la masse de la sortie. Ce trap affiche une banniere rouge sans ambiguite
# qui nomme l'etape fautive et rappelle que les etapes suivantes n'ont pas tourne.
on_error() {
  printf '\n\033[1;31m========================================================================\033[0m\n' >&2
  printf '\033[1;31m  PUBLICATION INTERROMPUE\033[0m\n' >&2
  printf '\033[1;31m  Etape : %s\033[0m\n' "$CURRENT_STEP" >&2
  printf '\033[1;31m========================================================================\033[0m\n' >&2
  printf '  Cause : voir le message juste au-dessus (souvent un depot non\n' >&2
  printf '          publiable : working tree sale, ou en avance sur origin).\n' >&2
  printf '  Les etapes suivantes N'"'"'ont pas ete executees' >&2
  if [ "$WITH_ARM64_CROSS" = "1" ]; then
    printf ' -- le packaging arm64 (5/5) non plus.\n' >&2
  else
    printf '.\n' >&2
  fi
  printf '  Corrige la cause, puis relance la publication.\n' >&2
}
trap on_error ERR

step "1/5  git pull (mise a jour de morfTools)"
git pull

step "2/5  morf dev pull (mise a jour de tous les projets)"
python3 morf.py dev pull "${MORF_ONLY[@]}"

step "3/5  morf dev build (preparation des compilations)"
# morf dev build ne prepare QUE le build natif (x86_64) : le message
# "auto-detected ... : linux" est normal et ne concerne pas l'arm64.
if [ "$WITH_ARM64_CROSS" = "1" ]; then
  printf '\033[1;33m    [arm64] Le build croise arm64 est produit a l'"'"'etape 5/5 (packaging),\n'
  printf '            pas ici. Cette etape 3/5 ne prepare que le natif.\033[0m\n'
fi
python3 morf.py dev build "${MORF_ONLY[@]}"

step "4/5  create-source-releases.py ${SOURCE_SCOPE[*]} (releases source)"
python3 ./create-source-releases.py "${SOURCE_SCOPE[@]}" \
  --notes "Source release for {project} {version}."

step "5/5  package-all.py --sync (livrables de cette machine)"
python3 ./package-all.py --sync --out ../dist "${EXTRA_PACKAGE_ARGS[@]}"

trap - ERR
printf '\n\033[1;32mTermine : releases publiees.\033[0m\n'
