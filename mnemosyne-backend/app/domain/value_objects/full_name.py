"""GitHub repository full-name value object."""

import re
from dataclasses import dataclass

_FULL_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+$")


class InvalidFullNameError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RepositoryFullName:
    """`owner/name` pair as GitHub renders it."""

    value: str

    def __post_init__(self) -> None:
        if not _FULL_NAME_RE.match(self.value):
            raise InvalidFullNameError(f"invalid repository full name: {self.value!r}")

    @property
    def owner(self) -> str:
        return self.value.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.value.split("/", 1)[1]

    def __str__(self) -> str:
        return self.value
