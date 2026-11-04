"""Optional server-side Recraft vector adapter, with an injectable HTTP client.

No generation happens during import, construction, payload planning or compilation.
No automatic retries: a timeout may already have consumed credits.
"""

import base64
import hashlib
import json
import os
import re
from pathlib import Path

from ..model import FontifyError
from . import Artwork, DesignRequest

MODELS = {
    "recraftv4_1_vector",
    "recraftv4_1_pro_vector",
    "recraftv4_1_utility_vector",
    "recraftv4_1_utility_pro_vector",
}
API_BASE = "https://external.api.recraft.ai/v1"


def plan_request(request: DesignRequest):
    if (
        not isinstance(request.prompt, str)
        or not request.prompt.strip()
        or len(request.prompt) > 10000
    ):
        raise FontifyError("Recraft prompt must contain 1-10000 characters")
    if request.model not in MODELS:
        raise FontifyError(
            "adapter supports documented V4.1 vector models only; select one explicitly"
        )
    if request.size not in {"1:1", "4:3", "3:4", "16:9", "9:16"}:
        raise FontifyError("adapter size must be 1:1, 4:3, 3:4, 16:9 or 9:16")
    if request.style_id and request.style_reference_urls:
        raise FontifyError("use style_id or style_reference_urls, not both")
    if request.style_id and not re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", request.style_id
    ):
        raise FontifyError("style_id must be a UUID from the provider")
    if len(request.style_reference_urls) > 10:
        raise FontifyError("at most ten style reference URLs")
    if any(not u.startswith("https://") for u in request.style_reference_urls):
        raise FontifyError("style reference URLs must use HTTPS")
    payload = {
        "prompt": request.prompt,
        "model": request.model,
        "size": request.size,
        "n": 1,
        "response_format": "b64_json",
    }
    if request.style_id:
        payload["style_id"] = request.style_id
    if request.style_reference_urls:
        payload["style_reference_urls"] = list(request.style_reference_urls)
    if request.seed is not None:
        if (
            isinstance(request.seed, bool)
            or not isinstance(request.seed, int)
            or not 0 <= request.seed <= 2147483647
        ):
            raise FontifyError("seed must be an integer from 0 to 2147483647")
        payload["random_seed"] = request.seed
    return payload


class RecraftProvider:
    def __init__(self, *, token=None, client=None):
        self._token = token
        self._client = client

    def generate(self, request: DesignRequest, *, allow_paid=False):
        payload = plan_request(request)
        if not allow_paid:
            raise FontifyError(
                "Recraft generation may spend credits; explicit allow_paid=True is required"
            )
        token = self._token or os.environ.get("RECRAFT_API_TOKEN")
        if not token:
            raise FontifyError(
                "set RECRAFT_API_TOKEN on the server; no credential is needed for offline builds"
            )
        try:
            import httpx
        except ImportError:
            raise FontifyError(
                "install fontify[recraft] for the optional provider"
            ) from None
        owned = self._client is None
        client = self._client or httpx.Client(timeout=120, follow_redirects=False)
        try:
            try:
                response = client.post(
                    API_BASE + "/images/generations",
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
            except httpx.HTTPError:
                raise FontifyError(
                    "Recraft network request failed; no retry was made (credits may already be charged)"
                ) from None
            if not response.is_success:
                # Provider bodies/URLs may contain credentials or signed asset URLs.
                raise FontifyError(
                    f"Recraft returned HTTP {response.status_code}; no retry was made"
                )
            try:
                result = response.json()
                item = result["data"][0]
                svg = base64.b64decode(item["b64_json"], validate=True)
            except (ValueError, KeyError, IndexError, TypeError):
                raise FontifyError(
                    "Recraft did not return b64_json SVG; adapter will not fetch arbitrary response URLs"
                ) from None
            if len(svg) > 10_000_000:
                raise FontifyError("Recraft artwork exceeds 10 MB limit")
            try:
                from defusedxml import ElementTree as SafeET

                root = SafeET.fromstring(
                    svg, forbid_dtd=True, forbid_entities=True, forbid_external=True
                )
                if root.tag.rsplit("}", 1)[-1] != "svg":
                    raise ValueError()
            except Exception:
                raise FontifyError("Recraft response is not safe SVG XML") from None
            # Keep prompt content and reference URLs out of logs/provenance by default.
            provenance = {
                "provider": "recraft-api",
                "model": request.model,
                "size": request.size,
                "request_sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest(),
                "artwork_sha256": hashlib.sha256(svg).hexdigest(),
                "credits": result.get("credits"),
                "review_status": "unreviewed_source_artwork",
            }
            style_id = result.get("style_id")
            if isinstance(style_id, str) and re.fullmatch(
                r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", style_id
            ):
                provenance["style_id"] = style_id
            return Artwork(svg, provenance)
        finally:
            if owned:
                client.close()


def save_candidate(artwork: Artwork, directory):
    """Write a fresh review folder, never overwrite existing approved/source glyphs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "source.svg").write_bytes(artwork.svg)
    (directory / "provenance.json").write_text(
        json.dumps(artwork.provenance, indent=2) + "\n"
    )
    return directory / "source.svg"
