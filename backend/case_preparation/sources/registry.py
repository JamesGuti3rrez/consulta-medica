from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceFile:
    name: str
    url: str
    sha256: str
    description: str


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    url: str
    version: str
    license: str
    files: tuple[SourceFile, ...]
    obtained_by: str


SOURCE_DEFINITIONS: dict[str, SourceDefinition] = {
    "medqa": SourceDefinition(
        name="MedQA",
        url="https://github.com/jind11/MedQA",
        # Commit fijo del repositorio oficial: la rama master podría cambiar y romper la huella.
        version="27b02f66aac217933c9648a06f82e9f720377925",
        license="MIT",
        files=(
            SourceFile(
                name="MedQA-27b02f66.zip",
                url="https://github.com/jind11/MedQA/archive/27b02f66aac217933c9648a06f82e9f720377925.zip",
                sha256="8cba6bdd54810ff8773a2f29129117c7142d135a5d0a0698ed929c267418fa15",
                description="Repositorio oficial en el commit 27b02f6: código, README y LICENSE (MIT). No contiene las preguntas.",
            ),
            SourceFile(
                name="data_clean.zip",
                url="https://drive.usercontent.google.com/download?id=1ImYUSLk9JbgHXOemfvyiDiirluZHPeQw&export=download&confirm=t",
                sha256="1c2ca8130b3d86d9a99a432ab9bef14f3bb9807bef20facd9ac86ba36960f629",
                description="Preguntas y libros de texto enlazados desde la sección Data del README oficial (Google Drive).",
            ),
        ),
        obtained_by="James Gutiérrez",
    )
}
