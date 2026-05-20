import pytest

from base64 import b64decode


if __name__ == "__main__":
    pytest.main()


def test_invalid_proto(ctx):
    with pytest.raises(RuntimeError, match=r'Could not parse proto:\n\d+:\d+:') as exc_info:
        ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            data;
        }
        """)

    assert 'Could not parse proto' in str(exc_info.value)


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


def test_from_json_invalid_message_type(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            bool data = 1;
        }
        """)

    with pytest.raises(RuntimeError, match='Could not find descriptor for message type "nonexistent"'):
        ctx.from_json('nonexistent', '{"data": true}')


def test_from_json_invalid_json(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            bool data = 1;
        }
        """)

    with pytest.raises(RuntimeError, match='Could not convert json to message'):
        ctx.from_json('test', 'not valid json')