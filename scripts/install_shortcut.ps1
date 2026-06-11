# ─────────────────────────────────────────────────────────────────────────────
#  install_shortcut.ps1
#  Crée un raccourci Windows (Ctrl+Alt+M) vers download_magazines.ps1
#  sur le Bureau ET dans le menu Démarrer.
#
#  À exécuter UNE SEULE FOIS (clic droit → Exécuter avec PowerShell)
# ─────────────────────────────────────────────────────────────────────────────

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "download_magazines.ps1"
$IconPath   = "$env:SystemRoot\System32\shell32.dll"   # icône Windows standard

# Vérifie que le script source existe
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERREUR : download_magazines.ps1 introuvable dans $ScriptDir" -ForegroundColor Red
    Read-Host "Appuyez sur Entrée pour quitter"
    exit 1
}

# ── Créer le raccourci ────────────────────────────────────────────────────────
function New-Shortcut {
    param([string]$Destination, [string]$HotKey = "")

    $WshShell  = New-Object -ComObject WScript.Shell
    $Shortcut  = $WshShell.CreateShortcut($Destination)
    $Shortcut.TargetPath  = "powershell.exe"
    $Shortcut.Arguments   = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Description = "Ouvrir WhatsApp Web pour telecharger les magazines PDF"
    $Shortcut.IconLocation = "$IconPath,16"   # icône téléchargement
    if ($HotKey) { $Shortcut.HotKey = $HotKey }
    $Shortcut.Save()
    Write-Host "  Raccourci cree : $Destination" -ForegroundColor Green
}

# Bureau
$Desktop = [System.Environment]::GetFolderPath("Desktop")
New-Shortcut -Destination "$Desktop\Download Magazines.lnk" -HotKey "Ctrl+Alt+M"

# Menu Démarrer (nécessaire pour que le raccourci clavier fonctionne globalement)
$StartMenu = "$env:AppData\Microsoft\Windows\Start Menu\Programs"
New-Shortcut -Destination "$StartMenu\Download Magazines LMS.lnk" -HotKey "Ctrl+Alt+M"

Write-Host ""
Write-Host "Installation terminee !" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Raccourci clavier : Ctrl + Alt + M" -ForegroundColor Yellow
Write-Host "  (valide depuis n'importe quelle application)"
Write-Host ""
Write-Host "  Un raccourci 'Download Magazines' a ete ajoute sur le Bureau."
Write-Host ""

# Test rapide : vérifier que PowerShell peut exécuter des scripts
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq "Restricted") {
    Write-Host "ATTENTION : La politique d'execution PowerShell est 'Restricted'." -ForegroundColor Yellow
    Write-Host "Exécutez cette commande pour autoriser les scripts :" -ForegroundColor Yellow
    Write-Host "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor White
}

Read-Host "Appuyez sur Entree pour fermer"
