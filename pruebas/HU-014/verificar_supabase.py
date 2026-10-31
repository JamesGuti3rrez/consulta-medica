"""HU-014 real: Auth, grupos/RPC, sesión y métricas. Solo cuentas/grupos temporales propios."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import json,secrets,sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
import httpx
from fastapi.testclient import TestClient
from server.config import settings
from server.api import ai
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.main import app


def main():
    http=httpx.Client(timeout=25);base=settings.supabase_url.rstrip('/')
    admin={'apikey':settings.supabase_secret_key}
    if not settings.supabase_secret_key.startswith('sb_'):admin['Authorization']='Bearer '+settings.supabase_secret_key
    users=[];groups=[];sessions=[];checks=[]
    report={'tarea':'HU-014','fecha':'2026-10-30','inicio_utc':datetime.now(timezone.utc).isoformat(),
      'supabase_real':True,'llm':'Proveedor local controlado; no necesario para evaluar el diagnóstico final.',
      'resultado':'PENDIENTE','pruebas':checks}
    original=ai.settings;gateway=ai.build_gateway
    def request(method,path,**kw):
        r=http.request(method,base+path,headers=kw.pop('headers',admin),**kw)
        if r.is_error:raise RuntimeError('Servicio remoto HTTP '+str(r.status_code))
        return r
    def check(value,label):
        if not value:raise RuntimeError(label)
        checks.append({'prueba':label,'resultado':'PASA'});print('[PASA] '+label,flush=True)
    def account(role,index):
        email=f'hu014-{uuid4().hex}@example.com';password=secrets.token_urlsafe(32)
        u=request('POST','/auth/v1/admin/users',json={'email':email,'password':password,'email_confirm':True,
            'app_metadata':{'rol':role},'user_metadata':{'nombres':'HU014','apellidos':index}}).json()
        users.append(u['id'])
        token=request('POST','/auth/v1/token',params={'grant_type':'password'},headers={'apikey':settings.supabase_publishable_key},json={'email':email,'password':password}).json()['access_token']
        return {'id':u['id'],'email':email,'token':token,'headers':{'Authorization':'Bearer '+token}}
    try:
        print('HU-014 | Supabase real: cuentas, grupos, asignaciones y sesiones temporales.',flush=True)
        doctor=account('profesor','Doctor A');other=account('profesor','Doctor B')
        students=[account('alumno',f'Alumno {i+1}') for i in range(5)]
        check(len(users)==7,'Siete cuentas temporales autenticadas; no se enviaron correos')
        ai.settings=replace(settings,langsmith_tracing=False,trace_path=ROOT/'pruebas/HU-014/auditoria_real.jsonl')
        ai.build_gateway=lambda:LLMGateway([LocalDevelopmentProvider()]);ai.get_service.cache_clear();ai.get_session_auth.cache_clear()
        with TestClient(app) as client:
            r=client.post('/api/grupos/doctor',headers=doctor['headers'],json={'nombre':'HU014 · Grupo temporal','descripcion':'Validación automática; se elimina al terminar'})
            check(r.status_code==201,'Doctor crea su grupo en Supabase');gid=r.json()['id'];groups.append(gid)
            empty=client.get('/api/grupos/doctor',headers=doctor['headers']).json()['grupos']
            check(len(empty)==1 and empty[0]['id']==gid and empty[0]['alumnos']==empty[0]['actividades']==0,
                  'Supabase recupera el grupo vacío antes de añadir alumnos o crear otro grupo')
            for method,path in [('POST','/api/grupos/doctor'),('PATCH',f'/api/grupos/doctor/{gid}')]:
                # Editar el mismo grupo sí debe aceptar su propio nombre.
                name=' hu014   ·   GRUPO TEMPORAL '
                duplicate=client.request(method,path,headers=doctor['headers'],json={'nombre':name})
                if method=='POST':
                    check(duplicate.status_code==409 and 'Ya tienes un grupo' in duplicate.json()['detail'],
                          '0006 activa: Supabase rechaza el nombre duplicado con HTTP 409')
                else:
                    check(duplicate.status_code==200 and duplicate.json()['nombre']=='hu014 · GRUPO TEMPORAL',
                          'Editar el mismo grupo normaliza espacios y conserva su identidad')
            check(client.get(f'/api/grupos/doctor/{gid}',headers=other['headers']).status_code==404,'Otro doctor no accede al grupo ajeno')
            for student in students:
                response=client.post(f'/api/grupos/doctor/{gid}/miembros',headers=doctor['headers'],json={'email':student['email']})
                if response.status_code!=200:raise RuntimeError('No se pudo incorporar una cuenta temporal')
            client.post(f'/api/grupos/doctor/{gid}/miembros',headers=doctor['headers'],json={'email':students[0]['email']})
            d=client.get(f'/api/grupos/doctor/{gid}',headers=doctor['headers']).json()
            check(len(d['miembros'])==5,'Cinco integrantes registrados; incorporación repetida sin duplicados')
            r=client.post(f'/api/grupos/doctor/{gid}/actividades',headers=doctor['headers'],json={'casos':[{'case_id':'MED-008','titulo':'Actividad de verificación'}]})
            check(r.status_code==201,'Asignación curada publicada al grupo');aid=r.json()['actividades'][0]['id']
            check(client.get(f'/api/grupos/actividades/{aid}').status_code==401,'Actividad de grupo requiere autenticación')
            diagnoses=['Basalioma','Respuesta no admitida','Basalioma o dermatitis']
            first_delivery=None
            for index,student in enumerate(students[:4]):
                r=client.post(f'/api/grupos/actividades/{aid}/iniciar',headers=student['headers'])
                if r.status_code!=200:raise RuntimeError('No se pudo iniciar una actividad asignada')
                sid=r.json()['session']['session_id'];sessions.append(sid)
                if index<3:
                    if index==0:
                        def finish(value):
                            return client.post(f'/api/ai/sessions/{sid}/finish',headers=student['headers'],json={'diagnosis':value})
                        with ThreadPoolExecutor(max_workers=2) as pool:
                            concurrent=list(pool.map(finish,['Basalioma','Carcinoma de células basales']))
                        check(all(r.status_code==200 for r in concurrent) and concurrent[0].json()['diagnosis_evaluation']==concurrent[1].json()['diagnosis_evaluation'],
                              'Dos cierres simultáneos conservan la primera calificación')
                        closed=concurrent[0];first_delivery=closed.json()['report']['diagnosis']['student']
                        events=client.get(f'/api/ai/sessions/{sid}/events',headers=student['headers']).json()
                        check(sum(e['type']=='session_finished' for e in events)==1,'Solo un evento de cierre para solicitudes concurrentes')
                    else:
                        closed=client.post(f'/api/ai/sessions/{sid}/finish',headers=student['headers'],json={'diagnosis':diagnoses[index]})
                    if closed.status_code!=200:raise RuntimeError('No se confirmó el cierre de una sesión asignada')
            d=client.get(f'/api/grupos/doctor/{gid}',headers=doctor['headers']).json();a=d['actividades'][0];s=a['resumen']
            states=[r['estado'] for r in a['resultados']]
            check(s['asignados']==5 and s['finalizados']==3 and s['pendientes_revision']==1 and s['tasa_acierto']==50,
                  'Comparativa: 5 asignados, 3 finalizados, 1 pendiente; acierto 1/2 = 50%')
            check('sin_iniciar' in states and 'en_curso' in states,'Sin iniciar y en curso separados de las entregas incorrectas')
            check(all(r['duracion_segundos'] is not None for r in a['resultados'] if r['estado'] in {'finalizada','pendiente_revision'}),
                  'Duración del alumno calculada con inicio y cierre persistidos')
            check(all(r['diagnostico'] is None and r['puntaje_diagnostico'] is None for r in a['resultados'] if r['estado'] in {'sin_iniciar','en_curso'}),
                  'Sin diagnóstico ni puntuación expuestos antes del cierre')
            # Nuevo servicio y repetición no crean otra entrega ni reemplazan el diagnóstico original.
            ai.get_service.cache_clear()
            start=client.post(f'/api/grupos/actividades/{aid}/iniciar',headers=students[0]['headers']).json()
            check(start['reutilizada'] and start['session']['session_id']==sessions[0],'Nueva instancia reutiliza la entrega original')
            again=client.post(f'/api/ai/sessions/{sessions[0]}/finish',headers=students[0]['headers'],json={'diagnosis':'Otra respuesta'}).json()
            check(again['diagnosis_evaluation']['score']==100 and again['report']['diagnosis']['student']==first_delivery,'Repetir cierre no altera el acierto ni la respuesta entregada')
            student=students[0]
            r=client.delete(f'/api/grupos/doctor/{gid}/miembros/{student["id"]}',headers=doctor['headers'])
            check(r.status_code==200 and client.get(f'/api/ai/sessions/{sessions[0]}/report',headers=student['headers']).status_code==404,
                  'Retirar integrante revoca su acceso a la sesión de grupo')
            detail=client.get(f'/api/grupos/doctor/{gid}',headers=doctor['headers']).json()
            check(len(detail['actividades'][0]['resultados'])==5,'Resultados históricos del integrante retirado se conservan')
            public={'apikey':settings.supabase_publishable_key,'Authorization':'Bearer '+students[1]['token']}
            for table in ['doctor_grupos','doctor_grupo_miembros','doctor_asignaciones','doctor_participaciones']:
                denied=http.get(base+'/rest/v1/'+table,headers=public,params={'select':'*','limit':1})
                if denied.status_code not in (401,403):raise RuntimeError('Acceso directo a tabla no denegado')
            denied=http.post(base+'/rest/v1/rpc/doctor_listar_grupos',headers=public,json={'p_actor':doctor['id']})
            check(denied.status_code in (401,403),'RLS y privilegios: navegador sin acceso directo a las cuatro tablas ni RPC')
            # Solo resultados de fixtures propios, sin tokens ni claves, para el informe.
            report['comparativa_previa_al_retiro']=a
            report['resultado']='PASA'
    except Exception as exc:
        report['resultado']='FALLA';report['error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
        print('[FALLA] '+report['error'],flush=True)
    finally:
        try:
            for sid in sessions:
                request('DELETE','/rest/v1/sma_sesiones',params={'session_id':'eq.'+sid})
                if request('GET','/rest/v1/sma_sesiones',params={'session_id':'eq.'+sid,'select':'session_id'}).json():raise RuntimeError('Limpieza de sesión no confirmada')
                if request('GET','/rest/v1/sma_eventos',params={'session_id':'eq.'+sid,'select':'id'}).json():raise RuntimeError('Limpieza de evento no confirmada')
            for gid in groups:
                request('DELETE','/rest/v1/doctor_grupos',params={'id':'eq.'+gid})
                if request('GET','/rest/v1/doctor_grupos',params={'id':'eq.'+gid,'select':'id'}).json():raise RuntimeError('Limpieza de grupo no confirmada')
            for uid in users:
                request('DELETE','/auth/v1/admin/users/'+uid)
                if http.get(base+'/auth/v1/admin/users/'+uid,headers=admin).status_code!=404:raise RuntimeError('Limpieza de cuenta no confirmada')
            report['limpieza']={'confirmada':True,'cuentas':len(users),'grupos':len(groups),'sesiones':len(sessions),'eventos_eliminados':True}
            print('[PASA] Limpieza: '+str(len(users))+' cuentas, '+str(len(groups))+' grupo y '+str(len(sessions))+' sesiones con sus eventos.',flush=True)
        except Exception:
            report['resultado']='FALLA';report['limpieza']={'confirmada':False};print('[FALLA] Limpieza requiere revisión.',flush=True)
        report['ids_temporales']={'cuentas':users,'grupos':groups,'sesiones':sessions}
        (ROOT/'pruebas/HU-014/supabase_real.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        ai.settings=original;ai.build_gateway=gateway;ai.get_service.cache_clear();ai.get_session_auth.cache_clear();http.close()
    print('Resultado final: '+report['resultado'],flush=True)
    return 0 if report['resultado']=='PASA' else 1


if __name__=='__main__':raise SystemExit(main())
