@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo.
echo  ============================================================
echo   AGENT VEILLE STRATEGIQUE -- Observatoire Transformation
echo   Lancement avec acces distant (ngrok)
echo  ============================================================
echo.

"C:\Users\LMS\AppData\Local\Programs\Python\Python314\python.exe" "%~dp0start_ngrok.py"

pause
