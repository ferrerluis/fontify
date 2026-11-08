"""Native vector authoring must not depend on raster preparation or tracing."""

import os
import subprocess
import sys

from conftest import ROOT


def test_vector_source_route_never_imports_raster_tools(tmp_path):
    code = r"""
import builtins
import importlib.util
import sys
from pathlib import Path

root, out = map(Path, sys.argv[1:])
original_import = builtins.__import__
def reject_raster(name, *args, **kwargs):
    if name.split('.')[0] in {'PIL', 'numpy', 'potrace', 'playwright'} or name == 'fontify.raster':
        raise AssertionError('Native vector path imported raster tooling: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = reject_raster
spec = importlib.util.spec_from_file_location('extract', root / 'scripts/prepare_recraft_sheet.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
project = module.prepare(root / 'examples/recraft-mellow/source/extraction-plan.json', out / 'vectors')
from fontify import build_font
from fontify.spacing import spacing_plan
plan = spacing_plan(project)
assert plan
manifest = build_font(project, out / 'font', draft=True)
assert manifest.is_file()
print('Vector extraction, spacing and compilation passed without raster imports.')
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT), str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
