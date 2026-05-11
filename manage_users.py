"""
Gestion des utilisateurs — Observatoire Transformation
Usage :
  python manage_users.py list              # Lister les utilisateurs
  python manage_users.py add               # Ajouter un utilisateur (interactif)
  python manage_users.py delete <username> # Supprimer un utilisateur
  python manage_users.py reset <username>  # Réinitialiser le mot de passe
"""
import sys
import getpass
from pathlib import Path

import yaml
from yaml.loader import SafeLoader
import bcrypt

USERS_FILE = Path(__file__).parent / "config" / "users.yaml"


def load() -> dict:
    with open(USERS_FILE, encoding="utf-8") as f:
        return yaml.load(f, Loader=SafeLoader)

def save(cfg: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def cmd_list():
    cfg = load()
    users = cfg["credentials"]["usernames"]
    print(f"\n{'='*55}")
    print(f"  Utilisateurs ({len(users)})")
    print(f"{'='*55}")
    print(f"  {'Identifiant':<22} {'Nom':<20} {'Rôle'}")
    print(f"  {'-'*50}")
    for uname, udata in users.items():
        role = udata.get("role", "user")
        print(f"  {uname:<22} {udata.get('name', ''):<20} {role}")
    print()


def cmd_add():
    cfg = load()
    users = cfg["credentials"]["usernames"]

    print("\n  Ajouter un utilisateur")
    print("  ─────────────────────")
    username = input("  Identifiant (ex: prenom.nom) : ").strip()
    if not username:
        print("  ❌ Identifiant vide.")
        return
    if username in users:
        print(f"  ❌ L'identifiant '{username}' existe déjà.")
        return

    name  = input("  Nom complet : ").strip()
    email = input("  Email : ").strip()
    role  = input("  Rôle [user/admin] (défaut: user) : ").strip() or "user"

    password = getpass.getpass("  Mot de passe : ")
    confirm  = getpass.getpass("  Confirmer le mot de passe : ")

    if password != confirm:
        print("  ❌ Les mots de passe ne correspondent pas.")
        return
    if len(password) < 8:
        print("  ❌ Le mot de passe doit contenir au moins 8 caractères.")
        return

    users[username] = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "role": role,
    }
    cfg["credentials"]["usernames"] = users
    save(cfg)
    print(f"\n  ✅ Utilisateur '{username}' ({name}) ajouté avec succès.\n")


def cmd_delete(username: str):
    cfg = load()
    users = cfg["credentials"]["usernames"]

    if username not in users:
        print(f"  ❌ Utilisateur '{username}' introuvable.")
        return

    confirm = input(f"  Supprimer '{username}' ({users[username]['name']}) ? [oui/non] : ")
    if confirm.lower() in ("oui", "o", "yes", "y"):
        del users[username]
        cfg["credentials"]["usernames"] = users
        save(cfg)
        print(f"  ✅ Utilisateur '{username}' supprimé.\n")
    else:
        print("  Annulé.\n")


def cmd_reset(username: str):
    cfg = load()
    users = cfg["credentials"]["usernames"]

    if username not in users:
        print(f"  ❌ Utilisateur '{username}' introuvable.")
        return

    print(f"  Réinitialisation du mot de passe pour : {users[username]['name']}")
    password = getpass.getpass("  Nouveau mot de passe : ")
    confirm  = getpass.getpass("  Confirmer : ")

    if password != confirm:
        print("  ❌ Les mots de passe ne correspondent pas.")
        return
    if len(password) < 8:
        print("  ❌ Minimum 8 caractères.")
        return

    users[username]["password"] = hash_password(password)
    cfg["credentials"]["usernames"] = users
    save(cfg)
    print(f"  ✅ Mot de passe réinitialisé pour '{username}'.\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    elif cmd == "add":
        cmd_add()
    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("  Usage : python manage_users.py delete <username>")
        else:
            cmd_delete(sys.argv[2])
    elif cmd == "reset":
        if len(sys.argv) < 3:
            print("  Usage : python manage_users.py reset <username>")
        else:
            cmd_reset(sys.argv[2])
    else:
        print(f"  Commande inconnue : {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
