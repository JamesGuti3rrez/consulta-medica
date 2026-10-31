"""Panel Doctor y actividades de alumnos autenticados (HU-014)."""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from server.auth import AuthUser, current_user, require_staff
from server.cases.catalog import to_student_case
from server.cases import CaseNotFound, CaseNotAvailable
from server.cases.repository import CaseValidationError
from server.config import settings
from server.groups import group_report
from server.persistence.groups import SupabaseGroups, GroupStoreError

router = APIRouter(prefix='/api/grupos', tags=['grupos-doctor'])


def get_groups_store():
    return SupabaseGroups(settings.supabase_url, settings.supabase_secret_key)


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class GroupInput(Input):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default='', max_length=1000)


class MemberInput(Input):
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


class CaseInput(Input):
    case_id: str = Field(pattern=r'^[A-Z]{3,5}-\d{3}$')
    titulo: str = Field(min_length=1, max_length=150)


class AssignInput(Input):
    casos: list[CaseInput] = Field(min_length=1, max_length=20)


class ActivityInput(Input):
    activa: bool


@router.get('/doctor')
def doctor_groups(user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return {'grupos': store.rpc('doctor_listar_grupos', p_actor=user.id)}


@router.post('/doctor', status_code=201)
def create_group(payload: GroupInput, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return store.rpc('doctor_crear_grupo', p_actor=user.id, p_nombre=payload.nombre, p_descripcion=payload.descripcion)


@router.get('/doctor/{group_id}')
def doctor_detail(group_id: UUID, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return group_report(store.rpc('doctor_detalle_grupo', p_actor=user.id, p_grupo=str(group_id)))


@router.patch('/doctor/{group_id}')
def edit_group(group_id: UUID, payload: GroupInput, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return store.rpc('doctor_actualizar_grupo', p_actor=user.id, p_grupo=str(group_id), p_nombre=payload.nombre, p_descripcion=payload.descripcion)


@router.post('/doctor/{group_id}/miembros')
def add_member(group_id: UUID, payload: MemberInput, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return store.rpc('doctor_gestionar_miembro', p_actor=user.id, p_grupo=str(group_id),
                     p_email=payload.email.casefold(), p_alumno=None, p_activo=True)


@router.delete('/doctor/{group_id}/miembros/{student_id}')
def remove_member(group_id: UUID, student_id: UUID, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return store.rpc('doctor_gestionar_miembro', p_actor=user.id, p_grupo=str(group_id),
                     p_email=None, p_alumno=str(student_id), p_activo=False)


@router.post('/doctor/{group_id}/actividades', status_code=201)
def assign(group_id: UUID, payload: AssignInput, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    from server.api.ai import get_service
    store.rpc('doctor_detalle_grupo', p_actor=user.id, p_grupo=str(group_id))
    service = get_service()
    try:
        for case in payload.casos:
            service.repository.get_conversation_case(case.case_id)
            if not service.graph.output_guard.validate(case.titulo, service.graph.protected_lexicon.for_case(case.case_id))[0]:
                raise HTTPException(422, 'El título de la actividad no debe revelar la solución del caso.')
    except (CaseNotFound, CaseNotAvailable, CaseValidationError) as exc:
        raise HTTPException(409, 'Uno de los casos no está disponible para asignarse.') from exc
    return {'actividades': store.rpc('doctor_asignar_casos', p_actor=user.id, p_grupo=str(group_id),
                                     p_casos=[c.model_dump() for c in payload.casos])}


@router.patch('/doctor/actividades/{assignment_id}')
def close_activity(assignment_id: UUID, payload: ActivityInput, user: AuthUser = Depends(require_staff), store=Depends(get_groups_store)):
    return store.rpc('doctor_cerrar_actividad', p_actor=user.id, p_asignacion=str(assignment_id), p_activa=payload.activa)


@router.get('/mios')
def my_groups(user: AuthUser = Depends(current_user), store=Depends(get_groups_store)):
    return {'grupos': store.rpc('alumno_mis_grupos', p_actor=user.id)}


@router.get('/actividades/{assignment_id}')
def activity(assignment_id: UUID, user: AuthUser = Depends(current_user), store=Depends(get_groups_store)):
    from server.api.ai import get_service
    row = store.rpc('alumno_actividad', p_actor=user.id, p_asignacion=str(assignment_id))
    return {'actividad': row, 'caso': to_student_case(get_service().repository.get_case(row['case_id']))}


@router.post('/actividades/{assignment_id}/iniciar')
def start_activity(assignment_id: UUID, user: AuthUser = Depends(current_user), store=Depends(get_groups_store)):
    from server.api.ai import get_service
    from server.orchestration.supabase_store import SupabaseSessionStore
    service = get_service()
    if not isinstance(service.store, SupabaseSessionStore):
        raise GroupStoreError('Las actividades de grupo requieren sesiones persistentes en Supabase.')
    row = store.rpc('alumno_actividad', p_actor=user.id, p_asignacion=str(assignment_id))
    state = service.prepare_start(row['case_id'], owner_id=user.id)
    state['group_assignment_id'] = str(assignment_id)
    result = store.rpc('alumno_iniciar_actividad', p_actor=user.id, p_asignacion=str(assignment_id), p_estado=state)
    sid = result['session_id']
    return {'session': service.get(sid), 'reutilizada': result['reutilizada'],
            'caso': to_student_case(service.repository.get_case(row['case_id'])),
            'actividad': row, 'eventos': service.events(sid), 'evidencias': service.revealed(sid)}
