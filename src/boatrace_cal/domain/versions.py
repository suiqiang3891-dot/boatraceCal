"""Version provenance for reproducible analysis artifacts."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactVersions:
    """Versions needed to reproduce a prediction or analysis artifact."""

    data: str
    feature: str
    model: str
    strategy: str

    def __post_init__(self) -> None:
        for name in ("data", "feature", "model", "strategy"):
            value = getattr(self, name)
            if type(value) is not str:
                raise ValueError(f"{name} version must be a string")
            value = value.strip()
            if not value:
                raise ValueError(f"{name} version must not be empty")
            object.__setattr__(self, name, value)
