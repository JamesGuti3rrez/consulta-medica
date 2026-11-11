from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auditar_casos import SPECIALTIES, allocate_strata


def test_stratified_sample_is_deterministic_for_same_seed():
    groups = {
        "medicina_interna": [{"case_id": "MED-001"}, {"case_id": "MED-002"}],
        "pediatria": [{"case_id": "PED-001"}, {"case_id": "PED-002"}],
    }

    first = allocate_strata(groups, sample_size=2, seed=7)
    second = allocate_strata(groups, sample_size=2, seed=7)

    assert [row["case_id"] for row in first] == [row["case_id"] for row in second]


def test_stratified_sample_represents_each_available_specialty_when_possible():
    groups = {
        "medicina_interna": [{"case_id": "MED-001"}, {"case_id": "MED-002"}],
        "pediatria": [{"case_id": "PED-001"}],
        "emergencias": [{"case_id": "EME-001"}],
    }

    selected = allocate_strata(groups, sample_size=3, seed=13)

    assert {row["case_id"][:3] for row in selected} == {"MED", "PED", "EME"}


def test_stratified_sample_never_exceeds_population():
    groups = {"medicina_interna": [{"case_id": "MED-001"}]}

    selected = allocate_strata(groups, sample_size=43, seed=20261106)

    assert len(selected) == 1


def test_minimum_stratum_representation_does_not_exceed_requested_size():
    groups = {
        "medicina_interna": [{"case_id": "MED-001"}, {"case_id": "MED-002"}],
        "pediatria": [{"case_id": "PED-001"}],
        "emergencias": [
            {"case_id": f"EME-{number:03d}"} for number in range(1, 11)
        ],
    }

    selected = allocate_strata(groups, sample_size=3, seed=19)

    assert len(selected) == 3
    assert {row["case_id"][:3] for row in selected} == {"MED", "PED", "EME"}


def test_specialty_strata_match_case_schema_vocabulary():
    assert SPECIALTIES == (
        "medicina_interna",
        "pediatria",
        "cirugia_general",
        "ginecologia_obstetricia",
        "emergencias",
    )
