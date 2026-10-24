"""LSP 3.17 over stdio. Stdout is reserved exclusively for framed JSON-RPC."""

import json
import sys
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor

from . import VERSION
from .language import Document, TOKEN_TYPES, Workspace
from .editing import EditError, format_document, prepare_rename, rename
from .compiler import checker_path, check as compiler_check

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
        self.versioned_edits = False
        self.lock = threading.RLock()
        self.checker = checker_path()
        self.executor = ThreadPoolExecutor(max_workers=1) if self.checker else None
        self.compiler_results, self.compiler_jobs = {}, {}
        self.compiler_generation = 0
        self.watch_supported = False
        self.watch_requested = False

    def send(self, **message):
        write_message(self.output, dict(jsonrpc="2.0", **message))

    def publish(self, document):
        diagnostics = self.workspace.diagnostics(document) + self.compiler_results.get(document.uri, [])
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
        with self.lock:
            return self._handle(message)

    def invalidate_compiler(self):
        self.compiler_generation += 1
        affected = list(self.compiler_results)
        self.compiler_results.clear()
        for future in list(self.compiler_jobs.values()):
            future.cancel()
        self.compiler_jobs.clear()
        for uri in affected:
            if uri in self.workspace.documents:
                self.publish(self.workspace.documents[uri])

    def schedule_compiler(self):
        if not self.executor:
            return
        generation = self.compiler_generation
        for document in list(self.workspace.documents.values()):
            if not document.uri.lower().endswith('.jsfx') or len(self.compiler_jobs) >= 8:
                continue
            sources = [document] + self.workspace.dependencies(document)
            future = self.executor.submit(compiler_check, self.checker, self.workspace, document, sources)
            self.compiler_jobs[document.uri] = future
            def completed(result, document=document, generation=generation):
                with self.lock:
                    if result.cancelled() or self.shutdown or generation != self.compiler_generation:
                        return
                    self.compiler_jobs.pop(document.uri, None)
                    if self.workspace.documents.get(document.uri) is not document:
                        return
                    try:
                        self.compiler_results[document.uri] = result.result()
                    except Exception as error:
                        print('eel2 compiler: ' + str(error), file=sys.stderr)
                        return
                    self.publish(document)
            future.add_done_callback(completed)

    def _handle(self, message):
        method = message.get("method")
        request = "id" in message
        if method is None:
            if message.get('id') == 'eel2-watch-files' and message.get('error'):
                self.send(method='window/logMessage', params=dict(type=2,
                    message='EEL2 file watching was declined; save or restart to refresh diagnostics.'))
            return None
        if method == "exit":
            status = 0 if self.shutdown else 1
            self.shutdown = True
            self.invalidate_compiler()
            if self.executor:
                self.executor.shutdown(wait=False, cancel_futures=True)
            return status
        if method == "initialize" and request and not self.initialized:
            self.initialized = True
            options = message.get('params') or {}
            folders = options.get('workspaceFolders') or []
            self.workspace.set_folders([f['uri'] for f in folders] or
                                       ([options['rootUri']] if options.get('rootUri') else []))
            initialization = options.get('initializationOptions') or {}
            excludes = initialization.get('exclude', []) if isinstance(initialization, dict) else []
            self.workspace.excludes = [x for x in excludes if isinstance(x, str)] if isinstance(excludes, list) else []
            self.versioned_edits = bool(options.get('capabilities', {}).get('workspace', {}).get(
                'workspaceEdit', {}).get('documentChanges'))
            self.watch_supported = bool(options.get('capabilities', {}).get('workspace', {}).get(
                'didChangeWatchedFiles', {}).get('dynamicRegistration'))
            self.send(id=message["id"], result=dict(
                serverInfo=dict(name="MTT EEL2 Language Server", version=VERSION),
                capabilities=dict(
                    positionEncoding="utf-16",
                    textDocumentSync=dict(openClose=True, change=1, save=dict(includeText=False)),
                    completionProvider=dict(triggerCharacters=[".", "@", "#", "$"]),
                    hoverProvider=True, definitionProvider=True, documentSymbolProvider=True,
                    referencesProvider=True,
                    workspaceSymbolProvider=True, documentHighlightProvider=True,
                    renameProvider=dict(prepareProvider=True), documentFormattingProvider=True,
                    workspace=dict(workspaceFolders=dict(supported=True, changeNotifications=True)),
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
            self.invalidate_compiler()
            if self.executor:
                self.executor.shutdown(wait=False, cancel_futures=True)
            self.send(id=message["id"], result=None)
            return None
        params = message.get("params") or {}
        if method == 'initialized':
            if self.watch_supported and not self.watch_requested:
                self.watch_requested = True
                self.send(id='eel2-watch-files', method='client/registerCapability', params=dict(
                    registrations=[dict(id='eel2-source-files', method='workspace/didChangeWatchedFiles',
                        registerOptions=dict(watchers=[dict(
                            globPattern='**/*.{[jJ][sS][fF][xX],[jJ][sS][fF][xX]-[iI][nN][cC],[eE][eE][lL],[eE][eE][lL]2}',
                            kind=7)]))]))
        elif method == 'workspace/didChangeWorkspaceFolders':
            event = params.get('event', {})
            removed = {f['uri'] for f in event.get('removed', [])}
            uris = [p.as_uri() for p in self.workspace.roots if p.as_uri() not in removed]
            self.workspace.set_folders(uris + [f['uri'] for f in event.get('added', [])])
            self.workspace.disk_cache.clear()
            self.invalidate_compiler()
            self.publish_all()
            self.schedule_compiler()
        elif method == "textDocument/didOpen":
            value = params["textDocument"]
            self.workspace.open(value["uri"], value["text"], value.get("version"))
            self.invalidate_compiler()
            self.publish_all()
            self.schedule_compiler()
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
                self.invalidate_compiler()
                # Diagnostics check this buffer's structure and import availability,
                # not imported contents. Opening/closing/saving still rechecks all.
                self.publish(document)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.workspace.documents.pop(uri, None)
            self.invalidate_compiler()
            self.workspace.disk_cache.pop(uri, None)
            self.published.pop(uri, None)
            self.send(method="textDocument/publishDiagnostics", params=dict(uri=uri, diagnostics=[]))
            self.publish_all()
            self.schedule_compiler()
        elif method in {"textDocument/didSave", "workspace/didChangeWatchedFiles"}:
            self.workspace.disk_cache.clear()
            self.invalidate_compiler()
            self.publish_all()
            self.schedule_compiler()
        elif request:
            methods = {
                "textDocument/completion": self.workspace.completion,
                "textDocument/hover": self.workspace.hover,
                "textDocument/definition": self.workspace.definition,
                "textDocument/signatureHelp": self.workspace.signature,
                "textDocument/documentHighlight": self.workspace.highlights,
            }
            document = self.workspace.read(params.get("textDocument", {}).get("uri", ""))
            if method in methods:
                result = methods[method](document, document.offset(params["position"])) if document else None
            elif method == 'workspace/symbol':
                result = self.workspace.workspace_symbols(params.get('query', ''))
                if not self.workspace.scan_complete:
                    self.send(method='window/logMessage', params=dict(type=2,
                        message='EEL2 symbol results are partial: refine the query or check workspace scan limits.'))
            elif method == "textDocument/references":
                result = self.workspace.references(document, document.offset(params["position"]),
                    params.get("context", {}).get("includeDeclaration", False)) if document else []
                if not self.workspace.scan_complete:
                    self.send(method='window/logMessage', params=dict(type=2,
                        message='EEL2 reference results are partial: workspace scan limits or unreadable files.'))
            elif method == 'textDocument/prepareRename':
                result = prepare_rename(self.workspace, document, document.offset(params['position'])) if document else None
            elif method == 'textDocument/rename':
                try:
                    if not document:
                        raise EditError('Document unavailable.')
                    result = rename(self.workspace, document, document.offset(params['position']),
                                    params.get('newName'), self.versioned_edits)
                except EditError as error:
                    self.send(id=message['id'], error=dict(code=-32602, message=str(error)))
                    return None
            elif method == 'textDocument/formatting':
                result = format_document(document, params.get('options', {})) if document else []
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
