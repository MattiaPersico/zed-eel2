"""Lexical EEL2 services. This module never compiles or executes effect code."""

from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import url2pathname

from .catalog import BUILTINS, OVERLOADS, SECTIONS

IDENT = r"(?:[A-Za-z_][A-Za-z_0-9.]*|\#[A-Za-z_0-9.]*|\$(?:pi|phi|e))"
LEX = re.compile(
    r'(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|\Z))'
    r'|(?P<preprocessor><\?[\s\S]*?(?:\?>|\Z))'
    r'|(?P<string>"(?:\\[\s\S]|[^"\\])*(?:"|\Z))'
    r"|(?P<number>\$?'(?:\\[\s\S]|[^'\\])*(?:'|\Z)|(?:\$x|0x)[0-9a-f]+|\$~\d+|(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)"
    r"|(?P<identifier>" + IDENT + r")"
    r"|(?P<operator>===|!==|==|!=|<=|>=|<<|>>|&&|\|\||[+*/%^|&~\-]=|[^\s])",
    re.IGNORECASE,
)
META = re.compile(r"[ \t]*(?:desc|tags|options|in_pin|out_pin|filename|slider\d+):[^\r\n]*", re.I)
SECTION = re.compile(r"[ \t]*(@[A-Za-z_]+)[^\r\n]*")
IMPORT = re.compile(r"[ \t]*import[ \t]+([^\r\n]+)", re.I)
ASSIGN = {"=", "+=", "-=", "*=", "/=", "%=", "^=", "|=", "&=", "~="}
TOKEN_TYPES = ["comment", "string", "number", "keyword", "function", "variable", "operator", "macro"]


def uri_path(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    return Path(url2pathname(parsed.path))


def utf16(text):
    return len(text.encode("utf-16-le")) // 2


def canonical_uri(uri):
    path = uri_path(uri)
    try:
        return path.resolve().as_uri() if path else uri
    except (OSError, ValueError, RuntimeError):
        return uri


@dataclass
class Token:
    value: str
    start: int
    end: int
    kind: str


@dataclass
class Symbol:
    name: str
    token: Token
    kind: int
    detail: str
    end: int
    section: str = ""
    parameters: object = None
    scope: object = None
    storage: str = "global"


@dataclass
class FunctionScope:
    start: int
    end: int
    variables: dict


class Document:
    def __init__(self, uri, text, version=None):
        self.uri, self.text, self.version = uri, text, version
        self.canonical_uri = canonical_uri(uri)
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self.tokens, self.sections, self.imports, self.symbols = [], [], [], []
        self.issues, self.pairs = [], {}
        self.scopes, self.scope_starts = [], []
        self.preprocessed = False
        self.lex()
        self.token_starts = [t.start for t in self.tokens]
        self.code = [t for t in self.tokens if t.kind not in
                     {"comment", "string", "header", "import", "preprocessor", "section"}]
        self.index()
        self.by_name, self.declarations = {}, {}
        for symbol in self.symbols:
            self.by_name.setdefault(symbol.name.lower(), []).append(symbol)
            self.declarations[symbol.token.start] = symbol
        self.code_indices = {t.start: i for i, t in enumerate(self.code)}

    def position(self, offset):
        offset = max(0, min(offset, len(self.text)))
        line = bisect_right(self.starts, offset) - 1
        return dict(line=line, character=utf16(self.text[self.starts[line]:offset]))

    def offset(self, position):
        line = max(0, position.get("line", 0))
        if line >= len(self.starts):
            return len(self.text)
        start = self.starts[line]
        end = self.starts[line + 1] if line + 1 < len(self.starts) else len(self.text)
        units, character = 0, max(0, position.get("character", 0))
        for offset in range(start, end):
            if self.text[offset] in "\r\n" or units >= character:
                return offset
            units += utf16(self.text[offset])
        return end

    def range(self, start, end):
        return dict(start=self.position(start), end=self.position(end))

    def issue(self, token, message, severity=1):
        self.issues.append(dict(range=self.range(token.start, token.end), severity=severity,
                                source="eel2-lsp", message=message))

    def lex(self):
        pos, in_header = 0, self.uri.lower().endswith(".jsfx")
        while pos < len(self.text):
            # Header text must be consumed before strings/comments within that text.
            if pos == 0 or self.text[pos - 1] == "\n":
                section = SECTION.match(self.text, pos)
                meta = META.match(self.text, pos)
                imported = IMPORT.match(self.text, pos)
                if section:
                    start, end = section.span(1)
                    token = Token(section[1], start, end, "section")
                    self.tokens.append(token)
                    self.sections.append(token)
                    in_header = False
                    pos = section.end()
                    continue
                if meta or imported:
                    match = meta or imported
                    token = Token(match[0], pos, match.end(), "header" if meta else "import")
                    self.tokens.append(token)
                    if imported:
                        value = imported[1].strip()
                        # Accept a quoted path and a trailing line comment.
                        path_match = re.match(r'"([^"]+)"|([^\s]+)', value)
                        if path_match:
                            self.imports.append((path_match[1] or path_match[2], token))
                    elif re.match(r"\s*slider\d+:", token.value, re.I):
                        slider = re.match(r"\s*(slider\d+):\s*(?:([A-Za-z_]\w*)\s*=)?", token.value, re.I)
                        for group in (1, 2):
                            if slider[group]:
                                a, b = slider.span(group)
                                name = Token(slider[group], pos + a, pos + b, "identifier")
                                self.symbols.append(Symbol(name.value, name, 13, token.value.strip(), token.end))
                    pos = match.end()
                    continue
                if in_header and not self.text[pos:].lstrip(" \t").startswith(("//", "/*", "<?")):
                    end = self.text.find("\n", pos)
                    end = len(self.text) if end < 0 else end
                    if end > pos:
                        self.tokens.append(Token(self.text[pos:end], pos, end, "header"))
                        pos = end
                        continue
            if self.text[pos].isspace():
                pos += 1
                continue
            match = LEX.match(self.text, pos)
            token = Token(match[0], pos, match.end(), match.lastgroup)
            self.tokens.append(token)
            if token.kind == "preprocessor":
                self.preprocessed = True
            elif token.kind == "comment" and token.value.startswith("/*") and not token.value.endswith("*/"):
                self.issue(token, "Unclosed block comment.")
            elif token.kind == "string" and not re.fullmatch(r'"(?:\\[\s\S]|[^"\\])*"', token.value):
                self.issue(token, "Unclosed string.")
            pos = match.end()

    def section_at(self, offset):
        result = ""
        for token in self.sections:
            if token.start > offset:
                break
            result = token.value.lower()
        return result

    def index(self):
        stack = []
        # Reset at section boundaries; a bracket cannot close in another section.
        section_ends = iter(self.sections)
        boundary = next(section_ends, None)
        for i, token in enumerate(self.code):
            while boundary and boundary.start < token.start:
                for j in stack:
                    self.issue(self.code[j], "Unclosed '" + self.code[j].value + "' before section.")
                stack = []
                boundary = next(section_ends, None)
            if token.value in ("(", "["):
                stack.append(i)
            elif token.value in (")", "]"):
                expected = "(" if token.value == ")" else "["
                if stack and self.code[stack[-1]].value == expected:
                    opening = stack.pop()
                    self.pairs[opening] = i
                else:
                    self.issue(token, "Unmatched '" + token.value + "'.")
        for j in stack:
            self.issue(self.code[j], "Unclosed '" + self.code[j].value + "'.")
        seen = set()
        for section in self.sections:
            name = section.value.lower()
            if name not in SECTIONS:
                self.issue(section, "Unknown JSFX section " + section.value + ".", 2)
            elif name in seen:
                self.issue(section, "Repeated JSFX section " + section.value + ".", 2)
            seen.add(name)
        # Generated/preprocessed source cannot be checked as a single EEL2 stream.
        if self.preprocessed:
            self.issues = []
        code = self.code
        declarations = set()
        for i, token in enumerate(code):
            if token.value.lower() != "function" or i + 2 >= len(code):
                continue
            name, opening = code[i + 1:i + 3]
            if name.kind != "identifier" or opening.value != "(" or i + 2 not in self.pairs:
                continue
            close = self.pairs[i + 2]
            params = code[i + 3:close]
            local_tokens = []
            signature_params = []
            for n, item in enumerate(params):
                if item.kind == "identifier":
                    suffix = "*" if n + 1 < len(params) and params[n + 1].value == "*" else ""
                    signature_params.append(item.value + suffix)
                    local_tokens.append((item, "namespace" if suffix else "parameter"))
            body = close + 1
            while body + 1 < len(code) and code[body].value.lower() in {"local", "static", "instance", "global", "globals"}:
                qualifier = code[body].value.lower()
                end = self.pairs.get(body + 1)
                if end is None:
                    break
                if qualifier in {"local", "static", "instance"}:
                    local_tokens.extend((t, qualifier) for t in code[body + 2:end] if t.kind == "identifier")
                body = end + 1
            end = self.pairs.get(body)
            # Keep unfinished function bodies scoped while the user is typing.
            body_end = code[end].end if end is not None else next(
                (s.start for s in self.sections if s.start > token.start), len(self.text))
            section = self.section_at(token.start)
            self.symbols.append(Symbol(name.value, name, 12,
                                       name.value + "(" + ", ".join(signature_params) + ")",
                                       body_end, section, signature_params))
            declarations.add(name.start)
            scope = FunctionScope(token.start, body_end, {})
            self.scopes.append(scope)
            self.scope_starts.append(token.start)
            for local, storage in local_tokens:
                symbol = Symbol(local.value, local, 13, storage.title() + ": " + local.value,
                                local.end, section, scope=(token.start, body_end), storage=storage)
                self.symbols.append(symbol)
                scope.variables[local.value.lower()] = symbol
                declarations.add(local.start)
        globals_seen = {s.name.lower() for s in self.symbols if s.kind == 13 and not s.scope}
        for i, token in enumerate(code[:-1]):
            if token.kind != "identifier" or token.start in declarations or code[i + 1].value not in ASSIGN:
                continue
            scope = self.scope_at(token.start)
            name = token.value.lower()
            if scope and (self.local_symbol(scope, name) or name.startswith("this.")):
                continue
            if token.value.lower() in globals_seen:
                continue
            globals_seen.add(token.value.lower())
            self.symbols.append(Symbol(token.value, token, 13, "EEL2 variable: " + token.value,
                                       token.end, self.section_at(token.start)))

    def scope_at(self, offset):
        index = bisect_right(self.scope_starts, offset) - 1
        if index >= 0 and offset < self.scopes[index].end:
            return self.scopes[index]
        return None

    @staticmethod
    def local_symbol(scope, name):
        symbol = scope.variables.get(name)
        if symbol:
            return symbol
        if name.startswith("this."):
            symbol = scope.variables.get(name[5:])
            if symbol and symbol.storage == "instance":
                return symbol
        prefix = name.split(".", 1)[0]
        symbol = scope.variables.get(prefix)
        return symbol if symbol and symbol.storage == "namespace" else None

    def identifier_at(self, offset):
        # Slider names live inside opaque metadata tokens.
        token = self.token_at(offset)
        if token and token.kind == "header":
            return next((s.token for s in self.symbols if
                         s.token.start <= offset < s.token.end), None)
        return token if token and token.kind == "identifier" else None

    def is_call(self, token):
        declaration = self.declarations.get(token.start)
        if declaration:
            return declaration.kind == 12
        index = self.code_indices.get(token.start)
        return index is not None and index + 1 < len(self.code) and self.code[index + 1].value == "("

    def token_at(self, offset):
        # Prefer the next token at a boundary; accept identifier ends for completion/hover.
        index = bisect_right(self.token_starts, offset) - 1
        if index >= 0:
            token = self.tokens[index]
            if offset < token.end or offset == token.end and token.kind == "identifier":
                return token
        return None

    def visible(self, offset):
        section = self.section_at(offset)
        return [s for s in self.symbols if
                (not s.scope or s.scope[0] <= offset <= s.scope[1]) and
                (s.kind != 12 or s.section in ("", "@init", section))]

    def document_symbols(self):
        symbols = [dict(name=s.name, kind=s.kind, detail=s.detail,
                        range=self.range(s.token.start, s.end),
                        selectionRange=self.range(s.token.start, s.token.end))
                   for s in self.symbols if not s.scope]
        for i, section in enumerate(self.sections):
            end = self.sections[i + 1].start if i + 1 < len(self.sections) else len(self.text)
            symbols.append(dict(name=section.value, kind=2,
                                range=self.range(section.start, end),
                                selectionRange=self.range(section.start, section.end)))
        return sorted(symbols, key=lambda s: (s["range"]["start"]["line"], s["range"]["start"]["character"]))

    def semantic_tokens(self):
        data, last_line, last_col = [], 0, 0
        functions = {s.token.start for s in self.symbols if s.kind == 12}
        for i, token in enumerate(self.tokens):
            kind = token.kind
            if kind in {"header", "import", "preprocessor", "section"}:
                kind = "macro"
            elif kind == "identifier":
                builtin = BUILTINS.get(token.value.lower())
                following = self.tokens[i + 1].value if i + 1 < len(self.tokens) else ""
                kind = "function" if token.start in functions or following == "(" else "variable"
                if builtin and builtin["kind"] == 14:
                    kind = "keyword"
            # Multiline tokens are split into single-line LSP spans.
            start = token.start
            for piece in token.value.splitlines(keepends=True):
                content = piece.rstrip("\r\n")
                if content:
                    position = self.position(start)
                    line, col = position["line"], position["character"]
                    data.extend([line - last_line, col - last_col if line == last_line else col,
                                 utf16(content), TOKEN_TYPES.index(kind), 0])
                    last_line, last_col = line, col
                start += len(piece)
        return {"data": data}


class Workspace:
    MAX_FILE = 2 * 1024 * 1024
    MAX_IMPORTS = 64

    def __init__(self):
        self.documents = {}
        self.disk_cache = {}

    def open(self, uri, text, version=None):
        document = Document(uri, text, version)
        self.documents[uri] = document
        return document

    def read(self, uri):
        if uri in self.documents:
            return self.documents[uri]
        canonical = canonical_uri(uri)
        for key, document in self.documents.items():
            if document.canonical_uri == canonical:
                return document
        path = uri_path(uri)
        if path is None:
            return None
        try:
            stat = path.stat()
            if not path.is_file() or stat.st_size > self.MAX_FILE:
                return None
            key = (stat.st_mtime_ns, stat.st_size)
            cached = self.disk_cache.get(uri)
            if cached and cached[0] == key:
                return cached[1]
            document = Document(uri, path.read_text(encoding="utf-8-sig"))
            if len(self.disk_cache) >= 128:
                self.disk_cache.clear()
            self.disk_cache[uri] = (key, document)
            return document
        except (OSError, UnicodeError, ValueError):
            return None

    def import_uri(self, document, name):
        path = uri_path(document.uri)
        if path is None or Path(name).is_absolute():
            return None
        try:
            return (path.parent / name).resolve().as_uri()
        except (OSError, ValueError, RuntimeError):
            return None

    def dependencies(self, document):
        found, seen, pending = [], {canonical_uri(document.uri)}, [document]
        while pending and len(seen) < self.MAX_IMPORTS:
            current = pending.pop()
            for name, _ in current.imports:
                uri = self.import_uri(current, name)
                if not uri or uri in seen or len(seen) >= self.MAX_IMPORTS:
                    continue
                seen.add(uri)
                imported = self.read(uri)
                if imported:
                    found.append(imported)
                    pending.append(imported)
        return found

    def candidates(self, document, offset):
        result = [(document, s) for s in document.visible(offset)]
        for imported in self.dependencies(document):
            result.extend((imported, s) for s in imported.symbols
                          if not s.scope and (s.kind != 12 or s.section in ("", "@init")))
        return result

    def resolve(self, document, offset, name, kind=None, sources=None):
        token = document.identifier_at(offset)
        if kind is None:
            kind = 12 if token and document.is_call(token) else 13
        name = name.lower()
        scope = document.scope_at(offset)
        declaration = document.declarations.get(token.start) if token else None
        if declaration and declaration.kind == kind and declaration.name.lower() == name:
            return [(document, declaration)]
        if kind == 13 and scope:
            local = document.local_symbol(scope, name)
            if local:
                return [(document, local)]
            if name.startswith("this."):
                return []
        sources = sources if sources is not None else self.dependencies(document)
        section = document.section_at(offset)
        while True:
            matches = []
            for source in [document] + [d for d in sources if d.canonical_uri != document.canonical_uri]:
                for symbol in source.by_name.get(name, ()):
                    if symbol.kind != kind or symbol.scope:
                        continue
                    if kind == 12:
                        own = source.canonical_uri == document.canonical_uri
                        if symbol.section not in (("", "@init", section) if own else ("", "@init")):
                            continue
                        if own and scope and symbol.token.start >= scope.start:
                            continue
                    matches.append((source, symbol))
            if matches or kind != 12 or "." not in name:
                break
            name = name.split(".", 1)[1]
        if kind == 12:
            own = [(d, s) for d, s in matches if d.canonical_uri == document.canonical_uri]
            section_matches = [(d, s) for d, s in own if s.section == section]
            return section_matches or own or matches
        return matches

    def bindings(self, document, token, root, sources):
        """Return lexical identities and precise spans, without inferring runtime aliases."""
        if document.preprocessed:
            return []
        name = token.value.lower()
        if name == "#":  # Anonymous strings have no stable identity.
            return []
        declaration = document.declarations.get(token.start)
        declared = bool(declaration)
        scope = document.scope_at(token.start)
        prefix, dot, member = name.partition(".")
        if scope:
            local = scope.variables.get(prefix)
            if local and local.storage == "namespace" and dot:
                key = ("local", document.canonical_uri, local.token.start)
                # Namespace parameters bind the prefix, not every field to the parameter.
                return [(key, token.start, token.start + len(prefix), False),
                        (("namespace-member", document.canonical_uri, scope.start, name,
                          document.is_call(token)), token.start + len(prefix) + 1, token.end, False)]
            local = document.local_symbol(scope, name)
            if local and local.storage != "instance" and not document.is_call(token):
                return [(("local", document.canonical_uri, local.token.start),
                         token.start, token.end, declared)]
            if not document.is_call(token) and (name.startswith("this.") or
                                                local and local.storage == "instance"):
                member = name[5:] if name.startswith("this.") else name
                if not member or member.startswith("."):
                    return []  # Parent-relative namespaces need call-site analysis.
                start = token.end - len(member)
                return [(("instance", document.canonical_uri, scope.start, member),
                         start, token.end, declared)]
        if document.is_call(token):
            matches = self.resolve(document, token.start, name, 12, sources)
            if len(matches) == 1:
                source, symbol = matches[0]
                if source.preprocessed:
                    return []
                key = ("function", source.canonical_uri, symbol.token.start)
                return [(key, token.end - len(symbol.name), token.end, declared)]
            builtin = BUILTINS.get(name)
            if not matches and builtin and builtin["kind"] == 3:
                return [(("builtin", root.canonical_uri, name), token.start, token.end, False)]
            return []
        builtin = BUILTINS.get(name)
        if builtin and builtin["kind"] == 14:
            return []
        return [(("global", root.canonical_uri, name), token.start, token.end, declared)]

    def references(self, document, offset, include_declaration=False):
        token = document.identifier_at(offset)
        if not token or document.preprocessed:
            return []
        # Roots keep unrelated effects' global variables separate. Shared imported
        # functions retain a source identity across all open importing effects.
        graphs = {}
        for root in list(self.documents.values()) + [document]:
            if root.canonical_uri not in graphs:
                graphs[root.canonical_uri] = (root, [root] + self.dependencies(root))
        imported = {d.canonical_uri for _, docs in graphs.values() for d in docs[1:]}
        contexts = [(root, docs) for root, docs in graphs.values() if root.canonical_uri not in imported]
        # Preserve standalone include buffers and import cycles with no root.
        covered = {d.canonical_uri for _, docs in contexts for d in docs}
        for root, docs in graphs.values():
            if root.canonical_uri not in covered:
                contexts.append((root, docs))
                covered.update(d.canonical_uri for d in docs)
        targets = set()
        for root, docs in contexts:
            if any(d.canonical_uri == document.canonical_uri for d in docs):
                for key, start, end, _ in self.bindings(document, token, root, docs):
                    if start <= offset < end or offset == token.end == end:
                        targets.add(key)
        if not targets:
            return []
        locations = {}
        for root, docs in contexts:
            for source in docs:
                tokens = [t for t in source.code if t.kind == "identifier"]
                tokens.extend(s.token for s in source.symbols if s.token.start not in source.code_indices)
                for occurrence in tokens:
                    for key, start, end, declared in self.bindings(source, occurrence, root, docs):
                        if key in targets and (include_declaration or not declared):
                            locations[(source.canonical_uri, start, end)] = dict(
                                uri=source.uri, range=source.range(start, end))
        return sorted(locations.values(), key=lambda loc: (
            loc["uri"], loc["range"]["start"]["line"], loc["range"]["start"]["character"]))

    def diagnostics(self, document):
        issues = list(document.issues)
        if not document.preprocessed:
            for name, token in document.imports:
                uri = self.import_uri(document, name)
                if not uri or not self.read(uri):
                    issues.append(dict(range=document.range(token.start, token.end), severity=2,
                                       source="eel2-lsp", message="Cannot read local import '" + name +
                                       "'. REAPER's global import search is not checked."))
        return issues[:200]

    def completion(self, document, offset):
        offset = max(0, min(offset, len(document.text)))
        token = document.token_at(offset)
        if token and token.kind in {"comment", "string", "preprocessor"}:
            return []
        start = offset
        while start > 0 and re.match(r"[\w.#$@]", document.text[start - 1], re.ASCII):
            start -= 1
        prefix = document.text[start:offset]
        namespace = prefix.rsplit(".", 1)[0] + "." if "." in prefix else ""
        items = {k: {key: value for key, value in v.items() if key != "parameters"}
                 for k, v in BUILTINS.items() if not namespace}
        candidates = sorted(self.candidates(document, offset),
                            key=lambda pair: (pair[0].uri == document.uri, bool(pair[1].scope)))
        for source, symbol in candidates:
            label = symbol.name
            if namespace and symbol.kind == 12 and "." not in label:
                label = namespace + label
            items[label.lower()] = dict(label=label, kind=3 if symbol.kind == 12 else 6,
                                         detail=symbol.detail)
        end = token.end if token and token.kind in {"identifier", "section"} else offset
        result = []
        for key, item in items.items():
            if key.startswith(prefix.lower()):
                item = dict(item)
                item["textEdit"] = dict(range=document.range(start, end), newText=item["label"])
                result.append(item)
        return sorted(result, key=lambda item: item["label"].lower())

    def hover(self, document, offset):
        token = document.identifier_at(offset) or document.token_at(offset)
        if not token or token.kind not in {"identifier", "section"}:
            return None
        matches = self.resolve(document, offset, token.value)
        if matches:
            _, symbol = matches[0]
            value = "```eel2\n" + symbol.detail + "\n```"
        else:
            builtin = BUILTINS.get(token.value.lower())
            if not builtin:
                return None
            labels = [builtin["detail"]]
            if token.value.lower() in OVERLOADS:
                labels = [builtin["label"] + "(" + ", ".join(params) + ")"
                          for params in OVERLOADS[token.value.lower()]]
            value = "```eel2\n" + "\n".join(labels) + "\n```\n\n" + builtin["documentation"]["value"]
        return dict(contents=dict(kind="markdown", value=value), range=document.range(token.start, token.end))

    def definition(self, document, offset):
        for name, token in document.imports:
            if token.start <= offset <= token.end:
                uri = self.import_uri(document, name)
                if uri and self.read(uri):
                    return [dict(uri=uri, range=dict(start=dict(line=0, character=0),
                                                    end=dict(line=0, character=0)))]
                return []
        token = document.identifier_at(offset)
        if not token or token.kind != "identifier":
            return []
        return [dict(uri=source.uri, range=source.range(s.token.start, s.token.end))
                for source, s in self.resolve(document, offset, token.value)]

    def signature(self, document, offset):
        active = document.token_at(offset)
        if active and active.kind in {"comment", "string", "header", "import", "preprocessor"}:
            return None
        stack, previous = [], None
        for token in document.tokens:
            if token.start >= offset:
                break
            if token.kind == "section":
                stack, previous = [], None
                continue
            if token.kind in {"comment", "string", "header", "import", "preprocessor"}:
                continue
            if token.value in ("(", "["):
                name = previous.value if previous and previous.kind == "identifier" and token.value == "(" else None
                stack.append([token.value, name, 0])
            elif token.value in (")", "]") and stack:
                stack.pop()
            elif token.value == "," and stack:
                stack[-1][2] += 1
            previous = token
        for _, name, argument in reversed(stack):
            if not name:
                continue
            matches = self.resolve(document, offset, name, kind=12)
            if matches:
                symbol = matches[0][1]
                label, params, documentation = symbol.detail, symbol.parameters, None
                variants = [params]
            else:
                builtin = BUILTINS.get(name.lower())
                if not builtin or builtin["parameters"] is None:
                    continue
                label, params, documentation = builtin["detail"], builtin["parameters"], builtin["documentation"]
                variants = OVERLOADS.get(name.lower(), [params])
            signatures = []
            for variant in variants:
                variant_label = label if len(variants) == 1 else name + "(" + ", ".join(variant) + ")"
                signature = dict(label=variant_label, parameters=[dict(label=p) for p in variant])
                if documentation:
                    signature["documentation"] = documentation
                signatures.append(signature)
            active_signature = next((i for i, variant in enumerate(variants)
                                     if argument < len(variant)), len(variants) - 1)
            count = len(variants[active_signature])
            result = dict(signatures=signatures, activeSignature=active_signature)
            if count:
                result["activeParameter"] = min(argument, count - 1)
            return result
        return None
