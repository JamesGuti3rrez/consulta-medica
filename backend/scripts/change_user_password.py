"""Actualiza solo la contraseña de una cuenta existente, con entrada oculta en terminal.

No recrea usuarios ni modifica app_metadata. Referencia del contrato de administración:
https://supabase.com/docs/reference/python/auth-admin-updateuserbyid
"""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from server.config import settings


def change_password(email, password, *, url, secret_key, client):
    email = email.strip().casefold()
    if '@' not in email or any(ch.isspace() for ch in email):
        raise ValueError('Escribe el correo exacto, sin espacios.')
    if len(password) < 8:
        raise ValueError('La nueva contraseña debe tener al menos 8 caracteres.')
    if not url or not secret_key:
        raise ValueError('Faltan las credenciales de administración de Supabase en .env.')
    headers = {'apikey': secret_key}
    if not secret_key.startswith('sb_'):
        headers['Authorization'] = 'Bearer ' + secret_key

    def request(method, path, **kwargs):
        try:
            response = client.request(method, url.rstrip('/') + path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ValueError('No se pudo conectar con Supabase.') from exc
        if response.is_error:
            # Los errores remotos no se imprimen: podrían contener datos sensibles.
            raise ValueError('Supabase rechazó la operación. Comprueba las claves y los requisitos de la contraseña.')
        return response.json()

    matches = []
    page = 1
    while True:
        users = request('GET', '/auth/v1/admin/users', params={'page': page, 'per_page': 100}).get('users', [])
        matches.extend(user for user in users if str(user.get('email') or '').casefold() == email)
        if len(users) < 100:
            break
        page += 1
    if len(matches) != 1:
        raise ValueError('No se encontró una única cuenta con ese correo. No se modificó ninguna cuenta.')
    user = matches[0]
    request('PUT', '/auth/v1/admin/users/' + user['id'], json={'password': password})
    verified = request('GET', '/auth/v1/admin/users/' + user['id'])
    if verified.get('id') != user['id'] or verified.get('app_metadata') != user.get('app_metadata'):
        raise ValueError('La contraseña se actualizó, pero los metadatos de la cuenta cambiaron; revisa su configuración.')
    return {'email': email, 'rol': (verified.get('app_metadata') or {}).get('rol', 'alumno')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    try:
        if not sys.stdin.isatty():
            raise ValueError('Ejecuta este comando desde la terminal interactiva de VS Code.')
        print('Actualizarás la contraseña de: ' + args.email)
        password = getpass.getpass('Nueva contraseña (no se mostrará al escribir): ')
        confirmation = getpass.getpass('Repite la nueva contraseña: ')
        if password != confirmation:
            raise ValueError('Las contraseñas no coinciden. No se realizó ningún cambio.')
        with httpx.Client(timeout=20) as client:
            result = change_password(args.email, password, url=settings.supabase_url,
                                     secret_key=settings.supabase_secret_key, client=client)
        print('Contraseña actualizada. Usuario conservado; rol: ' + result['rol'] + '.')
        print('Ya puedes iniciar sesión en http://localhost:3000 con la nueva contraseña.')
        return 0
    except (ValueError, EOFError, KeyboardInterrupt) as exc:
        print(str(exc) or 'Operación cancelada.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
