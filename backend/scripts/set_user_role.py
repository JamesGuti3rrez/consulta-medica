"""Asigna un rol de aplicación a una cuenta existente; usa solo la clave secreta del servidor."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from server.config import settings


def assign_role(email: str, role: str, *, url: str, secret_key: str, client=None, dry_run=False):
    if not url or not secret_key:
        raise ValueError("Configura SUPABASE_URL y SUPABASE_SECRET_KEY.")
    normalized = email.strip().casefold()
    if "@" not in normalized or any(char.isspace() for char in normalized):
        raise ValueError("Escribe el correo exacto, sin espacios.")
    if role not in {"alumno", "profesor", "administrativo"}:
        raise ValueError("Rol no válido.")
    headers = {"apikey": secret_key}
    if not secret_key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {secret_key}"
    def request(method, path, **kwargs):
        if client is not None:
            response = client.request(method, url.rstrip("/") + path, headers=headers, **kwargs)
        else:
            with httpx.Client(timeout=20) as http:
                response = http.request(method, url.rstrip("/") + path, headers=headers, **kwargs)
        if response.is_error:
            raise ValueError(f"Supabase Auth respondió HTTP {response.status_code}.")
        return response.json()
    matches, page = [], 1
    while True:
        payload = request("GET", "/auth/v1/admin/users", params={"page": page, "per_page": 100})
        users = payload.get("users", [])
        matches.extend(user for user in users if (user.get("email") or "").casefold() == normalized)
        if len(users) < 100:
            break
        page += 1
    if len(matches) != 1:
        raise ValueError("No se encontró una única cuenta con ese correo en este proyecto de Supabase.")
    user = matches[0]
    metadata = {**(user.get("app_metadata") or {}), "rol": role}
    if not dry_run:
        request("PUT", f"/auth/v1/admin/users/{user['id']}", json={"app_metadata": metadata})
        verified = request("GET", f"/auth/v1/admin/users/{user['id']}")
        if (verified.get("app_metadata") or {}).get("rol") != role:
            raise ValueError("No se pudo verificar el cambio de rol.")
    return {"email": normalized, "rol": role, "aplicado": not dry_run}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--rol", choices=["alumno", "profesor", "administrativo"], default="profesor")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = assign_role(args.email, args.rol, url=settings.supabase_url,
                             secret_key=settings.supabase_secret_key, dry_run=args.dry_run)
        print(f"Cuenta: {result['email']}; rol: {result['rol']}; aplicado: {result['aplicado']}.")
        if result["aplicado"]:
            print("Cierra sesión y vuelve a iniciarla para actualizar el acceso.")
        return 0
    except (ValueError, httpx.HTTPError):
        print("No se pudo asignar el rol. Comprueba el correo, las credenciales y la conexión.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

