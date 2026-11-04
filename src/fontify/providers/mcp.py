"""Read-only MCP schema discovery. Never executes tools or initiates OAuth."""

import json
from pathlib import Path

from ..model import FontifyError

MCP_URL = "https://mcp.recraft.ai/mcp"


def _message(response):
    if response.status_code in (401, 403):
        raise FontifyError(
            f"MCP discovery blocked (HTTP {response.status_code}); use your OAuth-capable client; no schema was verified"
        )
    if not response.is_success:
        raise FontifyError(f"MCP discovery failed (HTTP {response.status_code})")
    try:
        if "text/event-stream" in response.headers.get("content-type", ""):
            events = response.text.replace("\r\n", "\n").split("\n\n")
            candidates = []
            for event in events:
                data = "\n".join(
                    line[5:].lstrip()
                    for line in event.splitlines()
                    if line.startswith("data:")
                )
                if data:
                    candidates.append(json.loads(data))
            value = next(v for v in candidates if "result" in v or "error" in v)
        else:
            value = response.json()
        if "error" in value:
            raise FontifyError(
                "MCP returned a JSON-RPC error; schema discovery incomplete"
            )
        return value["result"]
    except (ValueError, KeyError, StopIteration, TypeError):
        raise FontifyError("invalid MCP discovery response") from None


def discover_schema(output, *, client=None, bearer_token=None):
    try:
        import httpx
    except ImportError:
        raise FontifyError(
            "install fontify[recraft] to discover remote MCP schemas"
        ) from None
    owned = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    try:
        first = client.post(
            MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "fontify-schema", "version": "0.1.0"},
                },
            },
        )
        server = _message(first)
        protocol = server.get("protocolVersion")
        if not protocol:
            raise FontifyError("MCP initialize did not return protocolVersion")
        headers["MCP-Protocol-Version"] = protocol
        if first.headers.get("mcp-session-id"):
            headers["Mcp-Session-Id"] = first.headers["mcp-session-id"]
        notify = client.post(
            MCP_URL,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        if not notify.is_success:
            raise FontifyError(
                f"MCP initialization notification failed (HTTP {notify.status_code})"
            )
        schemas = []
        cursor = None
        seen = set()
        for i in range(100):
            result = _message(
                client.post(
                    MCP_URL,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": i + 2,
                        "method": "tools/list",
                        "params": ({"cursor": cursor} if cursor else {}),
                    },
                )
            )
            page = result.get("tools")
            if not isinstance(page, list) or not all(
                isinstance(t, dict)
                and isinstance(t.get("name"), str)
                and isinstance(t.get("inputSchema"), dict)
                for t in page
            ):
                raise FontifyError("MCP tools/list lacks tool names/input schemas")
            schemas.extend(
                {
                    k: t[k]
                    for k in ("name", "description", "inputSchema", "outputSchema")
                    if k in t
                }
                for t in page
            )
            cursor = result.get("nextCursor")
            if not cursor:
                break
            if cursor in seen:
                raise FontifyError("MCP tools/list repeated cursor")
            seen.add(cursor)
        else:
            raise FontifyError("MCP tools/list exceeded page limit")
        snapshot = {
            "endpoint": MCP_URL,
            "protocol_version": protocol,
            "schema_verified": True,
            "tools": schemas,
        }
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as f:
            json.dump(snapshot, f, indent=2)
            f.write("\n")
        return snapshot
    except httpx.HTTPError:
        raise FontifyError(
            "MCP discovery network error; no schema was verified"
        ) from None
    finally:
        if owned:
            client.close()
