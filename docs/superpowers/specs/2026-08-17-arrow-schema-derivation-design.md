# Arrow schema derivation — design

## Purpose

The second of two planned features (see
`2026-08-17-descriptor-introspection-design.md`, part one). Given a
`Context` and a fully qualified message type name, derive a matching
`pyarrow.Schema`. This is meant to make protobuf-encoded data (e.g. from
Kafka, via the existing schema-registry CLI) directly writable to
Arrow/Parquet for analytics, without hand-writing a schema for every proto
message.

This feature is built entirely on top of `describe()` from part one — no
further changes to the native C++/nanobind extension. It lives in its own
optional submodule so that installing protosaurus for JSON conversion or
the Kafka CLI never requires pulling in `pyarrow`.

## Scope

One function:

```python
def derive_schema(ctx: Context, type_name: str, *, max_depth: int | None = None) -> pyarrow.Schema:
```

`type_name` is a fully qualified message name, resolved through `describe()`
exactly like `to_json`'s `message_type` argument. The returned schema's
top-level fields correspond to `type_name`'s fields, in declaration order.

Out of scope: deriving a schema for an enum type directly (enums only ever
appear as fields of a message here), converting actual message *data* into
an Arrow `Table`/`RecordBatch` (only the schema), and any change to
`Context` or the native extension.

## Recursion and cycles

`describe()` only resolves one level per call and never detects cycles
itself (see part one's "Follow-up" note) — that responsibility falls
entirely on `derive_schema`.

`derive_schema` walks message-typed fields by recursively calling
`describe()`, tracking the chain of type names from the root call to the
current field (the current *path*, not a global "already seen" set — two
sibling fields independently referencing the same message type is normal
and not a cycle; only a type reappearing in its own ancestor chain is).

- **No `max_depth` (default):** recursion is unbounded. Ordinary deep (but
  non-cyclic) nesting resolves fully. If a type appears in its own
  ancestor path, `derive_schema` raises `RuntimeError` naming the full
  cycle, e.g.:

  ```
  RuntimeError: Cannot derive an Arrow schema for "zoo.Person": "zoo.Person" -> "zoo.Animal" -> "zoo.Person" is a cycle. Pass max_depth=N to derive_schema() to cut the recursion off explicitly.
  ```

- **`max_depth=N`:** a hard cap on nesting depth from the root, counted in
  message-type levels (the root type is depth 0). This bounds both genuine
  cycles and ordinary deep nesting alike — one mechanism, not two. A
  message-typed field whose resolution would exceed `max_depth` is dropped
  from its containing `struct` entirely (not replaced by a placeholder
  type). This can produce a `struct` with zero fields in extreme cases;
  that is accepted as a documented consequence of an explicit, caller-opted
  cutoff rather than something to special-case.

`max_depth` applies uniformly — it is not "only active once a cycle is
detected." Passing `max_depth=2` truncates a plain 5-level-deep non-cyclic
message just as it would a self-referential one.

## Type mapping

| Protobuf `type` (from `describe()`) | Arrow type |
| --- | --- |
| `int32`, `sint32`, `sfixed32` | `pa.int32()` |
| `int64`, `sint64`, `sfixed64` | `pa.int64()` |
| `uint32`, `fixed32` | `pa.uint32()` |
| `uint64`, `fixed64` | `pa.uint64()` |
| `float` | `pa.float32()` |
| `double` | `pa.float64()` |
| `bool` | `pa.bool_()` |
| `string` | `pa.string()` |
| `bytes` | `pa.binary()` |
| `enum` | `pa.dictionary(pa.int32(), pa.string())` — dictionary values are the enum's value *names* (from `describe()`'s `enum_values`), not their numbers |
| `message`, `group` | `pa.struct([...])`, built by recursively deriving the referenced type's fields (subject to "Recursion and cycles" above) |
| `map` (`describe()`'s synthetic type) | `pa.map_(key_arrow_type, value_arrow_type)`, where `key_arrow_type`/`value_arrow_type` are derived from `key_type`/`value_type`/`value_type_name` using this same table. When the value is a `message`, it participates in the same path-tracked recursion as any other nested message field (see "Recursion and cycles") |

A field whose `label` is `repeated` (and whose `type` is not `map`, which is
already inherently repeated and handled above) is wrapped in
`pa.list_(item_type)`. List items are never nullable — protobuf has no
concept of a null entry inside a repeated field, only an empty list.

A field that belongs to a real (non-synthetic) `oneof` — per `describe()`'s
`oneof` key — is emitted as an ordinary top-level nullable field, exactly
like any other field. No Arrow-level grouping or union type is introduced;
`derive_schema` simply does not treat `oneof` specially beyond reading it
(consistent with how `to_json` already represents oneofs — only the set
member appears). The mutual-exclusion invariant is not represented in the
Arrow schema.

## Nullability and field naming

- `nullable = describe()["label"] != "required"`. Proto2 `required` fields
  are the only non-nullable case; proto3 has no `required`, so every proto3
  field is nullable at the top level regardless of `has_presence`.
- Column names use the `.proto` field name (`describe()`'s `name`, snake_case),
  not `json_name`. This matches how other proto-to-columnar tooling (e.g.
  BigQuery, Spark) names derived columns, and is a more natural fit for SQL
  consumers than `to_json`'s lowerCamelCase default. There is no parameter
  to switch to `json_name` in this version — add one later only if an
  actual need shows up.

## Error handling

- Unknown `type_name`: propagates the same `RuntimeError` `describe()`
  already raises for an unknown type — not re-wrapped.
- Cycle without `max_depth`: `RuntimeError` as shown above.
- `pyarrow` not installed: raises at `import protosaurus.arrow` time (not
  deferred to the first `derive_schema` call), with a message naming the
  extra to install:

  ```
  ImportError: pyarrow is required for protosaurus.arrow; install it with `pip install protosaurus[arrow]`.
  ```

## Implementation

- New pure-Python module `src/protosaurus/arrow.py`. `import pyarrow as pa`
  at module top level — no lazy/deferred import inside `derive_schema` — so
  the `ImportError` above surfaces immediately and predictably on
  `import protosaurus.arrow`, not on first use.
- `derive_schema` is a thin entry point that calls `ctx.describe(type_name)`
  and an internal recursive helper (e.g. `_struct_fields(ctx, type_name,
  path, max_depth)`) that returns the `list[pa.Field]` for one message
  level, calling itself for nested `message`/`group` fields and for a map's
  message-typed value.
- No new dependency for the rest of the package: `pyproject.toml` gets a
  new optional extra:

  ```toml
  [project.optional-dependencies]
  arrow = ["pyarrow >= 14"]
  ```

  (`>= 14` is the floor because `pa.map_` and dictionary-type handling are
  stable from that release onward.)
- `README.md` gets a new "Derive an Arrow schema" subsection under "Usage",
  mirroring the style of the existing sections, with one example showing a
  nested message + enum + repeated field.

## Testing

New `tests/test_arrow.py`, requiring the `arrow` extra (skip the whole file
via `pytest.importorskip("pyarrow")` if it isn't installed, matching how an
optional-dependency test file should behave in a suite that doesn't force
the extra on every environment):

- Every scalar type maps to the expected Arrow type.
- A nested message field becomes `pa.struct(...)` with the right nested
  fields.
- `map<string, string>` and `map<string, Animal>` (message-valued) both
  produce `pa.map_(...)` with the correct key/value types.
- An enum field becomes `pa.dictionary(pa.int32(), pa.string())`.
- A real oneof group's members each appear as independent nullable fields.
- A `repeated` scalar field becomes `pa.list_(...)` with a non-nullable
  item type.
- A proto2 `required` field has `nullable=False`; everything else has
  `nullable=True`.
- A self-referential message without `max_depth` raises `RuntimeError`
  naming the cycle.
- The same self-referential message with `max_depth=N` returns a schema
  where the over-depth field is absent, instead of raising.
- `import protosaurus.arrow` without `pyarrow` installed (simulated, e.g.
  via `sys.modules` patching) raises the documented `ImportError`.

## Follow-up

None planned beyond this — this closes the two-part plan
(`describe()` + `derive_schema()`).
