"""Proyección de resultados de grupo; las notas proceden de la sesión cerrada del servidor."""
from __future__ import annotations

from datetime import datetime
from statistics import mean


def duration(start, finish):
    if not start or not finish:
        return None
    try:
        return max(0, int((datetime.fromisoformat(finish.replace('Z', '+00:00')) -
                           datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds()))
    except (ValueError, TypeError):
        return None


def group_report(detail):
    members = {m['alumno_id']: m for m in detail['miembros']}
    activities = []
    for assignment in detail['actividades']:
        rows = []
        for participation in detail['participaciones']:
            if participation['asignacion_id'] != assignment['id']:
                continue
            member = members[participation['alumno_id']]
            closed = participation.get('phase') == 'finalizada' and bool(participation.get('finalizado_en'))
            grade = participation.get('calificacion') if closed else None
            status = (grade or {}).get('status')
            resolved = status in {'correct', 'incorrect', 'empty'}
            # Sin calificación automática (TA-021 pendiente) la entrega queda finalizada; solo una calificada ambigua espera revisión.
            state = 'pendiente_revision' if closed and grade and not resolved else 'finalizada' if closed else 'en_curso' if participation.get('session_id') else 'sin_iniciar'
            rows.append({'alumno_id': member['alumno_id'], 'nombre': member['nombre'] or member['email'],
                         'email': member['email'], 'miembro_activo': member['activo'], 'estado': state,
                         'iniciado_en': participation.get('iniciado_en'),
                         'finalizado_en': participation.get('finalizado_en') if closed else None,
                         'duracion_segundos': duration(participation.get('iniciado_en'), participation.get('finalizado_en')) if closed else None,
                         'diagnostico': participation.get('diagnostico') if closed else None,
                         'acierto': status if closed else None,
                         'puntaje_diagnostico': grade.get('score') if grade else None,
                         'motivo': grade.get('reason') if grade else None,
                         'puntaje_proceso': participation.get('puntaje_proceso') if closed else None})
        rows.sort(key=lambda r: r['nombre'].casefold())
        active = [r for r in rows if r['miembro_activo']]
        done = [r for r in active if r['estado'] in {'finalizada', 'pendiente_revision'}]
        evaluated = [r for r in done if r['acierto'] in {'correct', 'incorrect', 'empty'}]
        def average(values):
            values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
            return round(mean(values), 2) if values else None
        stats = {'asignados': len(active), 'iniciados': sum(r['estado'] != 'sin_iniciar' for r in active),
                 'finalizados': len(done), 'pendientes_revision': sum(r['estado'] == 'pendiente_revision' for r in active),
                 'aciertos': sum(r['acierto'] == 'correct' for r in evaluated), 'entregas_evaluadas': len(evaluated),
                 'tasa_acierto': round(100 * sum(r['acierto'] == 'correct' for r in evaluated) / len(evaluated), 2) if evaluated else None,
                 'tiempo_promedio_segundos': average(r['duracion_segundos'] for r in done),
                 'puntaje_diagnostico_promedio': average(r['puntaje_diagnostico'] for r in evaluated),
                 'puntaje_proceso_promedio': average(r['puntaje_proceso'] for r in done)}
        activities.append({**assignment, 'resultados': rows, 'resumen': stats})
    return {'grupo': detail['grupo'], 'miembros': detail['miembros'], 'actividades': activities,
            'reglas': {'entregas_por_actividad': 1, 'duracion': 'Tiempo transcurrido entre inicio y primer cierre, incluidas pausas.',
                       'comparacion': 'Misma actividad; solo integrantes activos en los promedios. Historial de retirados conservado.',
                       'acierto': 'Correctos / entregas evaluadas. Ambiguas pendientes de revisión excluidas.',
                       'puntajes': 'Diagnóstico y proceso independientes; sin ponderación combinada.'}}
