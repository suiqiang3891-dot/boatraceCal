import pytest

from boatrace_cal.domain.versions import ArtifactVersions


def test_artifact_versions_accepts_non_empty_values() -> None:
    versions = ArtifactVersions(
        data="data-v1",
        feature="feature-v1",
        model="model-v1",
        strategy="strategy-v1",
    )

    assert versions.data == "data-v1"
    assert versions.feature == "feature-v1"
    assert versions.model == "model-v1"
    assert versions.strategy == "strategy-v1"


def test_artifact_versions_strips_surrounding_whitespace() -> None:
    versions = ArtifactVersions(
        data=" data-v1 ",
        feature="\tfeature-v1",
        model="model-v1\n",
        strategy=" strategy-v1 ",
    )

    assert versions == ArtifactVersions(
        data="data-v1",
        feature="feature-v1",
        model="model-v1",
        strategy="strategy-v1",
    )


@pytest.mark.parametrize("invalid_value", ["", "   ", "\t\n"])
@pytest.mark.parametrize("field", ["data", "feature", "model", "strategy"])
def test_artifact_versions_rejects_empty_values(field: str, invalid_value: str) -> None:
    values = {
        "data": "data-v1",
        "feature": "feature-v1",
        "model": "model-v1",
        "strategy": "strategy-v1",
    }
    values[field] = invalid_value

    with pytest.raises(ValueError):
        ArtifactVersions(**values)
