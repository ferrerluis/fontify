import base64
import json

import httpx
import pytest

from fontify import FontifyError
from fontify.providers import DesignRequest, LocalSVGProvider
from fontify.providers.mcp import discover_schema
from fontify.providers.recraft import RecraftProvider, plan_request, save_candidate

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M0 0 H100 V100 H0 Z"/></svg>'


def test_adapter_paid_gate_and_local_provider(monkeypatch, tmp_path):
    monkeypatch.delenv("RECRAFT_API_TOKEN", raising=False)
    req = DesignRequest("One concept sheet of A V O R")
    assert plan_request(req)["model"] == "recraftv4_1_vector"
    with pytest.raises(FontifyError, match="allow_paid"):
        RecraftProvider().generate(req)
    with pytest.raises(FontifyError, match="RECRAFT_API_TOKEN"):
        RecraftProvider().generate(req, allow_paid=True)
    with pytest.raises(FontifyError, match="models only"):
        plan_request(DesignRequest("A", model="recraftv4_1"))
    p = tmp_path / "a.svg"
    p.write_bytes(SVG)
    assert LocalSVGProvider(p).generate().svg == SVG


def test_adapter_vector_payload_mock_and_save(tmp_path):
    requests = []

    def handle(req):
        requests.append(req)
        assert req.headers["authorization"] == "Bearer TEST_SECRET"
        body = json.loads(req.content)
        assert (
            body["n"] == 1
            and body["response_format"] == "b64_json"
            and "style" not in body
        )
        assert body["style_reference_urls"] == ["https://example.org/reference.png"]
        return httpx.Response(
            200,
            json={
                "credits": 80,
                "data": [{"b64_json": base64.b64encode(SVG).decode()}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        artwork = RecraftProvider(token="TEST_SECRET", client=client).generate(
            DesignRequest(
                "Glyph O", style_reference_urls=("https://example.org/reference.png",)
            ),
            allow_paid=True,
        )
    p = save_candidate(artwork, tmp_path / "candidate")
    assert p.read_bytes() == SVG and len(requests) == 1
    meta = (p.parent / "provenance.json").read_text()
    assert "TEST_SECRET" not in meta and "reference.png" not in meta
    assert artwork.provenance["review_status"] == "unreviewed_source_artwork"
    with pytest.raises(FileExistsError):
        save_candidate(artwork, p.parent)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_adapter_http_errors_are_not_retried(status):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(status, text="sensitive provider body")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(FontifyError, match=f"HTTP {status}") as e:
            RecraftProvider(token="secret", client=client).generate(
                DesignRequest("A"), allow_paid=True
            )
    assert len(calls) == 1 and "sensitive" not in str(e.value)


def test_adapter_rejects_url_response_without_fetch():
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(
            200, json={"data": [{"url": "https://untrusted.example/file"}]}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(FontifyError, match="b64_json"):
            RecraftProvider(token="secret", client=client).generate(
                DesignRequest("A"), allow_paid=True
            )
    assert len(calls) == 1


def test_discovery_reads_live_schema_and_pagination(tmp_path):
    methods = []

    def handle(req):
        b = json.loads(req.content)
        methods.append(b["method"])
        if b["method"] == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "mock", "version": "1"},
                    },
                },
                headers={"Mcp-Session-Id": "PRIVATE_SESSION"},
            )
        assert req.headers["Mcp-Session-Id"] == "PRIVATE_SESSION"
        if b["method"] == "notifications/initialized":
            return httpx.Response(202)
        assert b["method"] == "tools/list"
        if b["params"].get("cursor") == "next":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "result": {
                        "tools": [
                            {
                                "name": "get_user",
                                "inputSchema": {"type": "object", "properties": {}},
                            }
                        ]
                    },
                },
            )
        body = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "generate_image",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"actual_live_field": {"type": "string"}},
                        },
                    }
                ],
                "nextCursor": "next",
            },
        }
        return httpx.Response(
            200,
            text="event: message\ndata: " + json.dumps(body) + "\n\n",
            headers={"Content-Type": "text/event-stream"},
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = discover_schema(
            tmp_path / "schema.json", client=client, bearer_token="SECRET_TOKEN"
        )
    assert "actual_live_field" in result["tools"][0]["inputSchema"]["properties"]
    assert len(result["tools"]) == 2 and "tools/call" not in methods
    saved = (tmp_path / "schema.json").read_text()
    assert "PRIVATE_SESSION" not in saved and "SECRET_TOKEN" not in saved


def test_discovery_records_no_invented_schema_on_block(tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(403))
    ) as client:
        with pytest.raises(FontifyError, match="no schema was verified"):
            discover_schema(tmp_path / "schema.json", client=client)
    assert not (tmp_path / "schema.json").exists()
