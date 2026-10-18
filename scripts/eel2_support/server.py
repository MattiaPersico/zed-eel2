"""LSP 3.17 over stdio. Stdout is reserved exclusively for framed JSON-RPC."""

import json
import sys
import traceback

from .language import Document, TOKEN_TYPES, Workspace

MAX_MESSAGE = 16 * 1024 * 1024


def read_message(stream):
    headers = {}
    size = 0
    while True:
        line = stream.readline(8193)
        if not line:
            if not headers:
                return None
            raise ValueError("Truncated LSP headers")
        size += len(line)
        if size > 8192:
            raise ValueError("LSP headers too large")
        if line in (b"\r\n", b"\n"):
            break
        name, separator, value = line.partition(b":")
        if not separator:
            raise ValueError("Invalid LSP header")
        headers[name.strip().lower()] = value.strip()
    try:
        length = int(headers[b"content-length"])
    except (KeyError, ValueError) as exc:
        raise ValueError("Missing or invalid Content-Length") from exc
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError("LSP message size out of range")
    chunks, remaining = [], length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ValueError("Truncated LSP payload")
        chunks.append(chunk)
        remaining -= len(chunk)
    message = json.loads(b"".join(chunks))
    if not isinstance(message, dict):
        raise ValueError("Expected a JSON-RPC object")
    return message


def write_message(stream, message):
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(("Content-Length: %d\r\n\r\n" % len(body)).encode("ascii") + body)
    stream.flush()


class Server:
    def __init__(self, output):
        self.output = output
        self.workspace = Workspace()
        self.initialized = False
        self.shutdown = False
        self.published = {}

    def send(self, **message):
        write_message(self.output, dict(jsonrpc="2.0", **message))

    def publish(self, document):
        diagnostics = self.workspace.diagnostics(document)
        if self.published.get(document.uri) == diagnostics:
            return
        self.published[document.uri] = diagnostics
        params = dict(uri=document.uri, diagnostics=diagnostics)
        if document.version is not None:
            params["version"] = document.version
        self.send(method="textDocument/publishDiagnostics", params=params)

    def publish_all(self):
        # Imported buffers can change without being saved. Recheck open dependents too.
        for document in self.workspace.documents.values():
            self.publish(document)

    def handle(self, message):
        method = message.get("method")
        request = "id" in message
        if method is None:  # Client response to a server request (none currently sent).
            return None
        if method == "exit":
            return 0 if self.shutdown else 1
        if method == "initialize" and request and not self.initialized:
            self.initialized = True
            self.send(id=message["id"], result=dict(
                serverInfo=dict(name="MTT EEL2 Language Server", version="0.2.0"),
                capabilities=dict(
                    positionEncoding="utf-16",
                    textDocumentSync=dict(openClose=True, change=1, save=dict(includeText=False)),
                    completionProvider=dict(triggerCharacters=[".", "@", "#", "$"]),
                    hoverProvider=True, definitionProvider=True, documentSymbolProvider=True,
                    signatureHelpProvider=dict(triggerCharacters=["(", ","], retriggerCharacters=[","]),
                    semanticTokensProvider=dict(legend=dict(tokenTypes=TOKEN_TYPES, tokenModifiers=[]),
                                                full=True, range=False),
                )))
            return None
        if not self.initialized or self.shutdown:
            if request:
                self.send(id=message["id"], error=dict(code=-32600 if self.shutdown else -32002,
                                                      message="Server shut down" if self.shutdown else "Server not initialized"))
            return None
        if method == "shutdown" and request:
            self.shutdown = True
            self.send(id=message["id"], result=None)
            return None
        params = message.get("params") or {}
        if method == "textDocument/didOpen":
            value = params["textDocument"]
            self.workspace.open(value["uri"], value["text"], value.get("version"))
            self.publish_all()
        elif method == "textDocument/didChange":
            value = params["textDocument"]
            document = self.workspace.documents.get(value["uri"])
            if document and (document.version is None or value.get("version", 0) > document.version):
                text = document.text
                # Full sync is advertised. Accept ranged edits defensively as well.
                for change in params["contentChanges"]:
                    if "range" in change:
                        a = document.offset(change["range"]["start"])
                        b = document.offset(change["range"]["end"])
                        text = text[:a] + change["text"] + text[b:]
                        document = Document(value["uri"], text)
                    else:
                        text = change["text"]
                        document = Document(value["uri"], text)
                # The final edit already produced the index; do not parse it twice.
                document.version = value.get("version")
                self.workspace.documents[value["uri"]] = document
                # Diagnostics check this buffer's structure and import availability,
                # not imported contents. Opening/closing/saving still rechecks all.
                self.publish(document)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.workspace.documents.pop(uri, None)
            self.workspace.disk_cache.pop(uri, None)
            self.published.pop(uri, None)
            self.send(method="textDocument/publishDiagnostics", params=dict(uri=uri, diagnostics=[]))
            self.publish_all()
        elif method in {"textDocument/didSave", "workspace/didChangeWatchedFiles"}:
            self.workspace.disk_cache.clear()
            self.publish_all()
        elif request:
            methods = {
                "textDocument/completion": self.workspace.completion,
                "textDocument/hover": self.workspace.hover,
                "textDocument/definition": self.workspace.definition,
                "textDocument/signatureHelp": self.workspace.signature,
            }
            document = self.workspace.read(params.get("textDocument", {}).get("uri", ""))
            if method in methods:
                result = methods[method](document, document.offset(params["position"])) if document else None
            elif method == "textDocument/documentSymbol":
                result = document.document_symbols() if document else []
            elif method == "textDocument/semanticTokens/full":
                result = document.semantic_tokens() if document else {"data": []}
            else:
                self.send(id=message["id"], error=dict(code=-32601, message="Method not found: " + method))
                return None
            self.send(id=message["id"], result=result)
        return None


def main():
    server = Server(sys.stdout.buffer)
    while True:
        try:
            message = read_message(sys.stdin.buffer)
        except (ValueError, UnicodeError) as exc:
            print("eel2-lsp: " + str(exc), file=sys.stderr)
            return 1
        if message is None:
            return 0 if server.shutdown else 1
        try:
            status = server.handle(message)
            if status is not None:
                return status
        except Exception:
            traceback.print_exc(file=sys.stderr)
            if "id" in message:
                server.send(id=message["id"], error=dict(code=-32603, message="Internal error; see server log"))
