# ─────────────────────────────────────────────────────────────────────────────
#  download_magazines.ps1
#  Ouvre WhatsApp Web sur le groupe Biblio Observ Transfo dans Chrome,
#  prêt pour télécharger les PDFs via WA Media Downloader Pro.
#
#  Usage : raccourci clavier Ctrl+Alt+M (installé par install_shortcut.ps1)
#          ou double-clic sur le .lnk du bureau
# ─────────────────────────────────────────────────────────────────────────────

$WHATSAPP_URL  = "https://web.whatsapp.com"
$GROUP_NAME    = "Biblio Observ Transfo"
$MAGAZINES_DIR = "C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\Magazines"

# ── Notification Windows ──────────────────────────────────────────────────────
function Show-Toast {
    param([string]$Title, [string]$Message, [string]$Icon = "Info")
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = $Title
    $notify.BalloonTipText  = $Message
    $notify.Visible = $true
    $notify.ShowBalloonTip(6000)
    Start-Sleep -Milliseconds 6500
    $notify.Dispose()
}

# ── Compter les PDFs actuels dans le dossier ─────────────────────────────────
$before = (Get-ChildItem -Path $MAGAZINES_DIR -Filter "*.pdf" -ErrorAction SilentlyContinue |
           Measure-Object).Count

# ── Chercher si Chrome est déjà ouvert avec WhatsApp Web ─────────────────────
$chromeProcess = Get-Process -Name "chrome" -ErrorAction SilentlyContinue

if ($chromeProcess) {
    # Chrome est ouvert — ouvrir un nouvel onglet sur WhatsApp Web
    Start-Process "chrome.exe" -ArgumentList "--new-tab", $WHATSAPP_URL
} else {
    # Lancer Chrome sur WhatsApp Web
    $chromePaths = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
        "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
    )
    $chromeExe = $chromePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chromeExe) {
        Start-Process $chromeExe -ArgumentList $WHATSAPP_URL
    } else {
        # Fallback : ouvrir avec le navigateur par défaut
        Start-Process $WHATSAPP_URL
    }
}

# ── Mettre Chrome au premier plan ────────────────────────────────────────────
Start-Sleep -Seconds 1
$chrome = Get-Process -Name "chrome" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($chrome) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinAPI {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
    [WinAPI]::ShowWindow($chrome.MainWindowHandle, 9)   # SW_RESTORE
    [WinAPI]::SetForegroundWindow($chrome.MainWindowHandle)
}

# ── Instructions ─────────────────────────────────────────────────────────────
$msg = @"
WhatsApp Web ouvert.

Etapes :
  1. Naviguez vers le groupe "$GROUP_NAME"
  2. Cliquez sur l'icone WA Media Downloader Pro
  3. Filtrez par PDF
  4. Cliquez Telecharger tout
  5. Dossier : Magazines

PDFs actuellement dans le dossier : $before
"@

Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show(
    $msg,
    "Download Magazines — LMS ORH",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null

# ── Vérifier si de nouveaux PDFs ont été ajoutés ─────────────────────────────
$after = (Get-ChildItem -Path $MAGAZINES_DIR -Filter "*.pdf" -ErrorAction SilentlyContinue |
          Measure-Object).Count

$nouveaux = $after - $before
if ($nouveaux -gt 0) {
    Show-Toast -Title "Magazines mis a jour" -Message "$nouveaux nouveau(x) PDF(s) ajoute(s) dans le dossier."
} else {
    Show-Toast -Title "Magazines" -Message "Dossier verifie. $after PDFs presents."
}
