from server.domain import Intent
from server.engine.safety import ClinicalSafetyEngine


class CaseRepository:
    def __init__(self, *, allergies=None, contraindications=None):
        self.public = {
            "allergies_recorded": bool(allergies),
            "allergies": allergies or [],
        }
        self.protected = {"contraindications": contraindications or []}

    def get_conversation_case(self, case_id):
        return {"public": self.public}

    def get_protected(self, case_id):
        return self.protected


def test_flags_registered_allergy_and_case_contraindication_without_exposing_details():
    repository = CaseRepository(
        allergies=["penicilina"],
        contraindications=[
            {
                "drug_or_class": "Tetraciclinas (incluida la doxiciclina)",
                "reason": "Detalle protegido",
                "evidence_id": "MED-008.antecedente.alergias",
            }
        ],
    )
    engine = ClinicalSafetyEngine(repository)

    alerts = engine.evaluate_treatment(
        case_id="MED-008",
        message="Prescribo penicilina y doxiciclina.",
        intent=Intent.PROPOSE_TREATMENT,
    )

    assert [alert["code"] for alert in alerts] == ["known_allergy", "case_contraindication"]
    assert all("Detalle protegido" not in alert["message"] for alert in alerts)
    assert all("doxiciclina" not in alert["message"] for alert in alerts)


def test_ignores_negated_or_non_treatment_mentions():
    repository = CaseRepository(
        contraindications=[
            {
                "drug_or_class": "Antiagregantes, anticoagulantes y fibrinolíticos (aspirina, heparina, alteplasa)",
                "reason": "Detalle protegido",
                "evidence_id": "EME-103.imagen.angiotomografia_torax",
            }
        ]
    )
    engine = ClinicalSafetyEngine(repository)

    assert engine.evaluate_treatment(
        case_id="EME-103",
        message="No le doy aspirina.",
        intent=Intent.PROPOSE_TREATMENT,
    ) == []
    assert engine.evaluate_treatment(
        case_id="EME-103",
        message="¿Tomó aspirina?",
        intent=Intent.ASK_PATIENT,
    ) == []
