"""Réessayer les hoquets réseau/SSH transitoires des opérations git distantes.

`git fetch`/`pull`/`push`/`clone` parlent à GitHub par SSH. Une connexion qui
saute (« Connection closed by ... port 22 », « Connection reset », un blip DNS...)
est un échec de TRANSPORT transitoire, pas une vraie erreur : un seul suffisait à
faire échouer toute la chaîne de publication (publish-releases). Ce helper ne
réessaie QUE ces hoquets, avec un court backoff, et ne masque JAMAIS une vraie
erreur (accès refusé, non-fast-forward, conflit, clé d'hôte inconnue...).
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

# Motifs de hoquets réseau/SSH transitoires. Volontairement restreint au
# TRANSPORT : rien ici ne correspond à un refus d'authentification, un
# non-fast-forward ou un conflit, qui doivent remonter immédiatement.
_TRANSIENT = re.compile(
    r"connection closed|connection reset|connection timed out|closed by remote host|"
    r"timed out|timeout|kex_exchange_identification|broken pipe|early eof|"
    r"the remote end hung up|remote end hung up unexpectedly|"
    r"ssh_exchange_identification|connection refused|network is unreachable|"
    r"temporary failure in name resolution|could not resolve host|"
    r"failed to connect to github|unable to access|could not read from remote repository",
    re.IGNORECASE,
)


def is_transient(text: str) -> bool:
    """True si la sortie ressemble à un hoquet de transport transitoire."""
    return bool(_TRANSIENT.search(text or ""))


def run_git(args, cwd: Path | None = None, *, attempts: int = 4, backoff: float = 2.0,
            echo=None) -> subprocess.CompletedProcess:
    """Lance une commande git en ne réessayant QUE les hoquets réseau transitoires.

    Capture toujours les deux flux (pour lire le signal transitoire) ; l'appelant
    décide de ce qu'un code non nul signifie. `echo`, s'il est fourni, reçoit un
    message lisible avant chaque nouvel essai.
    """
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    attempt = 1
    while result.returncode != 0 and attempt < attempts:
        blob = (result.stderr or "") + (result.stdout or "")
        if not is_transient(blob):
            break
        wait = backoff * attempt
        if echo:
            echo(f"réseau git instable, nouvel essai dans {wait:.0f} s "
                 f"({attempt}/{attempts - 1})...")
        time.sleep(wait)
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
        attempt += 1
    return result
