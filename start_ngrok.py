"""
Lanceur combiné : Streamlit + ngrok
Lance l'app localement sur le port 8501 et crée un tunnel ngrok public.
"""
import os
import sys
import time
import subprocess
import threading
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).parent

# ── Chargement du .env ────────────────────────────────────────────────────────
env = dotenv_values(ROOT / ".env", encoding="utf-8")
for k, v in env.items():
    if v and not os.environ.get(k):   # écrase aussi les valeurs vides
        os.environ[k] = v

NGROK_TOKEN = os.environ.get("NGROK_AUTHTOKEN", "")
if not NGROK_TOKEN:
    print("❌  NGROK_AUTHTOKEN manquant dans le fichier .env")
    sys.exit(1)

PYTHON = sys.executable
PORT   = 8501


def start_streamlit():
    """Lance Streamlit en sous-processus."""
    cmd = [
        PYTHON, "-m", "streamlit", "run",
        str(ROOT / "app.py"),
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    env_proc = os.environ.copy()
    env_proc["PYTHONIOENCODING"] = "utf-8"
    env_proc["PYTHONUTF8"]       = "1"
    return subprocess.Popen(cmd, env=env_proc, cwd=str(ROOT))


def start_ngrok():
    """Crée le tunnel ngrok et affiche l'URL publique."""
    from pyngrok import ngrok, conf

    # Configurer le token
    conf.get_default().auth_token = NGROK_TOKEN

    # Attendre que Streamlit soit prêt
    time.sleep(4)

    # Ouvrir le tunnel
    tunnel = ngrok.connect(PORT, "http")
    url = tunnel.public_url

    print()
    print("=" * 60)
    print("  ✅  OBSERVATOIRE EN LIGNE")
    print("=" * 60)
    print(f"  🌐  URL publique  : {url}")
    print(f"  💻  URL locale    : http://localhost:{PORT}")
    print()
    print("  Partagez l'URL publique avec votre équipe.")
    print("  Ctrl+C pour arrêter.")
    print("=" * 60)
    print()

    return tunnel


def main():
    print()
    print("=" * 60)
    print("  Observatoire de la Transformation Organisationnelle")
    print("  Démarrage en cours…")
    print("=" * 60)

    # Lancer Streamlit
    print("\n  [1/2] Démarrage de Streamlit…")
    proc = start_streamlit()

    # Lancer ngrok
    print("  [2/2] Création du tunnel ngrok…")
    try:
        tunnel = start_ngrok()
    except Exception as e:
        print(f"\n❌  Erreur ngrok : {e}")
        proc.terminate()
        sys.exit(1)

    # Attendre Ctrl+C
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n  Arrêt en cours…")
        from pyngrok import ngrok
        ngrok.kill()
        proc.terminate()
        print("  ✅  Arrêté proprement.\n")


if __name__ == "__main__":
    main()
