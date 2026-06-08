"""Allow ``python -m taskmaster.mcp serve`` to start the MCP server."""

from __future__ import annotations

import sys

from .server import serve


def main() -> None:
    transport = "stdio"
    host = "127.0.0.1"
    port = 8000
    args = sys.argv[1:]
    if "serve" in args:
        args.remove("serve")
    if "--sse" in args:
        transport = "sse"
        args.remove("--sse")
    for i, a in enumerate(list(args)):
        if a == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif a == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
    serve(transport=transport, host=host, port=port)


if __name__ == "__main__":
    main()
