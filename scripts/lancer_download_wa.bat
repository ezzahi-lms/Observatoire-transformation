@echo off
title Download Magazines WhatsApp - LMS ORH
echo.
echo ============================================
echo  Download Magazines WhatsApp - LMS ORH
echo ============================================
echo.
echo Lancement du telechargement automatique...
echo (Ne fermez pas cette fenetre)
echo.

py -3 "C:\Users\LMS\OneDrive - LMS ORH\Bureau\LMS-Orga\Observatoire Transformation\agent-veille\scripts\auto_download_wa_pdfs.py"

echo.
if %errorlevel% neq 0 (
    echo ERREUR - code de sortie : %errorlevel%
) else (
    echo Termine avec succes !
)
echo.
pause
