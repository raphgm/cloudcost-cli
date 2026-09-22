from pathlib import Path


def test_release_workflow_uploads_to_pypi() -> None:
    workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-release.yml"
    content = workflow.read_text()

    assert "python -m build" in content
    assert "pypa/gh-action-pypi-publish" in content
    assert "twine upload" in content or "pypa/gh-action-pypi-publish" in content
