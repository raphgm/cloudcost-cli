from pathlib import Path


def test_project_metadata_is_pypi_ready() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject.read_text()

    assert 'name = "cloudcost-finops"' in content
    assert 'readme = "README.md"' in content
    assert 'authors = [' in content
    assert 'Homepage' in content or '[project.urls]' in content
    assert 'cloudcost = "cloudcost.cli:app"' in content
