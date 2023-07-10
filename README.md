# Protosaurus

Parse and create ProtoBuffer messages at runtime.

[![Pip Action Status][actions-pip-badge]][actions-pip-link]
[![Wheel Action Status][actions-wheels-badge]][actions-wheels-link]
[![PyPi][pypi-badge]][pypi-link]


[actions-pip-link]:        https://github.com/oberbichler/protosaurus/actions?query=workflow%3APip
[actions-pip-badge]:       https://github.com/oberbichler/protosaurus/workflows/Pip/badge.svg
[actions-wheels-link]:     https://github.com/oberbichler/protosaurus/actions?query=workflow%3AWheels
[actions-wheels-badge]:    https://github.com/oberbichler/protosaurus/workflows/Wheels/badge.svg
[pypi-link]:               https://pypi.org/project/protosaurus/
[pypi-badge]:              https://img.shields.io/pypi/v/protosaurus

## Installation

```bash
pip install protosaurus
```

## Usage

```python
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
