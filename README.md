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

[actions-ci-link]:         https://github.com/oberbichler/protosaurus/actions/workflows/ci.yml
[actions-ci-badge]:        https://github.com/oberbichler/protosaurus/actions/workflows/ci.yml/badge.svg
[actions-wheels-link]:     https://github.com/oberbichler/protosaurus/actions/workflows/wheels.yml
[actions-wheels-badge]:    https://github.com/oberbichler/protosaurus/actions/workflows/wheels.yml/badge.svg
[pypi-link]:               https://pypi.org/project/protosaurus/
[pypi-badge]:              https://img.shields.io/pypi/v/protosaurus
[python-badge]:            https://img.shields.io/pypi/pyversions/protosaurus
[license-badge]:           https://img.shields.io/pypi/l/protosaurus
[license-link]:            https://github.com/oberbichler/protosaurus/blob/main/LICENSE

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


# convert json to protobuf
data = ctx.from_json('Animal', json.dumps({"name":"Iguanodon","diet":"herbivorous","length":10}))

print(data)
# >>> b'\n\tIguanodon\x10\x01\x19\x00\x00\x00\x00\x00\x00$@'
```

### Deserialize Protobuf from Kafka using a schema registry

Protosaurus also ships a CLI that can deserialize Protobuf messages from Kafka automatically when a schema registry is available:

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | protosaurus - --schema-registry <url>
```

To disable SSL certificate verification (e.g. for self-signed certificates), pass `--no-verify`:

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | protosaurus - --schema-registry <url> --no-verify
```

Using [uvx](https://docs.astral.sh/uv/guides/tools/) (no installation required):

```bash
kcat -C -e -F <kafka.config> -t <topic> -f "%o\\n%k\\n%R%s" | uvx protosaurus - --schema-registry <url>
```

## License

ISC License — see [LICENSE](LICENSE) for details.
