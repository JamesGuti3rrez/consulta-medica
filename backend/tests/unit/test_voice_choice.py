"""Elección de la voz neuronal de cada personaje del simulador."""

import pytest

from server.voice.tts import VOICES, choose_voice


def test_patient_voice_follows_patient_sex():
    assert choose_voice("patient", "masculino") == "es-PE-AlexNeural"
    assert choose_voice("patient", "femenino") == "es-PE-CamilaNeural"


def test_patient_without_known_sex_gets_a_valid_voice():
    assert choose_voice("patient", None) in VOICES
    assert choose_voice("patient", "otro") in VOICES


def test_doctor_never_shares_the_voice_of_the_patient():
    for sex in ("masculino", "femenino", None):
        assert choose_voice("doctor", sex) != choose_voice("patient", sex)


def test_each_service_has_its_own_voice():
    services = {choose_voice(speaker, None) for speaker in ("laboratorio", "radiologia", "especialista")}
    assert len(services) == 3


def test_unknown_speaker_is_rejected():
    with pytest.raises(ValueError):
        choose_voice("student", None)
