"""Small synthetic fixtures exercise the optional authoring path, never the compiler."""

import copy
import hashlib
import json
import struct
import subprocess
import sys
import zlib

import pytest

from fontify.model import FontifyError
from fontify.raster import trace_sheet

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")
pytest.importorskip("potrace")


def source_plan(tmp_path, mask=None):
    if mask is None:
        mask = np.zeros((32, 32), dtype=bool)
        mask[9:24, 11:14] = True  # Stem, detached dot, and texture are all ink.
        mask[4:6, 11:14] = True
    image = tmp_path / "sheet.png"
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).save(image)
    base = {
        "schema": 1,
        "family": "Raster Test",
        "style": "Regular",
        "version": "1.000",
        "ascender": 900,
        "descender": -200,
        "cap_height": 700,
        "x_height": 500,
        "svg_baseline": 800,
        "required_characters": "i ",
        "samples": ["i i"],
        "glyphs": [],
    }
    (tmp_path / "fontify-base.json").write_text(json.dumps(base))
    plan = {
        "schema": 1,
        "image": image.name,
        "source_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "image_size": [32, 32],
        "threshold": 128,
        "cap_height": 700,
        "svg_baseline": 800,
        "sidebearing": 50,
        "rows": [{"baseline": 24, "pixels_per_cap": 20}],
        "trace": {
            "turdsize": 0,
            "alphamax": 0.7,
            "opticurve": False,
            "opttolerance": 0.05,
        },
        "glyphs": [{"name": "i", "unicode": "U+0069", "box": [0, 0, 32, 32], "row": 0}],
        "preparation": {"schema": 1},
    }
    return plan, image


def run_plan(tmp_path, plan, out="candidate"):
    path = tmp_path / f"{out}-plan.json"
    path.write_text(json.dumps(plan, sort_keys=True))
    project = trace_sheet(path, tmp_path / out)
    return project, json.loads((project.parent / "trace-record.json").read_text())


def test_raster_guides_labels_noise_and_explicit_preserve(tmp_path):
    mask = np.zeros((32, 32), dtype=bool)
    mask[9:24, 11:14] = True
    mask[4:6, 11:14] = True
    mask[14, 2:29] = True  # Guide crosses the stem, protected explicitly below.
    mask[1:3, 1:3] = True  # Printed label.
    mask[6, 24] = True  # Reviewed noise, not merely anything small.
    mask[25, 12] = True  # Intentional texture, just one pixel.
    plan, image = source_plan(tmp_path, mask)
    original = image.read_bytes()
    plan["preparation"].update(
        {
            "masks": [
                {
                    "kind": "guide",
                    "box": [0, 14, 32, 15],
                    "reason": "Template baseline",
                },
                {"kind": "label", "box": [0, 0, 4, 4], "reason": "Printed cell label"},
            ],
            "protect_boxes": [
                {"box": [11, 9, 14, 24], "reason": "Stem crosses the guide"}
            ],
            "components": {
                "small_area_max": 8,
                "glyphs": {
                    "i": {
                        "remove": [
                            {"point": [24, 6], "reason": "Verified scan speck"},
                            {"point": [12, 25], "reason": "Deliberate conflict test"},
                        ],
                        "preserve": [
                            {"point": [11, 4], "reason": "Detached dot"},
                            {
                                "point": [12, 25],
                                "reason": "Intentional texture; preserve wins",
                            },
                        ],
                    }
                },
            },
        }
    )
    project, record = run_plan(tmp_path, plan)
    g = record["glyphs"][0]
    cleaned = (
        np.asarray(Image.open(project.parent / g["artifacts"]["cleaned"]["path"])) == 0
    )
    expected = mask.copy()
    expected[14, :] = False
    expected[14, 11:14] = True
    expected[0:4, 0:4] = False
    expected[6, 24] = False
    assert np.array_equal(cleaned, expected)
    assert g["mask_removed_pixels"] == 28
    assert g["protected_mask_pixels"] == 3
    assert sum(c["decision"] == "remove_explicit" for c in g["components"]) == 1
    assert sum(c["decision"] == "preserve_explicit" for c in g["components"]) == 2
    assert image.read_bytes() == original
    assert (project.parent / record["source_original"]).read_bytes() == original
    for artifact in g["artifacts"].values():
        assert (
            hashlib.sha256((project.parent / artifact["path"]).read_bytes()).hexdigest()
            == artifact["sha256"]
        )
    assert record["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert (
        record["plan_sha256"]
        == hashlib.sha256(
            (project.parent / "source/trace-plan.json").read_bytes()
        ).hexdigest()
    )
    assert (
        record["base_sha256"]
        == hashlib.sha256(
            (project.parent / "source/fontify-base.json").read_bytes()
        ).hexdigest()
    )
    assert record["status"] == "review_required"


def test_raster_small_detached_ink_is_never_implicitly_deleted(tmp_path):
    mask = np.zeros((32, 32), dtype=bool)
    mask[9:24, 11:14] = True
    mask[4, 11] = True  # Dot.
    mask[3, 14:16] = True  # Accent.
    mask[26, 15] = True  # Punctuation-like mark.
    mask[13, 18] = True  # Texture.
    plan, _ = source_plan(tmp_path, mask)
    _, record = run_plan(tmp_path, plan)
    components = record["glyphs"][0]["components"]
    assert len(components) == 5
    assert all(c["decision"] == "preserve_default" for c in components)
    assert sum(c["classification"] == "small_candidate" for c in components) == 4


@pytest.mark.parametrize("filter_name", ["nearest", "bilinear", "bicubic", "lanczos"])
def test_raster_low_resolution_counter_and_padding_invariance(tmp_path, filter_name):
    mask = np.zeros((32, 32), dtype=bool)
    mask[7:24, 9:17] = True
    mask[9:22, 11:15] = False  # Counter in a low-resolution ring.
    plan, _ = source_plan(tmp_path, mask)
    plan["preparation"]["resample"] = {"scale": 4, "filter": filter_name}
    plan["glyphs"][0]["box"] = [9, 7, 17, 24]
    first, one = run_plan(tmp_path, plan, "tight")
    padded_plan = copy.deepcopy(plan)
    padded_plan["glyphs"][0]["box"] = [2, 1, 28, 31]
    second, two = run_plan(tmp_path, padded_plan, "padded")
    assert (first.parent / "glyphs/i.svg").read_bytes() == (
        second.parent / "glyphs/i.svg"
    ).read_bytes()
    assert first.read_bytes() == second.read_bytes()
    a, b = one["glyphs"][0], two["glyphs"][0]
    assert a["advance"] == b["advance"] == 380
    assert a["trace_ink_source_box"] == b["trace_ink_source_box"] == [9, 7, 17, 24]
    assert a["resampled_pixel_size_source"] == 0.25
    assert a["trace_scale"] == 8.75  # Uniform scale divided by interpolation factor.
    assert (
        a["artifacts"]["resampled"]["sha256"] == b["artifacts"]["resampled"]["sha256"]
    )
    sampled = np.asarray(Image.open(first.parent / a["artifacts"]["resampled"]["path"]))
    # Map the center of the counter from original sheet coordinates to this mask.
    ox, oy = a["resampled_origin_source"]
    assert sampled[int((16 - oy) * 4), int((13 - ox) * 4)] == 255
    assert one["resample"] == {"scale": 4, "filter": filter_name, "threshold": 128}


def test_raster_preparation_deterministic_and_no_overwrite(tmp_path):
    plan, _ = source_plan(tmp_path)
    first, _ = run_plan(tmp_path, plan, "first")
    second, _ = run_plan(tmp_path, plan, "second")
    for file in first.parent.rglob("*"):
        if file.is_file():
            assert (
                file.read_bytes()
                == (second.parent / file.relative_to(first.parent)).read_bytes()
            )
    snapshot = (first.parent / "trace-record.json").read_bytes()
    with pytest.raises(FontifyError, match="already exists"):
        trace_sheet(tmp_path / "first-plan.json", first.parent)
    assert (first.parent / "trace-record.json").read_bytes() == snapshot


@pytest.mark.parametrize(
    "change, message",
    [
        ({"schema": True}, "schema"),
        ({"preparation": None}, "expected an object"),
        ({"preparation": {"schema": 2}}, "preparation.schema"),
        ({"preparation": {"schema": 1, "mystery": True}}, "unknown fields"),
        ({"preparation": {"schema": 1, "resample": {"scale": 0}}}, "resample.scale"),
        (
            {"preparation": {"schema": 1, "resample": {"filter": "ai-upscaler"}}},
            "resample.filter",
        ),
        (
            {"preparation": {"schema": 1, "components": {"connectivity": 6}}},
            "connectivity",
        ),
        (
            {"preparation": {"schema": 1, "components": {"glyphs": {"unknown": {}}}}},
            "declared glyph names",
        ),
        (
            {
                "preparation": {
                    "schema": 1,
                    "masks": [
                        {"box": [0, 0, 33, 2], "kind": "guide", "reason": "Bad bounds"}
                    ],
                }
            },
            "crop box",
        ),
        (
            {
                "preparation": {
                    "schema": 1,
                    "masks": [
                        {"box": [0, 0, 2, 2], "kind": "guess", "reason": "Bad kind"}
                    ],
                }
            },
            "mask kind",
        ),
        ({"trace": {"turdsize": 2}}, "turdsize=0"),
        ({"image": "../outside.png"}, "stay inside"),
        (
            {
                "glyphs": [
                    {
                        "name": "../../escape",
                        "unicode": "U+0069",
                        "box": [0, 0, 32, 32],
                        "row": 0,
                    }
                ]
            },
            "glyph name",
        ),
    ],
)
def test_raster_malformed_plans_publish_nothing(tmp_path, change, message):
    plan, _ = source_plan(tmp_path)
    plan.update(change)
    with pytest.raises(FontifyError, match=message):
        run_plan(tmp_path, plan)
    assert not (tmp_path / "candidate").exists()


def test_raster_selector_on_background_and_empty_result_fail_closed(tmp_path):
    plan, _ = source_plan(tmp_path)
    plan["preparation"]["components"] = {
        "glyphs": {"i": {"remove": [{"point": [0, 0], "reason": "Mistake"}]}}
    }
    with pytest.raises(FontifyError, match="not retained foreground"):
        run_plan(tmp_path, plan)
    plan["preparation"] = {
        "schema": 1,
        "masks": [{"box": [0, 0, 32, 32], "kind": "label", "reason": "Mistake"}],
    }
    with pytest.raises(FontifyError, match="empty glyph"):
        run_plan(tmp_path, plan)
    assert not (tmp_path / "candidate").exists()


def test_raster_source_hash_dimensions_and_native_vector_rejection(
    tmp_path, monkeypatch
):
    plan, image = source_plan(tmp_path)
    image.write_bytes(image.read_bytes() + b"changed")
    with pytest.raises(FontifyError, match="source image hash"):
        run_plan(tmp_path, plan)
    plan["source_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    plan["image_size"] = [33, 32]
    with pytest.raises(FontifyError, match="dimensions"):
        run_plan(tmp_path, plan)
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"/>'
    )  # Even disguised as PNG.
    plan["source_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    monkeypatch.setattr(
        "fontify.raster._raster_dependencies",
        lambda: pytest.fail("vector reached raster dependencies"),
    )
    with pytest.raises(FontifyError, match="native vector"):
        run_plan(tmp_path, plan)


def test_raster_optional_dependencies_are_lazy():
    script = "import sys; import fontify.raster; assert not {'PIL', 'numpy', 'potrace'} & set(sys.modules)"
    subprocess.run([sys.executable, "-c", script], check=True)


def test_raster_dangling_output_symlink_is_not_followed(tmp_path):
    plan, _ = source_plan(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    target = tmp_path / "uncreated-target"
    output = tmp_path / "existing-link"
    output.symlink_to(target, target_is_directory=True)
    with pytest.raises(FontifyError, match="already exists"):
        trace_sheet(plan_path, output)
    assert output.is_symlink()
    assert not target.exists()


def test_raster_oversized_header_has_actionable_error(tmp_path):
    plan, image = source_plan(tmp_path)
    data = bytearray(image.read_bytes())
    data[16:24] = struct.pack(">II", 100000, 100000)
    data[29:33] = struct.pack(">I", zlib.crc32(data[12:29]))
    image.write_bytes(data)
    plan["source_sha256"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(FontifyError, match="cannot decode raster source"):
        run_plan(tmp_path, plan)
    assert not (tmp_path / "candidate").exists()
