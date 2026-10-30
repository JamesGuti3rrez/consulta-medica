from __future__ import annotations
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest
from server.api.ai import get_service
from server.groups import group_report
from .conftest import headers,new_group,add,assign


def test_empty_groups_are_listed_without_creating_another_group(api):
    ids = {new_group(api, 'Grupo 01'), new_group(api, 'Grupo 02')}
    for _ in range(2):
        rows = api.get('/api/grupos/doctor', headers=headers('doctor-a')).json()['grupos']
        assert {g['id'] for g in rows} == ids
        assert all(g['alumnos'] == g['actividades'] == 0 for g in rows)


def test_group_name_unique_on_create_and_edit_ignoring_case_and_whitespace(api):
    first = new_group(api, 'Grupo 01')
    second = new_group(api, 'Grupo 02')
    for name in ['grupo 01', ' GRUPO   01 ', 'Grupo\t01', 'Grupo\u00a001']:
        for method, path in [('POST', '/api/grupos/doctor'), ('PATCH', f'/api/grupos/doctor/{second}')]:
            response = api.request(method, path, headers=headers('doctor-a'), json={'nombre': name})
            assert response.status_code == 409, response.text
            assert response.json()['detail'] == 'Ya tienes un grupo con ese nombre. Elige otro nombre.'
    same = api.patch(f'/api/grupos/doctor/{first}', headers=headers('doctor-a'), json={'nombre': 'GRUPO   01'})
    assert same.status_code == 200 and same.json()['nombre'] == 'GRUPO 01'
    # Cada doctor administra su propia lista, sin revelar grupos de otros propietarios.
    assert api.post('/api/grupos/doctor', headers=headers('doctor-b'), json={'nombre': 'Grupo 01'}).status_code == 201
    rows = api.get('/api/grupos/doctor', headers=headers('doctor-a')).json()['grupos']
    assert {g['nombre'] for g in rows} == {'GRUPO 01', 'Grupo 02'}


def test_concurrent_group_creations_have_one_winner(api):
    def create(name):
        return api.post('/api/grupos/doctor', headers=headers('doctor-a'), json={'nombre': name})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, ['Grupo simultáneo', ' grupo   SIMULTÁNEO ']))
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert len(api.get('/api/grupos/doctor', headers=headers('doctor-a')).json()['grupos']) == 1


def test_complete_group_assignment_grade_and_persistent_summary(api):
    gid=new_group(api)
    for user in ('alumno-a','alumno-b','alumno-c'):add(api,gid,user)
    aid=assign(api,gid)
    initial=api.get(f'/api/grupos/doctor/{gid}',headers=headers('doctor-a')).json()['actividades'][0]
    assert initial['resumen']['asignados']==3 and initial['resumen']['tasa_acierto'] is None
    assert all(r['puntaje_diagnostico'] is None for r in initial['resultados'])
    start=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a'))
    assert start.status_code==200,start.text
    sid=start.json()['session']['session_id']
    assert 'protected' not in start.json()['caso'] and 'session_token' not in start.json()['session']
    again=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a')).json()
    assert again['reutilizada'] and again['session']['session_id']==sid and len(again['eventos'])==1
    turn=api.post(f'/api/ai/sessions/{sid}/message',headers=headers('alumno-a'),json={'message':'Realizo exploración física'})
    assert turn.status_code==200,turn.text
    closed=api.post(f'/api/ai/sessions/{sid}/finish',headers=headers('alumno-a'),json={'diagnosis':'Basalioma'})
    assert closed.status_code==200,closed.text
    assert closed.json()['diagnosis_evaluation']['score']==100
    repeat=api.post(f'/api/ai/sessions/{sid}/finish',headers=headers('alumno-a'),json={'diagnosis':'Otra respuesta'})
    assert repeat.json()['diagnosis_evaluation']==closed.json()['diagnosis_evaluation']
    get_service.cache_clear() # Otra instancia recupera tanto sesión como comparación desde PostgreSQL.
    group=api.get(f'/api/grupos/doctor/{gid}',headers=headers('doctor-a')).json()
    activity=group['actividades'][0];row=next(r for r in activity['resultados'] if r['acierto']=='correct')
    assert row['diagnostico']=='Basalioma' and row['puntaje_diagnostico']==100
    assert row['puntaje_proceso']==closed.json()['evaluation']['score'] and row['duracion_segundos'] is not None
    assert activity['resumen']['tasa_acierto']==100 and activity['resumen']['entregas_evaluadas']==1
    assert len(activity['resultados'])==3
    reopened=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a')).json()
    assert reopened['session']['phase']=='finalizada'


@pytest.mark.parametrize('token,expected',[(None,401),('alumno-a',403),('invalido',401)])
def test_only_staff_can_create_or_list_groups(api,token,expected):
    h=headers(token) if token else {}
    assert api.get('/api/grupos/doctor',headers=h).status_code==expected
    assert api.post('/api/grupos/doctor',headers=h,json={'nombre':'Grupo'}).status_code==expected


def test_other_doctor_cannot_read_edit_enroll_assign_or_close(api):
    gid=new_group(api);aid=assign(api,gid)
    for method,path,body in [('GET',f'/doctor/{gid}',None),('PATCH',f'/doctor/{gid}',{'nombre':'Ajeno'}),
        ('POST',f'/doctor/{gid}/miembros',{'email':'alumno-a@example.com'}),
        ('POST',f'/doctor/{gid}/actividades',{'casos':[{'case_id':'MED-008','titulo':'Ajeno'}]}),
        ('PATCH',f'/doctor/actividades/{aid}',{'activa':False})]:
        r=api.request(method,'/api/grupos'+path,headers=headers('doctor-b'),json=body)
        assert r.status_code==404,r.text


def test_enrollment_is_unique_and_accepts_only_registered_student(api):
    gid=new_group(api);first=add(api,gid);assert add(api,gid)==first
    for email in ['inexistente@example.com','doctor-b@example.com']:
        assert api.post(f'/api/grupos/doctor/{gid}/miembros',headers=headers('doctor-a'),json={'email':email}).status_code==404
    rows=api.get(f'/api/grupos/doctor/{gid}',headers=headers('doctor-a')).json()['miembros'];assert len(rows)==1


def test_new_member_receives_open_assignment_and_removed_member_loses_all_session_routes(api):
    gid=new_group(api);aid=assign(api,gid);uid=add(api,gid)
    start=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a'));assert start.status_code==200
    sid=start.json()['session']['session_id']
    assert api.delete(f'/api/grupos/doctor/{gid}/miembros/{uid}',headers=headers('doctor-a')).status_code==200
    assert gid not in {g['grupo_id'] for g in api.get('/api/grupos/mios',headers=headers('alumno-a')).json()['grupos']}
    for method,suffix,body in [('GET','',None),('GET','/events',None),('GET','/report',None),
                            ('POST','/message',{'message':'¿Tiene alergias?'}),('POST','/finish',{})]:
        r=api.request(method,f'/api/ai/sessions/{sid}{suffix}',headers=headers('alumno-a'),json=body)
        assert r.status_code==404,r.text
    detail=api.get(f'/api/grupos/doctor/{gid}',headers=headers('doctor-a')).json()
    assert detail['miembros'][0]['activo'] is False and detail['actividades'][0]['resumen']['asignados']==0


@pytest.mark.parametrize('method,suffix',[('GET',''),('POST','/iniciar')])
def test_unassigned_user_and_guest_cannot_open_activity(api,method,suffix):
    gid=new_group(api);add(api,gid);aid=assign(api,gid)
    for token,status in [(None,401),('alumno-b',404),('doctor-b',404)]:
        r=api.request(method,f'/api/grupos/actividades/{aid}{suffix}',headers=headers(token) if token else {})
        assert r.status_code==status and 'caso' not in r.json()


def test_closed_assignment_blocks_new_start_and_allows_started_delivery(api):
    gid=new_group(api);add(api,gid);add(api,gid,'alumno-b');aid=assign(api,gid)
    start=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a')).json()
    api.patch(f'/api/grupos/doctor/actividades/{aid}',headers=headers('doctor-a'),json={'activa':False})
    assert api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-b')).status_code==404
    assert api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a')).status_code==200
    sid=start['session']['session_id']
    assert api.post(f'/api/ai/sessions/{sid}/finish',headers=headers('alumno-a'),json={}).status_code==200


def test_client_cannot_set_owner_grade_or_reveal_reference_in_title(api):
    assert api.post('/api/grupos/doctor',headers=headers('doctor-a'),json={'nombre':'X','doctor_id':'inventado'}).status_code==422
    gid=new_group(api)
    r=api.post(f'/api/grupos/doctor/{gid}/actividades',headers=headers('doctor-a'),json={'casos':[{'case_id':'MED-008','titulo':'Basalioma'}]})
    assert r.status_code==422
    add(api,gid);aid=assign(api,gid)
    r=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a'),json={'owner_id':'otro','case_id':'CIR-101','score':100})
    assert r.status_code==200 and r.json()['session']['case_id']=='MED-008'
    sid=r.json()['session']['session_id']
    other=api.get(f'/api/ai/sessions/{sid}',headers=headers('alumno-b'));assert other.status_code==404
    d=api.get(f'/api/grupos/doctor/{gid}',headers=headers('doctor-a')).json()['actividades'][0]['resultados'][0]
    assert d['diagnostico'] is None and d['puntaje_diagnostico'] is None


def test_summary_excludes_pending_review_and_non_submissions_from_accuracy():
    members=[{'alumno_id':str(i),'nombre':str(i),'email':f'{i}@example.com','activo':i!=5} for i in range(6)]
    rows=[]
    for i,status in enumerate(['correct','incorrect','empty','ambiguous',None,'incorrect']):
        closed=status is not None
        rows.append({'alumno_id':str(i),'asignacion_id':'A','session_id':str(i) if closed else None,
          'phase':'finalizada' if closed else None,'iniciado_en':'2026-10-30T10:00:00Z' if closed else None,
          'finalizado_en':'2026-10-30T10:12:00Z' if closed else None,
          'calificacion':{'status':status,'score':100 if status=='correct' else 0,'reason':'Fixture'} if closed else None,
          'diagnostico':'Texto' if closed else None,'puntaje_proceso':50 if closed else None})
    report=group_report({'grupo':{'id':'G'},'miembros':members,'actividades':[{'id':'A'}],'participaciones':rows})
    stats=report['actividades'][0]['resumen']
    assert stats['asignados']==5 and stats['finalizados']==4 and stats['pendientes_revision']==1
    assert stats['entregas_evaluadas']==3 and stats['tasa_acierto']==33.33 and stats['tiempo_promedio_segundos']==720
    assert report['actividades'][0]['resultados'][4]['puntaje_diagnostico'] is None


def test_concurrent_finish_keeps_first_result_and_late_turn_cannot_reopen(api):
    gid=new_group(api);add(api,gid);aid=assign(api,gid)
    sid=api.post(f'/api/grupos/actividades/{aid}/iniciar',headers=headers('alumno-a')).json()['session']['session_id']
    old=get_service().store.get(sid)
    def close(diagnosis):
        r=api.post(f'/api/ai/sessions/{sid}/finish',headers=headers('alumno-a'),json={'diagnosis':diagnosis})
        assert r.status_code==200,r.text
        return r.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(close,['Basalioma','Otra propuesta']))
    assert results[0]['diagnosis_evaluation']==results[1]['diagnosis_evaluation']
    events=api.get(f'/api/ai/sessions/{sid}/events',headers=headers('alumno-a')).json()
    assert sum(e['type']=='session_finished' for e in events)==1
    with pytest.raises(ValueError,match='finalizó'):
        get_service().store.save(old)
    assert get_service().store.get(sid)['phase']=='finalizada'
