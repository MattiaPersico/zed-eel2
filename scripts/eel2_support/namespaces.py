"""Bounded static namespace instantiation for navigation, never for automatic edits."""

MAX_INSTANTIATIONS = 128


def expand(name, environment):
    """Expand a namespace using concrete this/namespace-parameter arguments."""
    parts = name.lower().split('.')
    if parts[0] == 'this' or parts[0] in environment:
        base = environment.get(parts.pop(0))
        if base is None:
            return None
        result = base.split('.') if base else []
        for part in parts:
            if not part:
                if result:
                    result.pop()
            else:
                result.append(part)
        return '.'.join(result)
    return name.lower()


def analyze(workspace, root, documents):
    aliases, pending, seen = {}, [], set()
    tokens_by_scope = {}
    for document in documents:
        if document.preprocessed:
            continue
        for token in document.code:
            if token.kind != 'identifier':
                continue
            scope = document.scope_at(token.start)
            if scope:
                tokens_by_scope.setdefault((document.canonical_uri, scope.start), []).append(token)
            elif document.is_call(token):
                pending.append((document, token, {}))

    def add(document, token, key, start=None):
        span = (key, token.start if start is None else start, token.end,
                token.start in document.declarations)
        values = aliases.setdefault((document.canonical_uri, token.start), [])
        if span not in values:
            values.append(span)

    while pending:
        caller, call, environment = pending.pop()
        concrete = expand(call.value, environment)
        if concrete is None:
            continue
        matches = workspace.resolve(caller, call.start, concrete, kind=12, sources=documents)
        if len(matches) != 1:
            continue
        source, function = matches[0]
        if source.preprocessed or '.' in function.name:
            continue
        scope = source.scope_at(function.token.start)
        if not scope:
            continue
        add(caller, call, ('function', source.canonical_uri, function.token.start),
            call.end - len(function.name))
        prefix = concrete[:-len(function.name)].rstrip('.')
        new_environment = {'this': prefix or function.name.lower()}
        index = caller.code_indices[call.start] + 1
        close = caller.pairs.get(index)
        if close is None:
            continue
        args, start, cursor = [], index + 1, index + 1
        while cursor < close:
            if caller.code[cursor].value == ',':
                args.append(caller.code[start:cursor]); start = cursor + 1
            cursor = caller.pairs.get(cursor, cursor) + 1
        args.append(caller.code[start:close])
        for number, parameter in enumerate(function.parameters or []):
            if not parameter.endswith('*'):
                continue
            arg = args[number] if number < len(args) else []
            value = expand(arg[0].value, environment) if len(arg) == 1 and arg[0].kind == 'identifier' else None
            new_environment[parameter[:-1].lower()] = value
        identity = (source.canonical_uri, scope.start, tuple(sorted(new_environment.items())))
        if identity in seen:
            continue
        if len(seen) >= MAX_INSTANTIATIONS:
            return aliases, False
        seen.add(identity)
        for token in tokens_by_scope.get((source.canonical_uri, scope.start), []):
            if token.start == function.token.start:
                continue
            if source.is_call(token):
                pending.append((source, token, new_environment))
                continue
            name = token.value.lower()
            local = source.local_symbol(scope, name)
            if name.startswith('this.'):
                concrete_name = expand(name, new_environment)
            elif local and local.storage == 'instance':
                concrete_name = expand('this.' + name, new_environment)
            elif local and local.storage == 'namespace' and '.' in name:
                concrete_name = expand(name, new_environment)
            else:
                continue
            if concrete_name:
                member = name.split('.', 1)[-1].lstrip('.')
                add(source, token, ('global', root.canonical_uri, concrete_name), token.end - len(member))
    return aliases, True
