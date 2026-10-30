"""Verifica login de una cuenta propia temporal, sin modificar la cuenta del usuario."""
from pathlib import Path
from uuid import uuid4
import os,secrets,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
import httpx
from server.config import settings


def main():
    headers={'apikey':settings.supabase_secret_key}
    if not settings.supabase_secret_key.startswith('sb_'):headers['Authorization']='Bearer '+settings.supabase_secret_key
    uid=None
    with httpx.Client(timeout=20) as client:
        try:
            email=f'login-check-{uuid4().hex}@example.com';password=secrets.token_urlsafe(32)
            r=client.post(settings.supabase_url+'/auth/v1/admin/users',headers=headers,json={
                'email':email,'password':password,'email_confirm':True,'app_metadata':{'rol':'profesor'}})
            if r.is_error:raise RuntimeError('No pudo crearse la cuenta temporal: HTTP '+str(r.status_code))
            uid=r.json()['id']
            result=subprocess.run(['node','pruebas/HU-014/probar_login_real.mjs'],cwd=ROOT,
              env={**os.environ,'LOGIN_TEST_EMAIL':email,'LOGIN_TEST_PASSWORD':password},capture_output=True,text=True,timeout=90)
            if result.stdout:print(result.stdout.strip())
            if result.returncode:print('La comprobación del formulario no terminó correctamente; revisar login/redirección.')
            return result.returncode
        finally:
            if uid:
                r=client.delete(settings.supabase_url+'/auth/v1/admin/users/'+uid,headers=headers)
                if r.is_error:raise RuntimeError('No pudo eliminarse la cuenta temporal.')
                check=client.get(settings.supabase_url+'/auth/v1/admin/users/'+uid,headers=headers)
                if check.status_code!=404:raise RuntimeError('No se confirmó la eliminación de la cuenta temporal.')
                print('Cuenta temporal eliminada. Cuenta original sin cambios.')


if __name__=='__main__':raise SystemExit(main())
