<p align="center">
  <img src="logo.png" alt="Protosaurus" width="200">
</p>

# Protosaurus

Parse and create Protobuf messages at runtime in Python — no `protoc` required. Also includes a CLI to deserialize Protobuf from Kafka using `kcat` and a schema registry.

[![CI][actions-ci-badge]][actions-ci-link]
[![Wheels][actions-wheels-badge]][actions-wheels-link]
[![PyPI][pypi-badge]][pypi-link]
[![Python][python-badge]][pypi-link]
[![License][license-badge]][license-link]

[actions-ci-link]: https://github.com/oberbichler/protosaurus/actions/workflows/ci.yml
[actions-ci-badge]: https://github.com/oberbichler/protosaurus/actions/workflows/ci.yml/badge.svg
[actions-wheels-link]: https://github.com/oberbichler/protosaurus/actions/workflows/wheels.yml
[actions-wheels-badge]: https://github.com/oberbichler/protosaurus/actions/workflows/wheels.yml/badge.svg
[pypi-link]: https://pypi.org/project/protosaurus/
[pypi-badge]: https://img.shields.io/pypi/v/protosaurus
[python-badge]: https://img.shields.io/pypi/pyversions/protosaurus
[license-badge]: https://img.shields.io/pypi/l/protosaurus
[license-link]: https://github.com/oberbichler/protosaurus/blob/main/LICENSE

## Installation

Requires Python >= 3.12.

```bash
uv add protosaurus
```

Or using pip:

```bash
pip install protosaurus
```

## Usage

### Parse and serialize Protobuf in Python

Protosaurus can parse `.proto` definitions at runtime without using `protoc`. This allows Protobuf byte arrays to be converted to JSON and vice versa. The `Context` object is thread-safe and can be shared across threads.

```python
import json
from protosaurus import Context
from base64 import b64decode

# create a context which stores the proto schemas
ctx = Context()

# add protos by specifying name and content
ctx.add_proto('diet.proto',
    """
    syntax = "proto3";
    enum Diet {
        carnivorous = 0;
        herbivorous = 1;
    }
    """)

# the proto can be imported via the specified name
ctx.add_proto('animal.proto',
    """
    syntax = "proto3";
    import "diet.proto";
    message Animal {
        string name = 1;
        Diet diet = 2;
        double length = 3;
    }
    """)

# convert a message from base64 string...
data = ctx.to_json('Animal', b64decode('CglJZ3Vhbm9kb24QARkAAAAAAAAkQA=='))

# ...or hex string
data = ctx.to_json('Animal', bytes.fromhex('0a09496775616e6f646f6e1001190000000000002440'))

print(data)
# >>> '{"name":"Iguanodon","diet":"herbivorous","length":10}'


# fields left at their default are omitted...
data = ctx.to_json('Animal', b64decode('CglJZ3Vhbm9kb24='))

print(data)
# >>> '{"name":"Iguanodon"}'

# ...unless they are requested explicitly
data = ctx.to_json('Animal', b64decode('CglJZ3Vhbm9kb24='), include_defaults=True)

print(data)
# >>> '{"name":"Iguanodon","diet":"carnivorous","length":0}'


# convert json to protobuf
data = ctx.from_json('Animal', json.dumps({"name":"Iguanodon","diet":"herbivorous","length":10}))

print(data)
# >>> b'\n\tIguanodon\x10\x01\x19\x00\x00\x00\x00\x00\x00$@'
```

`to_json` accepts the following keyword-only options, all `False` by default:

| Option              | Effect                                                                                                                                                                                                                                   |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `include_defaults`  | Print fields that do not track presence even when they hold their default: implicit-presence scalars, empty lists and empty maps. Fields with explicit presence (proto3 `optional`, submessages, oneof members) stay omitted when unset. |
| `pretty`            | Indent and line-break the output instead of emitting a single line.                                                                                                                                                                      |
| `proto_field_names` | Keep the field names as written in the `.proto` instead of lowerCamelCase.                                                                                                                                                               |
| `enums_as_ints`     | Print enum values as numbers instead of their names.                                                                                                                                                                                     |
| `unquote_int64`     | Print 64-bit integers unquoted when the value round-trips through a double. Values that would lose precision stay quoted, so the JSON type of a field depends on its value.                                                              |

`from_json` accepts one keyword-only option:

| Option | Effect |
| --- | --- |
| `ignore_unknown_fields` | Accept JSON fields the schema does not define instead of failing. Useful when a producer has already moved to a newer schema than the one at hand. |

```python
# fails: the schema has no such field
ctx.from_json('Animal', '{"name":"Iguanodon","colour":"green"}')

# succeeds, the unknown field is dropped
ctx.from_json('Animal', '{"name":"Iguanodon","colour":"green"}', ignore_unknown_fields=True)
```

### Read varints from the wire format

`read_varint` decodes a single base-128 varint out of a `bytes` object and returns the value together with the position just after it, so consecutive reads need no state of their own:

```python
from protosaurus import read_varint

data = b'\xac\x02\x08'

value, offset = read_varint(data)          # (300, 2)
value, offset = read_varint(data, offset)  # (8, 3)
```

Pass `zigzag=True` for the `sint32`/`sint64` encoding, which maps signed values onto unsigned ones. Field tags, lengths, `int32`, `int64`, `uint64`, `bool` and enums are **not** zigzag encoded, so the default is off:

```python
read_varint(b'\xac\x02')                # (300, 2)
read_varint(b'\xac\x02', zigzag=True)   # (150, 2)
```

Malformed input is rejected rather than read on indefinitely: data ending mid-varint raises `EOFError`, more than ten bytes raises `RuntimeError`, and an offset past the end raises `IndexError`.

### Deserialize Protobuf from Kafka using a schema registry

Protosaurus also ships a CLI that can deserialize Protobuf messages from Kafka automatically when a schema registry is available:

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | protosaurus - --schema-registry <url>
```

To disable SSL certificate verification (e.g. for self-signed certificates), pass `--no-verify`:

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | protosaurus - --schema-registry <url> --no-verify
```

The JSON output options above are available as flags: `--defaults`, `--pretty`,
`--proto-field-names`, `--enums-as-ints` and `--unquote-int64`.

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | protosaurus - --schema-registry <url> --defaults --pretty
```

Using [uvx](https://docs.astral.sh/uv/guides/tools/) (no installation required):

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | uvx protosaurus - --schema-registry <url>
```

## License

ISC License — see [LICENSE](LICENSE) for details.
