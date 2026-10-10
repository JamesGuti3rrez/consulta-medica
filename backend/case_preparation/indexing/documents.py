from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


REQUIREMENT_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class IndexingError(ValueError):
    """Entrada incompleta, ambigua o no autorizada para indexar."""


@dataclass(frozen=True)
class IndexDocument:
    document_id: str
    role: str
    text: str
    requires: tuple[str, ...] = ()
    source_id: str = ""
    case_id: str | None = None
    category: str = ""
    specialty: str = ""
    title: str = ""


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def _protected_terms(case: dict[str, Any]) -> tuple[str, ...]:
    protected = case.get("protected")
    if not isinstance(protected, dict):
        raise IndexingError(f"{case.get('case_id', 'caso')}: falta protected para filtrar fugas.")

    terms: set[str] = set()
    diagnosis = protected.get("diagnosis", {})
    if isinstance(diagnosis, dict):
        diagnosis_values: list[Any] = [diagnosis.get("name")]
        synonyms = diagnosis.get("synonyms", [])
        if isinstance(synonyms, list):
            diagnosis_values.extend(synonyms)
        for value in diagnosis_values:
            if isinstance(value, str) and len(_normalize(value)) >= 3:
                terms.add(_normalize(value))

    for differential in protected.get("differentials", []):
        if isinstance(differential, dict):
            name = differential.get("name")
            if isinstance(name, str) and len(_normalize(name)) >= 3:
                terms.add(_normalize(name))
            synonyms = differential.get("synonyms", [])
            if isinstance(synonyms, list):
                terms.update(
                    _normalize(synonym)
                    for synonym in synonyms
                    if isinstance(synonym, str) and len(_normalize(synonym)) >= 3
                )

    def add_strings(value: Any) -> None:
        if isinstance(value, str):
            normalized = _normalize(value)
            if len(normalized) >= 8:
                terms.add(normalized)
        elif isinstance(value, dict):
            for nested in value.values():
                add_strings(nested)
        elif isinstance(value, list):
            for nested in value:
                add_strings(nested)

    # `evaluation` contains topics/evidence names that can legitimately coincide
    # with conversational evidence (e.g. hemograma, alergias). Treating those
    # labels as secret terms causes false positives. Diagnosis/differentials,
    # treatment reference and contraindications remain protected lexicon.
    for key in ("treatment_reference", "contraindications"):
        add_strings(protected.get(key))
    return tuple(sorted(terms, key=lambda term: (-len(term), term)))


def _contains_protected_term(text: str, terms: tuple[str, ...]) -> bool:
    normalized = f" {_normalize(text)} "
    return any(f" {term} " in normalized for term in terms)


def _data_text(item: dict[str, Any]) -> str:
    parts = [item.get("label", "")]
    if isinstance(item.get("text"), str):
        parts.append(item["text"])
    elif "value" in item:
        parts.append(str(item["value"]))
        if isinstance(item.get("unit"), str):
            parts.append(item["unit"])
    interpretation = item.get("interpretation")
    if isinstance(interpretation, str):
        parts.append(interpretation)
    return "\n".join(part for part in parts if part)


def _document(
    collection_id: str,
    role: str,
    evidence_id: str,
    text: str,
    requires: Iterable[str] = (),
    *,
    case_id: str | None = None,
    category: str = "",
    specialty: str = "",
    title: str = "",
) -> IndexDocument:
    return IndexDocument(
        document_id=f"{collection_id}:{role}:{evidence_id}",
        role=role,
        text=text,
        requires=tuple(requires),
        source_id=evidence_id,
        case_id=case_id,
        category=category,
        specialty=specialty,
        title=title,
    )


def _validate_role_policy(
    case_id: str,
    owner: Any,
    mode: Any,
    requires: Any,
) -> str:
    if (
        not isinstance(requires, list)
        or not requires
        or any(not isinstance(required, str) for required in requires)
        or len(set(requires)) != len(requires)
    ):
        raise IndexingError(f"{case_id}: requires debe ser una lista única de ids.")

    # El RAG valida la forma del contrato, pero no mantiene una segunda lista
    # semántica de permisos. La autorización real pertenece a engine/disclosure.
    valid_requires = all(REQUIREMENT_ID.fullmatch(required) for required in requires)

    if owner == "paciente":
        role = owner
        valid_mode = mode == "al_preguntar"
    elif owner == "medico_asistente":
        role = owner
        valid_mode = mode in {"al_preguntar", "al_examinar"}
    elif owner in {"laboratorio", "radiologia"}:
        role = owner
        valid_mode = mode == "al_solicitar_examen"
    elif owner == "especialista":
        role = owner
        valid_mode = mode in {"al_preguntar", "al_examinar", "al_solicitar_examen"}
    else:
        raise IndexingError(f"{case_id}: owner de reveal_policy no autorizado: {owner!r}.")

    if not valid_requires or not valid_mode:
        raise IndexingError(f"{case_id}: requires/mode no respeta el contrato de {role}.")
    return role


def build_case_documents(cases: Iterable[dict[str, Any]]) -> tuple[IndexDocument, ...]:
    """Construye documentos únicamente desde contenido conversacional autorizado.

    `protected` solo se usa para detectar fugas durante la preparación; nunca se
    convierte en un documento recuperable.
    """
    documents: list[IndexDocument] = []
    seen_case_ids: set[str] = set()

    for case in sorted(cases, key=lambda item: str(item.get("case_id", ""))):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise IndexingError("Cada caso debe tener case_id.")
        if case_id in seen_case_ids:
            raise IndexingError(f"{case_id}: case_id duplicado.")
        seen_case_ids.add(case_id)
        if case.get("status") != "curado":
            raise IndexingError(f"{case_id}: solo se indexan casos con status=curado.")

        specialty = case.get("specialty") if isinstance(case.get("specialty"), str) else ""
        title = case.get("title") if isinstance(case.get("title"), str) else ""
        protected_terms = _protected_terms(case)
        public = case.get("public")
        if not isinstance(public, dict) or not isinstance(public.get("patient"), dict):
            raise IndexingError(f"{case_id}: falta public.patient.")
        patient = public["patient"]
        age = patient.get("age_years")
        sex = patient.get("sex")
        if not isinstance(age, int) or not isinstance(sex, str):
            raise IndexingError(f"{case_id}: edad o sexo público inválido.")

        chief = public.get("chief_complaint")
        if not isinstance(chief, dict) or chief.get("category") != "motivo":
            raise IndexingError(f"{case_id}: chief_complaint debe estar clasificado como motivo.")
        evidence_id = chief.get("evidence_id")
        if not isinstance(evidence_id, str):
            raise IndexingError(f"{case_id}: el motivo requiere evidence_id.")
        public_text = f"Edad: {age}\nSexo: {sex}\n{_data_text(chief)}"
        if _contains_protected_term(public_text, protected_terms):
            raise IndexingError(f"{case_id}: evidencia pública contiene contenido de protected.")
        case_documents = [
            _document(
                case_id,
                "public",
                evidence_id,
                public_text,
                case_id=case_id,
                category="motivo",
                specialty=specialty,
                title=title,
            ),
        ]

        on_request = case.get("on_request")
        if not isinstance(on_request, list):
            raise IndexingError(f"{case_id}: on_request debe ser una lista.")
        for item in on_request:
            if not isinstance(item, dict):
                raise IndexingError(f"{case_id}: elemento on_request inválido.")
            policy = item.get("reveal_policy")
            if not isinstance(policy, dict):
                raise IndexingError(f"{case_id}: elemento on_request sin reveal_policy.")
            role = _validate_role_policy(
                case_id,
                policy.get("owner"),
                policy.get("mode"),
                policy.get("requires"),
            )
            requires = policy["requires"]

            evidence_id = item.get("evidence_id")
            if not isinstance(evidence_id, str):
                raise IndexingError(f"{case_id}: evidencia bajo solicitud requiere evidence_id.")
            text = _data_text(item)
            if not text.strip():
                raise IndexingError(f"{case_id}: evidencia bajo solicitud sin texto.")
            if _contains_protected_term(text, protected_terms):
                raise IndexingError(f"{case_id}: evidencia bajo solicitud contiene contenido de protected.")
            category = item.get("category") if isinstance(item.get("category"), str) else ""
            case_documents.append(
                _document(
                    case_id,
                    role,
                    evidence_id,
                    text,
                    requires,
                    case_id=case_id,
                    category=category,
                    specialty=specialty,
                    title=title,
                )
            )

        document_ids = [document.document_id for document in case_documents]
        if len(document_ids) != len(set(document_ids)):
            raise IndexingError(f"{case_id}: evidence_id duplicado dentro del mismo rol.")
        source_ids = [document.source_id for document in case_documents]
        if len(source_ids) != len(set(source_ids)):
            raise IndexingError(f"{case_id}: evidence_id duplicado en el caso.")
        documents.extend(case_documents)
    return tuple(sorted(documents, key=lambda item: item.document_id))


def load_approved_knowledge_documents(
    knowledge_dir: Path,
    protected_cases: Iterable[dict[str, Any]] = (),
) -> tuple[IndexDocument, ...]:
    """Carga únicamente Markdown aprobado de un registro explícito; no descarga fuentes."""
    registry_path = knowledge_dir / "registry.json"
    if not registry_path.exists():
        return ()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IndexingError(f"No se pudo leer el registro de conocimiento: {error}") from error
    entries = registry.get("sources") if isinstance(registry, dict) else None
    if not isinstance(entries, list):
        raise IndexingError("data/knowledge/registry.json debe contener una lista 'sources'.")

    protected_terms = tuple(
        sorted(
            {term for case in protected_cases for term in _protected_terms(case)},
            key=lambda term: (-len(term), term),
        )
    )
    documents: list[IndexDocument] = []
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise IndexingError("Cada fuente de conocimiento debe ser un objeto.")
        if entry.get("approved") is not True:
            continue
        source_id = entry.get("id")
        relative_path = entry.get("path")
        license_name = entry.get("license")
        reviewer = entry.get("reviewed_by")
        scope = entry.get("scope")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (source_id, relative_path, license_name, reviewer, scope)
        ):
            raise IndexingError("Una fuente aprobada requiere id, path, license, reviewed_by y scope.")
        assert isinstance(source_id, str)
        assert isinstance(relative_path, str)
        assert isinstance(license_name, str)
        assert isinstance(reviewer, str)
        assert isinstance(scope, str)
        if source_id in seen_ids:
            raise IndexingError(f"Fuente de conocimiento duplicada: {source_id}.")
        seen_ids.add(source_id)
        if scope not in {"conversation", "evaluation"}:
            raise IndexingError(f"{source_id}: scope debe ser conversation o evaluation.")
        relative = Path(relative_path)
        source_path = (knowledge_dir / relative).resolve()
        if (
            relative.is_absolute()
            or source_path.parent != (knowledge_dir / "approved").resolve()
            or source_path.suffix.lower() != ".md"
        ):
            raise IndexingError(f"{source_id}: path debe apuntar a un Markdown directo de approved/.")
        try:
            text = source_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise IndexingError(f"{source_id}: no se pudo leer la fuente aprobada: {error}") from error
        if not text:
            raise IndexingError(f"{source_id}: la fuente aprobada está vacía.")
        if _contains_protected_term(text, protected_terms):
            raise IndexingError(f"{source_id}: la fuente contiene contenido de protected de un caso.")
        metadata = (
            f"Fuente aprobada: {source_id}\nLicencia: {license_name}\n"
            f"Revisor: {reviewer}\nAlcance: {scope}"
        )
        documents.append(
            _document(
                f"knowledge-{source_id}",
                f"knowledge:{scope}",
                source_id,
                f"{metadata}\n\n{text}",
                case_id=None,
                category="knowledge",
            )
        )
    return tuple(sorted(documents, key=lambda item: item.document_id))


def documents_fingerprint(documents: Iterable[IndexDocument]) -> str:
    serialized = [
        asdict(document)
        for document in sorted(documents, key=lambda item: item.document_id)
    ]
    payload = json.dumps(serialized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
