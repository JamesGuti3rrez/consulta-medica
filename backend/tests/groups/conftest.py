from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import socket
import subprocess
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from server.api import ai, groups
import server.auth as auth
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import LocalDevelopmentProvider
from server.cases.catalog import CURATED_CASES_DIR
from server.main import app
from server.orchestration.supabase_store import SupabaseSessionStore

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def sql_server():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env={**os.environ,'HU014_SQL_PORT':str(port)}
    process=subprocess.Popen(['node',str(ROOT/'pruebas/HU-014/sql_server.mjs')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            if process.poll() is not None:raise RuntimeError('No pudo iniciarse PostgreSQL de pruebas; ejecuta npm install.')
            try:
                if httpx.get(url+'/__health',timeout=1).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        else:raise RuntimeError('PostgreSQL de pruebas no respondió.')
        yield url
    finally:
        process.terminate();process.wait(timeout=10)


@pytest.fixture
def api(sql_server,monkeypatch,tmp_path):
    # Cada prueba conserva identidades/casos de fixture, pero empieza sin grupos ajenos.
    httpx.post(sql_server+'/__clear_groups', timeout=25).raise_for_status()
    config=replace(ai.settings,supabase_url=sql_server,supabase_publishable_key='sb_publishable_fixture',
      supabase_secret_key='sb_secret_fixture',case_store='local',session_store='supabase',rag_backend='local',
      rag_embedded_enabled=False,rag_service_url='',history_enabled=False,synthetic_case_data=False,
      synthetic_exam_data=False,langsmith_tracing=False,trace_path=tmp_path/'audit.jsonl')
    for module in (ai,groups,auth):monkeypatch.setattr(module,'settings',config)
    monkeypatch.setattr(ai,'STORE',SupabaseSessionStore(sql_server,'sb_secret_fixture'))
    monkeypatch.setattr(ai,'CASES_DIR',CURATED_CASES_DIR)
    monkeypatch.setattr(ai,'build_gateway',lambda:LLMGateway([LocalDevelopmentProvider()]))
    ai.get_service.cache_clear();ai.get_session_auth.cache_clear();ai.get_attempts.cache_clear()
    with TestClient(app) as client:yield client
    ai.get_service.cache_clear();ai.get_session_auth.cache_clear();ai.get_attempts.cache_clear()


def headers(token):return {'Authorization':'Bearer '+token}


def new_group(client, name='Grupo API'):
    response=client.post('/api/grupos/doctor',headers=headers('doctor-a'),json={'nombre':name,'descripcion':'Pruebas HTTP'})
    assert response.status_code==201,response.text
    return response.json()['id']


def add(client,gid,student='alumno-a'):
    r=client.post(f'/api/grupos/doctor/{gid}/miembros',headers=headers('doctor-a'),json={'email':student+'@example.com'})
    assert r.status_code==200,r.text
    return r.json()['alumno_id']


def assign(client,gid,title='Consulta clínica',case='MED-008'):
    r=client.post(f'/api/grupos/doctor/{gid}/actividades',headers=headers('doctor-a'),json={'casos':[{'case_id':case,'titulo':title}]})
    assert r.status_code==201,r.text
    return r.json()['actividades'][0]['id']
