# ===========================================================================
#  download_magazines.ps1
#  Lance le telechargement automatique de TOUS les PDFs du groupe WhatsApp
#  "Biblio Observ Transfo" via Playwright (sans limite de 25 fichiers).
#
#  Premiere execution : scanner le QR code WhatsApp dans la fenetre qui s'ouvre
#  Executions suivantes : connexion automatique (session sauvegardee)
#
#  Usage : raccourci Ctrl+Alt+M ou double-clic
# ===========================================================================

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "auto_download_wa_pdfs.py"
$MAGAZINES_DIR = "C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\Magazines"

# ---------------------------------------------------------------------------
# Verifier que le script Python existe
# ---------------------------------------------------------------------------
if (-not (Test-Path $PythonScript)) {
    [System.Windows.Forms.MessageBox]::Show(
        "Script introuvable :`n$PythonScript",
        "Erreur",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

# ---------------------------------------------------------------------------
# Verifier que Playwright est installe
# ---------------------------------------------------------------------------
$playwrightCheck = py -3 -c "import playwright; print('ok')" 2>&1
if ($playwrightCheck -ne "ok") {
    Add-Type -AssemblyName System.Windows.Forms
    $install = [System.Windows.Forms.MessageBox]::Show(
        "Playwright n'est pas installe.`n`nCliquez OK pour l'installer automatiquement (une seule fois).",
        "Installation requise",
        [System.Windows.Forms.MessageBoxButtons]::OKCancel,
        [System.Windows.Forms.MessageBoxIcon]::Information
    )
    if ($install -eq "OK") {
        Write-Host "Installation de Playwright..."
        py -3 -m pip install playwright
        py -3 -m playwright install chromium
        py -3 -m playwright install-deps chromium 2>$null
        Write-Host "Installation terminee."
    } else {
        exit 0
    }
}

# ---------------------------------------------------------------------------
# Verifier que Chromium est bien telecharge
# ---------------------------------------------------------------------------
$chromiumExe = Get-Item "$env:LOCALAPPDATA\ms-playwright\chromium-*\chrome-win64\chrome.exe" -ErrorAction SilentlyContinue
if (-not $chromiumExe) {
    Write-Host "Chromium manquant — telechargement en cours..."
    py -3 -m playwright install chromium
}

# ---------------------------------------------------------------------------
# Compter les PDFs avant
# ---------------------------------------------------------------------------
$before = (Get-ChildItem -Path $MAGAZINES_DIR -Filter "*.pdf" -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "PDFs avant : $before"

# ---------------------------------------------------------------------------
# Lancer le telechargement
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Lancement du telechargement automatique..."
Write-Host "(Une fenetre de navigateur va s'ouvrir)"
Write-Host ""

if ($before -eq 0) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "Une fenetre de navigateur va s'ouvrir.`n`nSi c'est la premiere fois :`n  -> Scannez le QR code avec votre telephone`n`nEnsuite le telechargement demarre automatiquement.",
        "Download Magazines - LMS ORH",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
} else {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "Telechargement automatique en cours.`n`nDossier actuel : $before PDFs`n`nUne fenetre de navigateur va s'ouvrir.`nNe la fermez pas pendant le telechargement.",
        "Download Magazines - LMS ORH",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

# Lancer Python (fenetre visible pour voir la progression)
Start-Process "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -NoExit -Command `"py -3 '$PythonScript'`"" -WindowStyle Normal -Wait

# ---------------------------------------------------------------------------
# Compter les PDFs apres
# ---------------------------------------------------------------------------
$after = (Get-ChildItem -Path $MAGAZINES_DIR -Filter "*.pdf" -ErrorAction SilentlyContinue | Measure-Object).Count
$nouveaux = $after - $before

Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = "Magazines mis a jour"

if ($nouveaux -gt 0) {
    $notify.BalloonTipText = "$nouveaux nouveau(x) PDF(s) telecharge(s). Total : $after PDFs."
} else {
    $notify.BalloonTipText = "Aucun nouveau PDF. Dossier a jour ($after PDFs)."
}

$notify.Visible = $true
$notify.ShowBalloonTip(8000)
Start-Sleep -Milliseconds 8500
$notify.Dispose()
