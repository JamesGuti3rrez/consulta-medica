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
        version="master",
        license="MIT",
        files=(
            SourceFile(
                name="MedQA-master.zip",
                url="https://github.com/jind11/MedQA/archive/refs/heads/master.zip",
                sha256="1b7af07b4de67376d0e5fb4a376a7bcc605678aa32a26f0409fcc7d0d8c4b60c",
                description="Repositorio oficial: código, README y LICENSE (MIT). No contiene las preguntas.",
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
