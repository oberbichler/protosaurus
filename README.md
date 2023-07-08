# Protosaurus

Parse ProtoBuffer messages at runtime.

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

# the specified names can be used for imports (like filenames)
ctx.add_proto('dino.proto',
    """
    syntax = "proto3";
    import "diet.proto";
    message Dino {
        string name = 1;
        Diet diet = 2;
        double length = 3;
    }
    """)

# convert a message from base64 string...
data = ctx.to_json('Dino', b64decode('CglJZ3Vhbm9kb24QARkAAAAAAAAkQA=='))

# ...or hex string
data = ctx.to_json('Dino', bytes.fromhex('0a09496775616e6f646f6e1001190000000000002440'))

print(data)
# >>> {"name":"Iguanodon","diet":"herbivorous","length":10}
```