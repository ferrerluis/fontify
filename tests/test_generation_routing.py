"""Guard the agent skill contract, not an automatic visual-quality classifier.

These checks keep the entrypoint and linked guidance aligned. Existing mocked
provider tests separately exercise n=1, model choice and the paid-call gate.
"""

import importlib.util
import re

from conftest import ROOT


def text(path):
    return " ".join((ROOT / path).read_text().split())


def test_generation_routing_entrypoints_link_the_reference():
    for path in (
        "SKILL.md",
        "README.md",
        "references/recraft.md",
        "docs/architecture.md",
    ):
        content = (ROOT / path).read_text()
        links = re.findall(r"\]\(([^)]*generation-routing\.md)\)", content)
        assert links, path
        for link in links:
            assert ((ROOT / path).parent / link).resolve().is_file(), (path, link)
    routing = ROOT / "references/generation-routing.md"
    for link in re.findall(r"\]\(([^)]+)\)", routing.read_text()):
        assert (routing.parent / link).is_file(), link


def test_generation_routing_pilot_precedes_option_expansion():
    skill = text("SKILL.md")
    guide = text("references/generation-routing.md")
    assert "Inspect the references and requested letterform qualities" in skill
    assert "one pilot iteration" in skill and "one output (`n=1`)" in skill
    assert "even when several design options were requested" in skill
    assert "after choosing the vector route, not to every new concept" in skill
    assert "Inspect the actual returned artwork" in guide
    assert "remaining requested options through the vector route" in guide
    assert "do not ask again for calls already covered" in guide
    assert "pilot gate, not a lifetime cap" in guide
    assert "For a new typeface concept, use Recraft Vector Pro" not in skill


def test_generation_routing_systemic_failure_is_not_a_retry_loop():
    guide = text("references/generation-routing.md")
    skill = text("SKILL.md")
    assert "If systemically off, stop the vector route" in guide
    assert "Do not run more vector prompts, switch vector models" in guide
    assert "local defects is not automatically a systemic mismatch" in guide
    assert "not visual evidence of model unsuitability" in guide
    assert "Check an uncertain request's outcome" in guide
    assert "do not rasterize the failed SVG" in guide
    assert "does not authorize repeated vector attempts after systemic failure" in skill


def test_generation_routing_selection_and_authorization_stay_explicit():
    guide = text("references/generation-routing.md")
    assert '"native vector only" or "no raster" restriction is a boundary' in guide
    assert "ask before relaxing that restriction" in guide
    assert "The single trial is not permission to spend" in guide
    assert "Do not spend beyond an existing limit" in guide
    assert "Unselected concepts stay unselected" in guide
    assert (
        "wait for their selection before cleanup, tracing or font construction" in guide
    )
    assert "Do not regenerate or replace existing options" in guide


def test_generation_routing_disclosure_preserves_truthful_provenance():
    guide = text("references/generation-routing.md")
    assert (
        "Always retain the actual source method, provider/model, exact prompt" in guide
    )
    assert "only if the user specifically requested vector generation" in guide
    assert "answer direct questions truthfully" in guide
    assert "never label traced raster artwork as native vector generation" in guide
    assert "not an automatic style classifier" in guide
    for path in ("SKILL.md", "README.md"):
        entrypoint = text(path)
        assert "specifically requested vector generation" in entrypoint
        assert "State whether generation" not in entrypoint


def test_generation_routing_evidence_digest_binds_policy_files(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "fontify_acceptance", ROOT / "scripts/run_acceptance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    policy_files = (
        "SKILL.md",
        "README.md",
        "references/generation-routing.md",
        "references/recraft.md",
        "docs/architecture.md",
    )
    for name in (
        *policy_files,
        "pyproject.toml",
        "requirements.lock",
        "scripts/run_acceptance.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("initial\n")
    previous = module.source_digest()
    for name in policy_files:
        (tmp_path / name).write_text("changed policy\n")
        current = module.source_digest()
        assert current != previous, name
        previous = current
