# publish-releases.ps1 - enchaine la publication des releases du parc (Windows).
#
# Le pendant Windows de publish-releases.sh : meme chaine, a lancer sous Windows
# pour ajouter les livrables Windows a des releases dont le Pi fournit la part
# Linux (package-all.py --sync recupere ce qui est deja publie). Au moindre
# echec on s'arrete, pour ne jamais publier depuis un build incomplet.
$ErrorActionPreference = 'Stop'

# Se placer a la racine de morfTools : les scripts et ..\dist sont references
# en relatif.
Set-Location -Path $PSScriptRoot

# python3 n'existe pas toujours sous Windows : retomber sur python, puis py -3.
function Resolve-Python {
    foreach ($name in 'python3', 'python') {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return , @($cmd.Source) }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) { return , @('py', '-3') }
    throw "Aucun interpreteur Python trouve (python3, python ou py)."
}
$py = Resolve-Python

# Lance une commande native et stoppe la chaine si elle echoue : un code de
# sortie != 0 ne leve pas d'exception tout seul pour un .exe, il faut le tester.
function Invoke-Step {
    param([string] $Title, [string[]] $Command)
    Write-Host "`n==> $Title" -ForegroundColor Cyan
    & $Command[0] @($Command[1..($Command.Count - 1)])
    if ($LASTEXITCODE -ne 0) { throw "Echec ($LASTEXITCODE) a l'etape : $Title" }
}

Invoke-Step '1/5  git pull (mise a jour de morfTools)' @('git', 'pull')
Invoke-Step '2/5  morf dev pull (mise a jour de tous les projets)' ($py + @('morf.py', 'dev', 'pull'))
Invoke-Step '3/5  morf dev build (preparation des compilations)'   ($py + @('morf.py', 'dev', 'build'))
Invoke-Step '4/5  create-source-releases.py --all (releases source)' ($py + @('.\create-source-releases.py', '--all', '--notes', 'Source release for {project} {version}.'))
Invoke-Step '5/5  package-all.py --sync (livrables de cette machine)' ($py + @('.\package-all.py', '--sync', '--out', '..\dist'))

Write-Host "`nTermine : releases publiees." -ForegroundColor Green
