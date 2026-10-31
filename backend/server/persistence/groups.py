"""HU-014: RPC de grupos, aisladas del catálogo y del historial opcional de intentos."""
from __future__ import annotations

import httpx
from fastapi import HTTPException


class GroupStoreError(RuntimeError):
    pass


class SupabaseGroups:
    def __init__(self, url, secret, *, client=None):
        if not url or not secret:
            raise GroupStoreError("Configura Supabase para utilizar los grupos.")
        self.base = url.rstrip('/') + '/rest/v1/rpc/'
        self.headers = {'apikey': secret}
        if not secret.startswith('sb_'):
            self.headers['Authorization'] = 'Bearer ' + secret
        self.client = client

    def rpc(self, function, **payload):
        try:
            if self.client is not None:
                response = self.client.post(self.base + function, headers=self.headers, json=payload)
            else:
                with httpx.Client(timeout=25) as client:
                    response = client.post(self.base + function, headers=self.headers, json=payload)
        except httpx.HTTPError as exc:
            raise GroupStoreError("No se pudo conectar con los grupos. Inténtalo de nuevo.") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise GroupStoreError("La respuesta de grupos no es válida.") from exc
        if response.is_error:
            code = body.get('code') if isinstance(body, dict) else None
            if code == 'P0002':
                message = 'No hay un alumno registrado con ese correo.' if body.get('message') == 'alumno_registrado_no_encontrado' else 'Grupo, integrante o actividad no disponible.'
                raise HTTPException(404, message)
            if code == '42501':
                raise HTTPException(403, 'No tienes permiso para realizar esta operación.')
            if code == '23505' and 'doctor_grupos_nombre_unico' in body.get('message', ''):
                raise HTTPException(409, 'Ya tienes un grupo con ese nombre. Elige otro nombre.')
            if code in {'22023', '23514', '23503', '23505', '22P02'}:
                raise HTTPException(409, 'La actividad o los datos cambiaron. Actualiza el grupo y revisa la solicitud.')
            if response.status_code == 404:
                raise GroupStoreError('El módulo de grupos aún no está habilitado en Supabase. Completa su configuración para continuar.')
            raise GroupStoreError('No se pudo completar la operación de grupos.')
        return body
