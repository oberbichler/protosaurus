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


def derive_schema(ctx: Context, type_name: str, *, max_depth: int | None = None) -> pa.Schema:
    fields = _struct_fields(ctx, type_name, (type_name,), max_depth)
    return pa.schema(fields)


def _struct_fields(
    ctx: Context, type_name: str, path: tuple[str, ...], max_depth: int | None
) -> list[pa.Field]:
    message = ctx.describe(type_name)

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

    if kind in ('message', 'group'):
        return _message_type(ctx, field['type_name'], path, max_depth)

    return _SCALAR_ARROW_TYPES[kind]


def _message_type(
    ctx: Context, type_name: str, path: tuple[str, ...], max_depth: int | None
) -> pa.StructType | None:
    prospective_depth = len(path)

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
