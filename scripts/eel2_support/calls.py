"""Conservative static call hierarchy; never execute code or infer runtime aliases."""

import hashlib

from .language import uri_path

MAX_TOKENS = 262144
MAX_CALL_SITES = 16384
MAX_RESOLUTIONS = 32768
MAX_RESULTS = 256
MAX_RANGES = 2048


class StaleItem(ValueError):
    pass


def analyzable(document):
    return not document.preprocessed and not any(i['severity'] == 1 for i in document.issues)


def revision(document):
    # Documents are replaced, not mutated, after text changes.
    if not hasattr(document, '_call_revision'):
        document._call_revision = hashlib.sha256(document.text.encode('utf-8')).hexdigest()
    return document._call_revision


def node_key(node):
    document, kind, start = node
    return document.canonical_uri, kind, start


def item(node):
    document, kind, start = node
    path = uri_path(document.uri)
    label = path.name if path else document.uri
    if kind == 'function':
        symbol = document.declarations.get(start)
        if not symbol or symbol.kind != 12:
            return None
        scope = document.scope_at(start)
        if not scope:
            return None
        name, detail, symbol_kind = symbol.name, symbol.detail + ' — ' + label, 12
        first, end, selection_end = scope.start, symbol.end, symbol.token.end
    elif kind == 'section':
        section = next((s for s in document.sections if s.start == start), None)
        if section is None:
            return None
        name, detail, symbol_kind = section.value, section.value + ' — ' + label, 2
        first, selection_end = start, section.end
        end = next((s.start for s in document.sections if s.start > start), len(document.text))
    elif kind == 'file' and start == 0:
        name, detail, symbol_kind = label, label + ' — Top-level EEL2 calls', 2
        first = selection_end = 0
        end = document.sections[0].start if document.sections else len(document.text)
    else:
        return None
    return dict(name=name, kind=symbol_kind, detail=detail, uri=document.uri,
                range=document.range(first, end), selectionRange=document.range(start, selection_end),
                data=dict(kind=kind, offset=start, revision=revision(document)))


def static_target(workspace, document, token, sources):
    scope = document.scope_at(token.start)
    name = token.value.lower()
    if scope:
        local = document.local_symbol(scope, name)
        if name.startswith('this.') or (local and local.storage == 'namespace' and '.' in name):
            return None
    matches = workspace.resolve(document, token.start, name, kind=12, sources=sources)
    if len(matches) != 1 or not analyzable(matches[0][0]):
        return None
    source, symbol = matches[0]
    return source, 'function', symbol.token.start


def prepare(workspace, document, offset):
    if not document or not analyzable(document):
        return []
    token = document.identifier_at(offset)
    if token and document.is_call(token):
        target = static_target(workspace, document, token, [document] + workspace.dependencies(document))
        prepared = item(target) if target else None
        return [prepared] if prepared else []
    token = document.token_at(offset)
    if token and token.kind == 'section':
        return [item((document, 'section', token.start))]
    return []


def restore(workspace, supplied):
    if not isinstance(supplied, dict) or not isinstance(supplied.get('uri'), str):
        return None
    data = supplied.get('data')
    if not isinstance(data, dict) or type(data.get('offset')) is not int:
        return None
    document = workspace.read(supplied['uri'])
    if document is None or not analyzable(document) or data.get('revision') != revision(document):
        raise StaleItem('Source changed or is unavailable; reopen the call hierarchy.')
    node = document, data.get('kind'), data['offset']
    current = item(node)
    if not current or current['name'] != supplied.get('name') or current['selectionRange'] != supplied.get('selectionRange'):
        raise StaleItem('The selected symbol changed; reopen the call hierarchy.')
    return node


def calls(workspace, supplied, incoming):
    workspace.scan_complete = True
    selected = restore(workspace, supplied)
    if selected is None:
        return []
    selected_key = node_key(selected)
    contexts = workspace.contexts(selected[0])
    occurrences, records = {}, {}
    token_count = resolutions = 0
    for root, sources in contexts:
        for source in sources:
            if not analyzable(source):
                workspace.scan_complete = False
                continue
            if source.canonical_uri not in occurrences:
                token_count += len(source.code)
                if token_count > MAX_TOKENS:
                    workspace.scan_complete = False
                    return []
                functions = {source.scope_at(s.token.start).start: s for s in source.symbols
                             if s.kind == 12 and source.scope_at(s.token.start)}
                found = []
                for token in source.code:
                    if token.kind != 'identifier' or token.start in source.declarations or not source.is_call(token):
                        continue
                    scope = source.scope_at(token.start)
                    if scope:
                        symbol = functions.get(scope.start)
                        if symbol is None:
                            continue
                        owner = source, 'function', symbol.token.start
                    else:
                        section = next((s for s in reversed(source.sections) if s.start <= token.start), None)
                        owner = (source, 'section', section.start) if section else (source, 'file', 0)
                    key = source.canonical_uri, token.start
                    if len(records) >= MAX_CALL_SITES:
                        workspace.scan_complete = False
                        return []
                    records[key] = (owner, token, {})
                    found.append(key)
                occurrences[source.canonical_uri] = found
            for key in occurrences[source.canonical_uri]:
                resolutions += 1
                if resolutions > MAX_RESOLUTIONS:
                    workspace.scan_complete = False
                    return []
                owner, token, targets = records[key]
                target = static_target(workspace, source, token, sources)
                targets[node_key(target) if target else None] = target
    groups = {}
    for owner, token, targets in records.values():
        # A shared include can resolve differently in separate effects. Do not
        # present one possible target as a definite static call.
        if len(targets) != 1 or None in targets:
            continue
        target_key, target = next(iter(targets.items()))
        if (target_key if incoming else node_key(owner)) != selected_key:
            continue
        other = owner if incoming else target
        key = node_key(other)
        node, spans = groups.setdefault(key, (other, set()))
        spans.add((token.start, token.end))
    result, ranges_left = [], MAX_RANGES
    for key, (other, spans) in sorted(groups.items()):
        if len(result) >= MAX_RESULTS or ranges_left <= 0:
            workspace.scan_complete = False
            break
        ordered = sorted(spans)
        if len(ordered) > ranges_left:
            ordered = ordered[:ranges_left]
            workspace.scan_complete = False
        ranges_left -= len(ordered)
        caller = other[0] if incoming else selected[0]
        prepared = item(other)
        if prepared:
            result.append({('from' if incoming else 'to'): prepared,
                           'fromRanges': [caller.range(a, b) for a, b in ordered]})
    return result
