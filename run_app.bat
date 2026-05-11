@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo.
echo  ============================================================
echo   AGENT VEILLE STRATEGIQUE — Observatoire Transformation
echo  ============================================================
echo.
echo  Demarrage de l'interface graphique...
echo  Ouvrez votre navigateur sur : http://localhost:8501
echo  (Ctrl+C pour arreter)
echo.

"C:\Users\LMS\AppData\Local\Programs\Python\Python314\python.exe" -m streamlit run "%~dp0app.py" --server.port 8501 --server.headless false --browser.gatherUsageStats false

pause
