import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")


def test_local_markdown_links_resolve() -> None:
    documents = (ROOT / "README.md", *(ROOT / "docs").rglob("*.md"))
    missing: list[str] = []
    for document in documents:
        for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            path = target.split("#", 1)[0]
            if not path or "://" in path or path.startswith(("mailto:", "#")):
                continue
            resolved = (document.parent / path).resolve()
            if not resolved.exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing, "Missing local documentation links:\n" + "\n".join(missing)


def test_release_artifacts_exist_and_stale_claims_are_absent() -> None:
    required = (
        "docs/diagrams/system-context.mmd",
        "docs/diagrams/system-context.svg",
        "docs/demo-script.md",
        "docs/release-audit.md",
        "docs/release-checklist.md",
        "evals/datasets/grounded-answers-v1.json",
        "evals/results/grounded-answers-v1.json",
    )
    assert all((ROOT / path).is_file() for path in required)

    inspected = (
        ROOT / "README.md",
        ROOT / "docs/requirements-traceability.md",
        ROOT / "src/orysys/bootstrap.py",
    )
    contents = "\n".join(path.read_text(encoding="utf-8") for path in inspected)
    assert "All rows currently remain **Planned**" not in contents
    assert "Live adapters have not been implemented" not in contents
