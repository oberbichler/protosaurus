import pytest

from base64 import b64decode


if __name__ == "__main__":
    pytest.main()


def test_invalid_proto(ctx):
    with pytest.raises(RuntimeError, match='Could not parse proto'):
        ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            data;
        }
        """)

def test_invalid_message_type(ctx):
    with pytest.raises(RuntimeError, match='Could not find descriptor for message type "invalid type"'):
        ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            bool data = 1;
        }
        """)

        ctx.to_json('invalid type', b64decode('CAE='))

def test_invalid_data(ctx):
    with pytest.raises(RuntimeError, match='Could not parse value in buffer'):
        ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            bool data = 1;
        }
        """)

        ctx.to_json('test', b'invalid data')