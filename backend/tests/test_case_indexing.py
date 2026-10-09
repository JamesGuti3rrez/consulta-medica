from __future__ import annotations

import asyncio
import json
import shutil
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

from case_preparation.indexing.documents import (
    IndexingError,
    build_case_documents,
    documents_fingerprint,
    load_approved_knowledge_documents,
)


@contextmanager
def workspace_artifacts(name: str):
    path = Path(__file__).resolve().parent / f".{name}-artifacts"
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def case_fixture() -> dict:
    return {
        "case_id": "MED-001",
        "status": "curado",
        "public": {
            "patient": {"age_years": 42, "sex": "femenino", "alias": "Paciente 1"},
            "chief_complaint": {
                "evidence_id": "MED-001.motivo.dolor",
                "category": "motivo",
                "label": "Motivo",
                "text": "Dolor abdominal desde ayer.",
            },
            "items": [
                {
                    "evidence_id": "MED-001.historia.no_indexar",
                    "category": "anamnesis",
                    "label": "No indexar",
                    "text": "Este campo no autorizado no debe salir.",
                }
            ],
            "allergies_recorded": False,
        },
        "on_request": [
            {
                "evidence_id": "MED-001.anamnesis.inicio",
                "category": "anamnesis",
                "label": "Inicio y evolución",
                "text": "Comenzó hace un día.",
                "reveal_policy": {
                    "owner": "paciente",
                    "mode": "al_preguntar",
                    "requires": ["inicio_y_evolucion"],
                },
            },
            {
                "evidence_id": "MED-001.examen.exploracion",
                "category": "examen_fisico",
                "label": "Exploración física",
                "text": "Abdomen blando, doloroso a la palpación.",
                "reveal_policy": {
                    "owner": "medico_asistente",
                    "mode": "al_examinar",
                    "requires": ["exploracion_fisica"],
                },
            },
            {
                "evidence_id": "MED-001.lab.hemograma",
                "category": "laboratorio",
                "label": "Hemograma",
                "text": "Hemoglobina 13 g/dL.",
                "reveal_policy": {
                    "owner": "laboratorio",
                    "mode": "al_solicitar_examen",
                    "requires": ["hemograma"],
                },
            },
            {
                "evidence_id": "MED-001.img.radiografia_torax",
                "category": "imagen",
                "label": "Radiografía de tórax",
                "text": "Sin hallazgos agudos.",
                "reveal_policy": {
                    "owner": "radiologia",
                    "mode": "al_solicitar_examen",
                    "requires": ["radiografia_torax"],
                },
            },
        ],
        "protected": {
            "diagnosis": {"name": "Diagnóstico reservado", "synonyms": ["Diagnóstico final reservado"]},
            "differentials": [{"name": "Diferencial reservado"}],
            "treatment_reference": {"summary": "Tratamiento reservado", "key_actions": ["Acción reservada"]},
            "contraindications": [],
            "evaluation": {"key_questions": [{"topic": "Texto de evaluación reservado"}]},
        },
    }


def test_case_documents_are_separated_by_role_and_keep_requires():
    docs = build_case_documents([case_fixture()])

    assert [doc.role for doc in docs] == [
        "laboratorio",
        "medico_asistente",
        "paciente",
        "public",
        "radiologia",
    ]
    by_role = {doc.role: doc for doc in docs}
    assert by_role["paciente"].requires == ("inicio_y_evolucion",)
    assert by_role["medico_asistente"].requires == ("exploracion_fisica",)
    assert by_role["laboratorio"].requires == ("hemograma",)
    assert by_role["radiologia"].requires == ("radiografia_torax",)
    assert "42" in by_role["public"].text and "femenino" in by_role["public"].text
    assert "no autorizado" not in "\n".join(doc.text for doc in docs)
    assert "Paciente 1" not in "\n".join(doc.text for doc in docs)
    assert all("reservado" not in doc.text for doc in docs)


def test_document_order_and_fingerprint_are_deterministic():
    first = case_fixture()
    second = case_fixture()
    second["case_id"] = "MED-002"
    second["public"]["chief_complaint"]["evidence_id"] = "MED-002.motivo.dolor"

    forward = build_case_documents([first, second])
    backward = build_case_documents([second, first])

    assert forward == backward
    assert documents_fingerprint(forward) == documents_fingerprint(backward)
    assert documents_fingerprint(forward) != documents_fingerprint(forward[:-1])


def test_requires_order_is_preserved_in_index_metadata():
    case = case_fixture()
    case["on_request"][0]["reveal_policy"]["requires"] = [
        "inicio_y_evolucion",
        "caracteristicas_sintoma",
    ]

    documents = build_case_documents([case])

    patient_doc = next(document for document in documents if document.role == "paciente")
    assert patient_doc.requires == ("inicio_y_evolucion", "caracteristicas_sintoma")


@pytest.mark.parametrize(
    ("owner", "mode", "requires"),
    [
        ("paciente", "al_preguntar", ["historia_clinica"]),
        ("medico_asistente", "al_preguntar", ["exploracion_fisica"]),
        ("laboratorio", "al_solicitar_examen", ["Hemograma completo"]),
        ("radiologia", "al_solicitar_examen", ["radiografia__torax"]),
    ],
)
def test_invalid_role_contract_fails_closed(owner, mode, requires):
    case = case_fixture()
    policy = case["on_request"][0]["reveal_policy"]
    policy.update(owner=owner, mode=mode, requires=requires)

    with pytest.raises(IndexingError, match="requires/mode"):
        build_case_documents([case])


def test_protected_leak_is_normalized_and_rejects_entire_case():
    case = case_fixture()
    case["on_request"][0]["text"] = "Se menciona DIAGNOSTICO RESERVADO al paciente."

    with pytest.raises(IndexingError, match="contenido de protected"):
        build_case_documents([case])


def test_differential_synonym_leak_is_rejected():
    case = case_fixture()
    case["protected"]["differentials"][0]["name"] = "Cetoacidosis diabética"
    case["protected"]["differentials"][0]["synonyms"] = ["CAD"]
    case["on_request"][0]["text"] = "El paciente tiene CAD."

    with pytest.raises(IndexingError, match="contenido de protected"):
        build_case_documents([case])


def test_uncurated_case_and_duplicate_ids_are_rejected():
    case = case_fixture()
    case["status"] = "validado"
    with pytest.raises(IndexingError, match="status=curado"):
        build_case_documents([case])

    case["status"] = "curado"
    with pytest.raises(IndexingError, match="duplicado"):
        build_case_documents([case, case])


def test_knowledge_registry_loads_only_explicitly_approved_documents():
    with workspace_artifacts("knowledge") as knowledge_dir:
        approved_dir = knowledge_dir / "approved"
        approved_dir.mkdir()
        (approved_dir / "guia.md").write_text("Contenido aprobado de prueba.", encoding="utf-8")
        (knowledge_dir / "registry.json").write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "id": "guia-prueba",
                            "path": "approved/guia.md",
                            "license": "MIT",
                            "reviewed_by": "revisor clínico",
                            "scope": "evaluation",
                            "approved": True,
                        },
                        {"id": "pendiente", "approved": False},
                    ]
                }
            ),
            encoding="utf-8",
        )

        docs = load_approved_knowledge_documents(knowledge_dir)

        assert len(docs) == 1
        assert docs[0].role == "knowledge:evaluation"
        assert "Licencia: MIT" in docs[0].text
        assert "Contenido aprobado de prueba." in docs[0].text


def test_knowledge_registry_rejects_paths_outside_approved_folder():
    with workspace_artifacts("knowledge-path") as knowledge_dir:
        (knowledge_dir / "registry.json").write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "id": "fuera",
                            "path": "../outside.md",
                            "license": "MIT",
                            "reviewed_by": "revisor",
                            "scope": "conversation",
                            "approved": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(IndexingError, match="path debe apuntar"):
            load_approved_knowledge_documents(knowledge_dir)


def test_approved_knowledge_cannot_reveal_an_active_case_protected_term():
    case = case_fixture()
    with workspace_artifacts("knowledge-leak") as knowledge_dir:
        approved_dir = knowledge_dir / "approved"
        approved_dir.mkdir()
        (approved_dir / "guia.md").write_text("Referencia a diagnóstico reservado.", encoding="utf-8")
        (knowledge_dir / "registry.json").write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "id": "guia",
                            "path": "approved/guia.md",
                            "license": "MIT",
                            "reviewed_by": "revisor",
                            "scope": "conversation",
                            "approved": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(IndexingError, match="contenido de protected"):
            load_approved_knowledge_documents(knowledge_dir, [case])


def test_lightrag_backend_uses_pinned_api_without_external_llm(monkeypatch):
    from case_preparation.indexing import lightrag_backend

    calls = []
    assert asyncio.run(lightrag_backend._no_entity_extraction("prompt")) == "<|COMPLETE|>"

    class FakeEmbeddingFunc:
        def __init__(self, **kwargs):
            self.options = kwargs

    class FakeLightRAG:
        def __init__(self, **kwargs):
            self.options = kwargs
            calls.append(("construct", kwargs["working_dir"]))

        async def initialize_storages(self):
            calls.append(("initialize",))

        async def ainsert(self, text, **kwargs):
            calls.append(("insert", text, kwargs))

        async def finalize_storages(self):
            calls.append(("finalize",))

    lightrag = types.ModuleType("lightrag")
    lightrag.LightRAG = FakeLightRAG
    lightrag_utils = types.ModuleType("lightrag.utils")
    lightrag_utils.EmbeddingFunc = FakeEmbeddingFunc
    monkeypatch.setitem(sys.modules, "lightrag", lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.utils", lightrag_utils)
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "1.5.7")

    docs = build_case_documents([case_fixture()])
    with workspace_artifacts("lightrag") as artifacts:
        index_root = artifacts / "indexes"
        destination = asyncio.run(lightrag_backend.index_documents(docs, index_root))

        assert calls[0][0] == "construct"
        assert len([call for call in calls if call[0] == "insert"]) == len(docs)
        assert len([call for call in calls if call[0] == "initialize"]) == len(docs)
        assert len([call for call in calls if call[0] == "finalize"]) == len(docs)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["backend_version"] == "1.5.7"
        assert manifest["llm"] == "disabled-empty-entity-extraction"
        partitions = manifest["partitions"]
        assert len(partitions) == len(docs)
        assert {partition["role"] for partition in partitions} == {doc.role for doc in docs}
        assert all(len(partition["document_ids"]) == 1 for partition in partitions)

        calls.clear()
        same_destination = asyncio.run(lightrag_backend.index_documents(docs, index_root))
        assert same_destination == destination
        assert calls == []
