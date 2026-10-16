"""Límites determinísticos del complemento de historia clínica."""

import re

from .policy import _normalize


OUT_OF_SCOPE_REPLY = "Prefiero que hablemos de mi salud, doctor. ¿Seguimos con la consulta?"

# Claves estables: dos paráfrasis del mismo tema comparten el mismo dato del caso.
TOPICS = {
    "medicacion_habitual": ("medic", "pastill", "tratamiento", "tomando", "que toma", "controlar",
                             "que podrias tomar", "que podria tomar", "tomar para", "para el control"),
    "inicio_antecedentes": ("desde cuando", "que ano", "cuantos anos", "hace cuanto", "diagnostic", "cuando le dio",
                            "que edad", "edad tenia"),
    "hidratacion_habitual": ("agua", "vaso", "hidrat", "liquido"),
    "alimentacion_habitual": ("comida", "come", "comer", "dieta", "aliment", "sal "),
    "actividad_fisica": ("ejercicio", "actividad fisica", "camina", "deporte", "sedentar"),
    "tabaco": ("fuma", "tabaco", "cigarr"),
    "alcohol": ("alcohol", "cerveza", "licor", "vino"),
    "sueno_habitual": ("duerme", "dormir", "sueno", "descansa"),
    "ocupacion": ("trabaj", "ocupacion", "profesion"),
    "reaccion_diagnostico": ("reaccion", "se sintio", "te sentiste", "como lo tomo", "como se lo tomo",
                             "preocup", "asust", "miedo", "aceptar", "acepto"),
    "impacto_vida_diaria": ("actividades diarias", "vida diaria", "vida cotidiana", "actividades cotidianas",
                            "inconveniente", "dificulta", "le impide", "le limita", "le afecta",
                            "le ha afectado", "hacer sus actividades", "quehaceres", "independiente", "compras"),
}


def outside_clinical_scope(message: str) -> bool:
    text = _normalize(message)
    return bool(
        re.search(r"\d\s*[+*^=]\s*\d", message)
        or re.fullmatch(r"\s*[¿?(]*[\d\s.+*/^=()-]+[?)]*\s*", message)
        or re.search(r"\b(?:uno|dos|tres|cuatro|cinco) (?:mas|menos|por|entre) (?:uno|dos|tres|cuatro|cinco)\b", text)
        or re.search(r"\b(?:cuanto es|resuelve|calcula|multiplica|divide)\b.*\d", text)
        or any(term in text for term in (
            "pregunta matematica", "ecuacion", "raiz cuadrada", "capital de ",
            "presidente de ", "escribe un poema", "escribe un cuento", "escribe codigo",
            "programa en python", "ignora las instrucciones", "ignora tus instrucciones",
        ))
    )


def candidate_topics(question: str) -> list[str]:
    text = _normalize(question) + " "
    return [key for key, words in TOPICS.items() if any(word in text for word in words)]


def rapport_reply(question: str) -> str | None:
    """Conversación social breve: no fabrica ni guarda historia clínica."""
    text = _normalize(question)
    if candidate_topics(question) or len(text) > 160:
        return None
    if re.fullmatch(r"(?:hola|buenos dias|buenas tardes|buenas noches)(?: doctor| doctora)?", text):
        return "Hola, doctor. Lo escucho."
    if re.fullmatch(r"(?:muchas )?gracias(?: doctor| doctora)?", text):
        return "De nada, doctor."
    if re.search(r"\b(?:chistoso|chistosa|chiste|broma|jajaja|jeje)\b", text):
        if text.startswith("pero "):
            return "No entendí bien lo último, doctor. ¿Me lo puede repetir?"
        return "Je, je. Bueno, doctor, lo escucho."
    return None


def canonical_topic_exists(case: dict, topic: str) -> bool:
    """No sintetizar un campo que ya está en el caso, aunque aún no esté autorizado.

    Solo el código inspecciona on_request; no lo entrega completo al modelo.
    """
    items = [*case["public"].get("items", []), *case.get("on_request", [])]
    for item in items:
        category = item.get("category")
        text = _normalize(str(item.get("text", "")) + " " + str(item.get("label", "")))
        if topic == "medicacion_habitual" and category == "medicacion":
            return True
        if topic == "inicio_antecedentes":
            if category == "antecedente" and re.search(r"\b(?:hace|desde|anos|ano)\b", text):
                return True
        elif topic == "reaccion_diagnostico":
            if "alerg" not in text and any(word in text for word in TOPICS[topic]):
                return True
        elif topic != "medicacion_habitual" and any(word in text for word in TOPICS[topic]):
            return True
    return False
