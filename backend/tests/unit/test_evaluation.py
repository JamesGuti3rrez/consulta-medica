from server.engine.evaluation import ClinicalEvaluationEngine


class CaseRepository:
    def get_protected(self, case_id):
        return {
            "evaluation": {
                "key_questions": [
                    {
                        "id": "kq1",
                        "topic": "Contenido clínico protegido",
                        "evidence_ids": ["MED-900.anamnesis.alergias"],
                        "weight": 5,
                        "error_if_missing": "negligencia",
                    },
                    {
                        "id": "kq2",
                        "topic": "Otro contenido protegido",
                        "evidence_ids": ["MED-900.anamnesis.inicio_dolor"],
                        "weight": 3,
                        "error_if_missing": "anamnesis_incompleta",
                    },
                ]
            }
        }


def test_evaluation_scores_requested_evidence_and_returns_only_aggregated_errors():
    engine = ClinicalEvaluationEngine(CaseRepository())

    report = engine.evaluate(
        case_id="MED-900",
        evidence_ids=["MED-900.anamnesis.alergias"],
    )

    assert report == {
        "score": 62.5,
        "earned_weight": 5,
        "total_weight": 8,
        "completed_questions": 1,
        "total_questions": 2,
        "errors": {
            "negligencia": 0,
            "anamnesis_incompleta": 1,
            "razonamiento_clinico": 0,
        },
    }
    assert "Contenido clínico protegido" not in str(report)


def test_evidence_given_at_the_start_does_not_count_as_an_omission():
    # kq1 solo pide el motivo de consulta, que el doctor lee al presentar el caso:
    # el estudiante no puede pedirlo, así que no se puntúa ni se cuenta como error.
    engine = ClinicalEvaluationEngine(CaseRepository())

    report = engine.evaluate(
        case_id="MED-900",
        evidence_ids=["MED-900.anamnesis.inicio_dolor"],
        initial_evidence_ids=["MED-900.anamnesis.alergias"],
    )

    assert report["score"] == 100.0
    assert report["completed_questions"] == 1
    assert report["total_questions"] == 1
    assert sum(report["errors"].values()) == 0
