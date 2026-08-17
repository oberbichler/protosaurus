# Descriptor introspection API — design

## Purpose

`Context` currently only converts messages between the wire format and JSON
(`to_json`, `from_json`) and resolves Confluent message indices
(`message_type_from_index`). There is no way to ask a `Context` what shape a
message or enum type actually has.

This is the first of two planned features. The second — deriving an Apache
Arrow schema from a parsed proto schema — will be designed and specced
separately, built entirely in Python on top of the API described here. This
spec does not need to anticipate Arrow's exact needs beyond staying
general-purpose.

## Scope

Add one new method:

```python
def describe(self, type_name: str) -> dict:
```

`type_name` is a fully qualified message or enum name, resolved the same way
`to_json`'s `message_type` argument is. `describe` returns one level of a
message's or enum's shape: fields with their number, type, label and
presence; enum values inline where they terminate a field. Referencing a
nested message type by name only, rather than embedding it, is the mechanism
that keeps a single call O(1) in schema depth and immune to cycles from
self-referential messages — the caller decides whether and how far to
recurse by calling `describe` again.

Out of scope for this spec: resolving `type_name` transitively into a full
tree, listing all types known to a `Context`, and anything Arrow-specific.

## Return shape

### Message

```python
ctx.describe('zoo.Animal')
# {
#   "name": "zoo.Animal",
#   "kind": "message",
#   "fields": [
#     {
#       "name": "name", "json_name": "name", "number": 1,
#       "type": "string", "label": "optional",
#       "has_presence": False, "oneof": None,
#     },
#     {
#       "name": "diet", "json_name": "diet", "number": 2,
#       "type": "enum", "type_name": "zoo.Diet",
#       "label": "optional", "has_presence": False, "oneof": None,
#       "enum_values": [
#         {"name": "carnivorous", "number": 0},
#         {"name": "herbivorous", "number": 1},
#       ],
#     },
#     {
#       "name": "trainer", "json_name": "trainer", "number": 3,
#       "type": "message", "type_name": "zoo.Person",
#       "label": "optional", "has_presence": True, "oneof": None,
#     },
#     {
#       "name": "tags_by_key", "json_name": "tagsByKey", "number": 4,
#       "type": "map", "key_type": "string", "value_type": "string",
#       "label": "repeated",
#     },
#   ],
# }
```

### Enum

```python
ctx.describe('zoo.Diet')
# {
#   "name": "zoo.Diet",
#   "kind": "enum",
#   "values": [
#     {"name": "carnivorous", "number": 0},
#     {"name": "herbivorous", "number": 1},
#   ],
# }
```

### Field keys

Present on every field:

| Key | Type | Notes |
| --- | --- | --- |
| `name` | `str` | The field name as written in the `.proto`. |
| `json_name` | `str` | protobuf's lowerCamelCase JSON name, mirroring `to_json`'s `proto_field_names` option. |
| `number` | `int` | The field number. |
| `type` | `str` | One of protobuf's own type names (`FieldDescriptor::TypeName()`): `double`, `float`, `int64`, `uint64`, `int32`, `fixed64`, `fixed32`, `bool`, `string`, `group`, `message`, `bytes`, `uint32`, `enum`, `sfixed32`, `sfixed64`, `sint32`, `sint64` — or the synthetic `map` (see below). `group` is legacy proto2 and is exposed as-is (it structurally behaves like `message`); it is not otherwise special-cased. |
| `label` | `str` | `optional`, `required`, or `repeated`, taken directly from `FieldDescriptorProto::Label`. Map fields report `repeated`, matching their underlying representation. |
| `has_presence` | `bool` | Whether the field distinguishes "unset" from "set to the default": proto3 `optional`, submessages, and oneof members are `True`; implicit-presence scalars, and repeated/map fields, are `False`. |
| `oneof` | `str \| None` | The name of the oneof the field belongs to, or `None`. **Synthetic oneofs** (which proto3 generates internally for every `optional` scalar field) are never reported here — only real, multi-member oneof groups. |

Present only when relevant:

| Key | When | Notes |
| --- | --- | --- |
| `type_name` | `type` is `message`, `group`, or `enum` | Fully qualified name of the referenced type. |
| `enum_values` | `type` is `enum` | List of `{"name": str, "number": int}`, in declaration order. Embedded inline rather than requiring a second `describe` call, since enum values are small, finite, and cannot themselves introduce a cycle. |
| `key_type` | `type` is `map` | The map key's protobuf type name (always a scalar or `string`, per protobuf's own restriction on map keys). |
| `value_type` | `type` is `map` | The map value's protobuf type name, using the same vocabulary as `type`. |
| `value_type_name` | `type` is `map` and the value is `message` or `enum` | Fully qualified name of the value type. |

A map field is detected via protobuf's `FieldDescriptor::is_map()` and is
never reported as a `message`-typed `repeated` field pointing at the
synthetic `...MapEntry` type — that implementation detail is fully absorbed
into `type: "map"` plus `key_type`/`value_type`/`value_type_name`.

## Error handling

`describe` looks up `type_name` first as a message, then as an enum. If
neither exists, it raises the same `RuntimeError` shape `to_json` already
uses for an unknown `message_type` — the message plus a listing of known
types. The "known types" listing is extended to include known enum types
alongside known message types, since `describe` can now target either.

## Implementation

### `include/protosaurus/protosaurus.h`

New plain-C++ value types (no nanobind dependency in the header, matching
how `to_json`/`from_json` return `std::string`, not Python objects):

```cpp
struct EnumValueInfo {
  std::string name;
  int number;
};

struct FieldInfo {
  std::string name;
  std::string json_name;
  int number;
  std::string type;
  std::string label;
  bool has_presence;
  std::optional<std::string> oneof;
  std::optional<std::string> type_name;
  std::optional<std::string> key_type;
  std::optional<std::string> value_type;
  std::optional<std::string> value_type_name;
  std::vector<EnumValueInfo> enum_values;  // empty unless type == "enum"
};

struct MessageInfo {
  std::string name;
  std::vector<FieldInfo> fields;
};

struct EnumInfo {
  std::string name;
  std::vector<EnumValueInfo> values;
};

struct DescribeResult {
  bool is_enum;
  MessageInfo message;  // valid iff !is_enum
  EnumInfo enum_info;   // valid iff is_enum
};
```

`Context::describe(const std::string& type_name) -> DescribeResult`:

1. Take `m_mutex` as a shared lock (read-only access to the pool, same as
   `to_json`/`from_json`).
2. Try `m_pool.FindMessageTypeByName`, then `m_pool.FindEnumTypeByName`.
3. On miss, raise `std::runtime_error` via a new
   `throw_unknown_type(type_name)` helper — a generalization of the existing
   `throw_unknown_message_type` that also lists known enum types (collected
   the same way `known_message_types()` walks `m_filenames`, extended to
   also collect `file->enum_type(i)` and nested enums).
4. On a message hit, walk `descriptor->field(i)` for `i` in
   `[0, field_count())` and fill one `FieldInfo` each:
   - `type` from `field->type_name()`.
   - `is_map()` → `type = "map"`, `key_type`/`value_type` from the synthetic
     entry message's `key()`/`value()` fields, `value_type_name` from
     `value()->message_type()` or `value()->enum_type()` when applicable.
   - Otherwise, `message`/`group`/`enum` → `type_name` from
     `field->message_type()->full_name()` or
     `field->enum_type()->full_name()`; `enum` also fills `enum_values` from
     `field->enum_type()`.
   - `oneof` from `field->containing_oneof()`, but only when
     `!field->containing_oneof()->is_synthetic()`.
   - `has_presence` from `field->has_presence()`.
5. On an enum hit, walk `enum_descriptor->value(i)` into `EnumValueInfo`.

### `src/protosaurus_ext.cpp`

A new free function `describe(Context&, const std::string&) -> nb::dict`
that calls `Context::describe`, releasing the GIL for the call (mirroring
`add_proto`/`to_json`/`message_type_from_index`), then — GIL held — builds
the `nb::dict`/`nb::list` result from the returned `DescribeResult`,
producing exactly the shapes in "Return shape" above. Bound as
`Context.describe(type_name: str) -> dict`, with a docstring following the
existing `*_DOC` constant convention.

### `src/protosaurus/protosaurus_ext.pyi`

New `describe` stub on `Context`, documented like the other methods
(purpose, what `type_name` means, what it raises).

### `README.md`

A short "Inspect a parsed schema" subsection under "Usage", with one example
each for a message and an enum, plus a one-line mention of the map/oneof/
presence conventions above.

## Testing

New `tests/test_describe.py`, following the existing suite's fixture/style
(see `tests/test_json_options.py`):

- Every scalar type round-trips to the expected `type` string.
- A message-typed field reports `type_name` and no `enum_values`.
- An enum-typed field reports `type_name` and inline `enum_values` in
  declaration order.
- A `map<string, Animal>`-style field reports `type: "map"` with
  `value_type: "message"` and `value_type_name` set; a
  `map<string, string>` field omits `value_type_name`.
- A real oneof group: both members report the same `oneof` name.
- A proto3 `optional` scalar field: `has_presence: True`, `oneof: None`
  (the synthetic oneof must not leak).
- A proto2 `required` field reports `label: "required"`.
- A plain `repeated` (non-map) field reports `label: "repeated"`.
- `describe` on an enum type directly returns the `kind: "enum"` shape.
- `describe` on an unknown type raises `RuntimeError` listing known types
  (including at least one enum name, to confirm the listing was extended).
- A self-referential message (`message R { R child = 1; }`) — a single
  `describe` call returns immediately with `type_name: "pkg.R"` on the
  `child` field; it must not attempt to resolve it, so there is nothing to
  terminate.

## Follow-up

Once this ships, the Arrow schema derivation gets its own spec and will
consume `describe()` purely from Python — no further native changes implied
by this spec.
