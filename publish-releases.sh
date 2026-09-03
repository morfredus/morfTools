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
EXTRA_PACKAGE_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --with-arm64-cross) EXTRA_PACKAGE_ARGS+=(--with-arm64-cross) ;;
    *) printf 'Option inconnue ignoree : %s\n' "$arg" >&2 ;;
  esac
done

# Toujours travailler depuis la racine de morfTools : create-source-releases.py,
# package-all.py et ../dist sont references en relatif.
cd "$(dirname "$0")"

# Pas de pre-vol "appli ouverte" ici : sous Linux, relinker un executable en
# cours d'execution ne le verrouille pas (l'ancien inode reste valide). Ce verrou
# est un piege Windows, traite dans publish-releases.ps1.

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

step "1/5  git pull (mise a jour de morfTools)"
git pull

step "2/5  morf dev pull (mise a jour de tous les projets)"
python3 morf.py dev pull

step "3/5  morf dev build (preparation des compilations)"
python3 morf.py dev build

step "4/5  create-source-releases.py --all (releases source)"
python3 ./create-source-releases.py --all \
  --notes "Source release for {project} {version}."

step "5/5  package-all.py --sync (livrables de cette machine)"
python3 ./package-all.py --sync --out ../dist "${EXTRA_PACKAGE_ARGS[@]}"

printf '\n\033[1;32mTermine : releases publiees.\033[0m\n'
