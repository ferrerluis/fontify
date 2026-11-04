import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project_dir(tmp_path):
    dest = tmp_path / "project"
    shutil.copytree(ROOT / "examples/offline", dest)
    return dest


def edit_project(root, **updates):
    path = root / "fontify.json"
    d = json.loads(path.read_text())
    d.update(updates)
    path.write_text(json.dumps(d))
    return path


@pytest.fixture(scope="session")
def release(tmp_path_factory):
    from fontify import build_font

    root = tmp_path_factory.mktemp("release")
    return build_font(ROOT / "examples/offline/fontify.json", root)
