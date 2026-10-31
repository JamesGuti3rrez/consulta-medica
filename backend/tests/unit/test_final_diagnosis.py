"""HU-006: el diagnóstico final es obligatorio y su texto se valida y normaliza antes de registrarlo."""

import pytest

from server.domain.final_diagnosis import MAX_LENGTH, InvalidDiagnosis, normalize_final_diagnosis


@pytest.mark.parametrize("text, expected", [
    ("Apendicitis aguda", "Apendicitis aguda"),
    ("  Apendicitis   aguda  ", "Apendicitis aguda"),
    ("Neumonía adquirida en la comunidad", "Neumonía adquirida en la comunidad"),
    ("IAM", "IAM"),
    ("Diabetes mellitus tipo 2", "Diabetes mellitus tipo 2"),
    ("Apendicitis\taguda", "Apendicitis aguda"),
    ("Apendicitis aguda.\r\nJustificación: dolor en fosa ilíaca derecha.",
     "Apendicitis aguda.\nJustificación: dolor en fosa ilíaca derecha."),
    ("Apendicitis aguda\n\n\n\nPor el dolor migratorio", "Apendicitis aguda\n\nPor el dolor migratorio"),
    ("  línea con espacios  \n  otra  ", "línea con espacios\notra"),
    # Forma descompuesta (e + tilde combinada) a la forma compuesta.
    ("Neumonía", "Neumonía"),
    ("Hb 9.8 g/dL, anemia ferropénica (probable)", "Hb 9.8 g/dL, anemia ferropénica (probable)"),
])
def test_valid_text_is_normalized(text, expected):
    assert normalize_final_diagnosis(text) == expected


def test_text_at_the_maximum_length_is_accepted():
    text = "a" * MAX_LENGTH
    assert normalize_final_diagnosis(text) == text


@pytest.mark.parametrize("text", [None, "", "   ", "\n\t \n"])
def test_missing_diagnosis_is_rejected(text):
    with pytest.raises(InvalidDiagnosis) as error:
        normalize_final_diagnosis(text)
    assert error.value.message == "Escribe tu diagnóstico final antes de cerrar la consulta."


@pytest.mark.parametrize("text", ["ab", "a b", "12345", "...", "1 2 3 4", "?!", "x1"])
def test_fewer_than_three_letters_is_rejected(text):
    with pytest.raises(InvalidDiagnosis) as error:
        normalize_final_diagnosis(text)
    assert error.value.message == "El diagnóstico debe tener al menos 3 letras."


def test_text_over_the_maximum_is_rejected():
    with pytest.raises(InvalidDiagnosis) as error:
        normalize_final_diagnosis("a" * (MAX_LENGTH + 1))
    assert error.value.message == f"El diagnóstico no puede superar los {MAX_LENGTH} caracteres."


def test_the_maximum_counts_after_normalizing():
    # Los espacios sobrantes no cuentan: tras normalizar queda dentro del límite.
    assert len(normalize_final_diagnosis("  " + "a" * MAX_LENGTH + "  ")) == MAX_LENGTH


@pytest.mark.parametrize("text", ["Apendicitis\x00aguda", "Apendicitis\x07", "Apendi\x1bcitis", "Apendicitis\x7f",
                                  "Apendicitis​\x0c"])
def test_control_characters_are_rejected(text):
    with pytest.raises(InvalidDiagnosis) as error:
        normalize_final_diagnosis(text)
    assert error.value.message == "El diagnóstico tiene caracteres no permitidos."


@pytest.mark.parametrize("text", ["<script>alert(1)</script> apendicitis", "Apendicitis <b>aguda</b>", "Dolor > 3 días"])
def test_markup_signs_are_rejected(text):
    with pytest.raises(InvalidDiagnosis) as error:
        normalize_final_diagnosis(text)
    assert error.value.message == "El diagnóstico no puede contener los signos < ni >."


def test_non_text_is_rejected_as_missing():
    with pytest.raises(InvalidDiagnosis):
        normalize_final_diagnosis(12345)
