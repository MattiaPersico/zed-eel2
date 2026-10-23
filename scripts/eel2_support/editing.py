"""Conservative, client-applied edits. This module never writes source files."""

import re

from .catalog import BUILTINS


class EditError(ValueError):
    pass


def format_document(document, options):
    """Normalize indentation without changing tokens, line endings or opaque text."""
    if document.preprocessed or any(i['severity'] == 1 for i in document.issues):
        return []
    width = options.get('tabSize', 2)
    width = max(1, min(8, width)) if isinstance(width, int) else 2
    unit = ' ' * width if options.get('insertSpaces', True) else '\t'
    protected, line_tokens, comment_lines = set(), {}, set()
    for token in document.tokens:
        first = document.position(token.start)['line']
        last = document.position(max(token.start, token.end - 1))['line']
        if token.kind == 'comment':
            comment_lines.update(range(first, last + 1))
        if token.kind in {'header', 'import', 'preprocessor', 'section'} or last > first:
            protected.update(range(first, last + 1))
        if token.kind not in {'header', 'import', 'preprocessor', 'section', 'string', 'comment'}:
            line_tokens.setdefault(first, []).append(token)
    edits, depth = [], 0
    section_lines = {document.position(t.start)['line'] for t in document.sections}
    for line, raw in enumerate(document.text.splitlines(keepends=True)):
        content = raw.rstrip('\r\n')
        if line in section_lines:
            depth = 0
        tokens = line_tokens.get(line, [])
        closing = 0
        for token in tokens:
            if token.value not in (')', ']'):
                break
            closing += 1
        if line not in protected:
            stripped = content.lstrip(' \t')
            desired = unit * max(0, depth - closing) + stripped if stripped else ''
            # Preserve comment text exactly; only remove trailing whitespace on code.
            if line not in comment_lines:
                desired = desired.rstrip(' \t')
            if desired != content:
                start = document.starts[line]
                edits.append(dict(range=document.range(start, start + len(content)), newText=desired))
        for token in tokens:
            if token.value in ('(', '['):
                depth += 1
            elif token.value in (')', ']'):
                depth = max(0, depth - 1)
    return edits


def rename_target(workspace, document, offset):
    token = document.identifier_at(offset)
    if not token or document.preprocessed or document.issues:
        raise EditError('Rename requires a structurally complete, non-preprocessed document.')
    contexts = workspace.contexts(document)
    selected = []
    for root, docs in contexts:
        if any(d.canonical_uri == document.canonical_uri for d in docs):
            selected.extend((key, start, end) for key, start, end, _ in workspace.bindings(document, token, root, docs)
                            if start <= offset < end or offset == token.end == end)
    keys = {key for key, _, _ in selected}
    if len(keys) != 1:
        raise EditError('Rename is unavailable: this name has more than one meaning in the workspace.')
    key = next(iter(keys))
    if key[0] not in {'local', 'function', 'global'}:
        raise EditError('Rename of instance members or dynamic namespaces requires runtime alias analysis.')
    _, start, end = selected[0]
    old_name = document.text[start:end]
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', old_name) or old_name.lower() in BUILTINS:
        raise EditError('Built-in names, slider numbers and qualified names cannot be renamed.')
    if re.fullmatch(r'slider\d+|spl\d+|reg\d+', old_name, re.I):
        raise EditError('Host variable names cannot be renamed.')
    relevant = {}
    for root, docs in contexts:
        if key[0] == 'local':
            docs = [d for d in docs if d.canonical_uri == key[1]]
        elif key[0] == 'global' and root.canonical_uri != key[1]:
            continue
        elif key[0] == 'function' and not any(d.canonical_uri == key[1] for d in docs):
            continue
        for source in docs:
            relevant[source.canonical_uri] = source
    if key[0] != 'local':
        if not workspace.roots or not workspace.scan_complete:
            raise EditError('Project rename needs a complete workspace scan. Open a smaller project or adjust exclusions.')
        if key[0] == 'global' and any(root.canonical_uri != key[1] and
            any(d.canonical_uri in relevant for d in docs) for root, docs in contexts):
            raise EditError('This global belongs to a shared import used by multiple effects; rename is unavailable.')
        for source in relevant.values():
            if source.preprocessed or source.issues or not workspace.imports_complete(source):
                raise EditError('Project rename is blocked by incomplete source, preprocessing or unresolved imports.')
            if any(re.search(r'\{\s*' + re.escape(old_name) + r'\s*\}', t.value, re.I)
                   for t in source.tokens if t.kind == 'string'):
                raise EditError('A formatted string refers to this name; rename it manually to preserve string semantics.')
            for occurrence in source.code:
                if occurrence.kind != 'identifier' or occurrence.value.lower().rsplit('.', 1)[-1] != old_name.lower():
                    continue
                if '..' in occurrence.value:
                    raise EditError('Parent-relative namespaces make this rename ambiguous.')
                if key[0] == 'function' and source.is_call(occurrence):
                    bindings = workspace.bindings(source, occurrence, document, list(relevant.values()))
                    if not bindings or any(b[0][0] == 'namespace-member' for b in bindings):
                        raise EditError('An ambiguous or dynamic call may refer to this function; rename is unavailable.')
        if key[0] == 'function':
            source = relevant[key[1]]
            scope = source.scope_at(key[2])
            if scope and (any(s.storage == 'instance' for s in scope.variables.values()) or
                          any(t.value.lower().startswith('this.') for t in source.code
                              if scope.start <= t.start < scope.end)):
                raise EditError('This function uses its instance namespace; renaming it could change persistent state names.')
    return key, start, end, old_name, relevant, contexts


def prepare_rename(workspace, document, offset):
    try:
        _, start, end, name, _, _ = rename_target(workspace, document, offset)
        return dict(range=document.range(start, end), placeholder=name)
    except EditError:
        return None


def rename(workspace, document, offset, new_name, versioned=False):
    key, start, end, old_name, sources, contexts = rename_target(workspace, document, offset)
    if not isinstance(new_name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', new_name):
        raise EditError('Use a simple EEL2 identifier: letters, digits and underscores, starting with a letter or underscore.')
    if new_name.lower() in BUILTINS or re.fullmatch(r'slider\d+|spl\d+|reg\d+|this|globals', new_name, re.I):
        raise EditError('The new name is reserved by EEL2 or JSFX.')
    scope = document.scope_at(offset) if key[0] == 'local' else None
    if new_name.lower() != old_name.lower():
        for source in sources.values():
            for token in source.code + [s.token for s in source.symbols]:
                if scope and not (scope.start <= token.start < scope.end):
                    continue
                parts = token.value.lower().split('.')
                if token.kind == 'identifier' and new_name.lower() in parts:
                    raise EditError('The new name is already used in this scope; rename would risk a collision.')
    locations = workspace.references(document, offset, True, lexical=True, reference_contexts=contexts)
    if not locations:
        raise EditError('No unambiguous references found.')
    changes, documents = {}, {}
    for location in locations:
        source = workspace.read(location['uri'])
        if source is None:
            raise EditError('A source file changed or became unavailable. Retry the rename.')
        original = sources.get(source.canonical_uri)
        if original is None or source.text != original.text or source.version != original.version:
            raise EditError('A source file changed during analysis. Retry the rename.')
        changes.setdefault(source.uri, []).append(dict(range=location['range'], newText=new_name))
        documents[source.uri] = source
    if versioned:
        return dict(documentChanges=[dict(textDocument=dict(uri=uri, version=documents[uri].version), edits=edits)
                                     for uri, edits in sorted(changes.items())])
    return dict(changes=changes)
