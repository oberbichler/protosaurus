from protosaurus import Context

try:
    import pyarrow as pa
except ImportError as e:
    raise ImportError(
        'pyarrow is required for protosaurus.arrow; '
        'install it with `pip install protosaurus[arrow]`.'
    ) from e


_SCALAR_ARROW_TYPES: dict[str, pa.DataType] = {
    'int32': pa.int32(),
    'sint32': pa.int32(),
    'sfixed32': pa.int32(),
    'int64': pa.int64(),
    'sint64': pa.int64(),
    'sfixed64': pa.int64(),
    'uint32': pa.uint32(),
    'fixed32': pa.uint32(),
    'uint64': pa.uint64(),
    'fixed64': pa.uint64(),
    'float': pa.float32(),
    'double': pa.float64(),
    'bool': pa.bool_(),
    'string': pa.string(),
    'bytes': pa.binary(),
}

_ENUM_ARROW_TYPE: pa.DataType = pa.dictionary(pa.int32(), pa.string())


def derive_schema(ctx: Context, type_name: str, *, max_depth: int | None = None) -> pa.Schema:
    """
    Derive a pyarrow Schema for the message type `type_name` from `ctx`.

    Nested message types are resolved recursively into struct fields. A
    self-referential message raises RuntimeError naming the cycle unless
    `max_depth` is given, which caps recursion depth (root is depth 0) and
    drops fields that would exceed it instead of raising.
    """
    fields = _struct_fields(ctx, type_name, (type_name,), max_depth)
    return pa.schema(fields)


def _struct_fields(
    ctx: Context, type_name: str, path: tuple[str, ...], max_depth: int | None
) -> list[pa.Field]:
    message = ctx.describe(type_name)

    if message['kind'] != 'message':
        raise RuntimeError(
            f'Cannot derive an Arrow schema for "{type_name}": it is an enum, not a message.'
        )

    fields = []
    for field in message['fields']:
        arrow_field = _arrow_field(ctx, field, path, max_depth)
        if arrow_field is not None:
            fields.append(arrow_field)

    return fields


def _arrow_field(
    ctx: Context, field: dict, path: tuple[str, ...], max_depth: int | None
) -> pa.Field | None:
    arrow_type = _arrow_type(ctx, field, path, max_depth)

    if arrow_type is None:
        return None

    if field['label'] == 'repeated' and field['type'] != 'map':
        arrow_type = pa.list_(pa.field('item', arrow_type, nullable=False))

    nullable = field['label'] != 'required'
    return pa.field(field['name'], arrow_type, nullable=nullable)


def _arrow_type(
    ctx: Context, field: dict, path: tuple[str, ...], max_depth: int | None
) -> pa.DataType | None:
    kind = field['type']

    if kind == 'map':
        return _map_type(ctx, field, path, max_depth)

    if kind in ('message', 'group'):
        return _message_type(ctx, field['type_name'], path, max_depth)

    if kind == 'enum':
        return _ENUM_ARROW_TYPE

    return _SCALAR_ARROW_TYPES[kind]


def _message_type(
    ctx: Context, type_name: str, path: tuple[str, ...], max_depth: int | None
) -> pa.StructType | None:
    prospective_depth = len(path)

    # These two checks are mutually exclusive by design, not just by
    # coincidence -- do not merge them into a single `if/elif` chain keyed on
    # `max_depth is not None and prospective_depth > max_depth`. Once
    # max_depth is set, depth alone decides whether to truncate; the cycle
    # check must never run in that mode, or a cycle within the depth budget
    # would incorrectly raise instead of being truncated once it exceeds it.
    if max_depth is not None:
        if prospective_depth > max_depth:
            return None
    elif type_name in path:
        cycle_path = (*path, type_name)
        cycle = ' -> '.join(f'"{p}"' for p in cycle_path)
        raise RuntimeError(
            f'Cannot derive an Arrow schema for "{path[0]}": {cycle} is a cycle. '
            'Pass max_depth=N to derive_schema() to cut the recursion off explicitly.'
        )

    fields = _struct_fields(ctx, type_name, (*path, type_name), max_depth)
    return pa.struct(fields)


def _map_type(
    ctx: Context, field: dict, path: tuple[str, ...], max_depth: int | None
) -> pa.MapType | None:
    key_type = _SCALAR_ARROW_TYPES[field['key_type']]
    value_type = _value_type(ctx, field, path, max_depth)

    if value_type is None:
        return None

    return pa.map_(key_type, value_type)


def _value_type(
    ctx: Context, field: dict, path: tuple[str, ...], max_depth: int | None
) -> pa.DataType | None:
    value_kind = field['value_type']

    if value_kind == 'message':
        return _message_type(ctx, field['value_type_name'], path, max_depth)

    if value_kind == 'enum':
        return _ENUM_ARROW_TYPE

    return _SCALAR_ARROW_TYPES[value_kind]
