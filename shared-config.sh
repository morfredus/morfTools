#!/usr/bin/env bash
# Conserve pour ne pas casser les habitudes et les procedures deja ecrites.
# Le point d'entree unique est desormais « config.sh shared ».
echo "Note: './config.sh shared $*' is the current entry point." >&2
exec "$(dirname "$0")/scripts/linux/shared-config.sh" "$@"
