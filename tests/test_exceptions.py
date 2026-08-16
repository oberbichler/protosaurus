import re
from base64 import b64decode

import pytest

if __name__ == "__main__":
    pytest.main()


_SIMPLE_PROTO = """
    syntax = "proto3";
    package zoo;
    message Animal {
        bool data = 1;
    }
    """


@pytest.fixture
def zoo(ctx):
    ctx.add_proto("zoo", _SIMPLE_PROTO)
    return ctx


# --- add_proto ---


def test_invalid_proto(ctx):
    with pytest.raises(RuntimeError, match=r"Could not parse proto:\n\d+:\d+:"):
        ctx.add_proto(
            "test",
            """
            syntax = "proto3";
            message test {
                data;
            }
            """,
        )


def test_missing_import_is_reported(ctx):
    # BuildFile used to log this to stderr and raise a message that said nothing.
    with pytest.raises(RuntimeError) as exc_info:
        ctx.add_proto(
            "test",
            """
            syntax = "proto3";
            import "nowhere.proto";
            message test {
                bool data = 1;
            }
            """,
        )

    assert "nowhere.proto" in str(exc_info.value)


def test_unresolved_field_type_is_reported(ctx):
    with pytest.raises(RuntimeError) as exc_info:
        ctx.add_proto(
            "test",
            """
            syntax = "proto3";
            message test {
                NoSuchType data = 1;
            }
            """,
        )

    assert "NoSuchType" in str(exc_info.value)


def test_duplicate_symbol_is_reported(ctx):
    ctx.add_proto("a", _SIMPLE_PROTO)

    with pytest.raises(RuntimeError) as exc_info:
        ctx.add_proto("b", _SIMPLE_PROTO)

    assert "zoo.Animal" in str(exc_info.value)


# --- unknown message type ---


def test_to_json_unknown_type_names_the_type(zoo):
    with pytest.raises(RuntimeError, match=re.escape('"Animal"')):
        zoo.to_json("Animal", b64decode("CAE="))


def test_to_json_unknown_type_lists_known_types(zoo):
    # The usual cause is a missing package prefix, so show what is registered.
    with pytest.raises(RuntimeError) as exc_info:
        zoo.to_json("Animal", b64decode("CAE="))

    assert "zoo.Animal" in str(exc_info.value)


def test_from_json_unknown_type_lists_known_types(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.from_json("nonexistent", '{"data": true}')

    assert "zoo.Animal" in str(exc_info.value)


# --- from_json: protobuf's own diagnosis must survive ---


def test_from_json_unknown_field_is_named(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.from_json("zoo.Animal", '{"dta": true}')

    message = str(exc_info.value)
    assert "no such field" in message
    assert "dta" in message


def test_from_json_unparseable_number_is_explained(ctx):
    ctx.add_proto("zoo", 'syntax = "proto3"; package zoo; message Counter { int32 n = 1; }')

    with pytest.raises(RuntimeError) as exc_info:
        ctx.from_json("zoo.Counter", '{"n": "abc"}')

    message = str(exc_info.value)
    assert "invalid number" in message
    assert "abc" in message


def test_from_json_truncated_input_is_explained(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.from_json("zoo.Animal", '{"data":')

    assert "EOF" in str(exc_info.value)


def test_from_json_error_has_no_double_spaces(zoo):
    # protobuf composes these messages from pieces and leaves doubled blanks.
    with pytest.raises(RuntimeError) as exc_info:
        zoo.from_json("zoo.Animal", '{"dta": true}')

    assert "  " not in str(exc_info.value)


# --- to_json: wire format ---


def test_to_json_malformed_buffer_names_type_and_size(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.to_json("zoo.Animal", b"\xff\xff\xff\xff")

    message = str(exc_info.value)
    assert "zoo.Animal" in message
    assert "4" in message


def test_to_json_missing_required_field_is_named(ctx):
    ctx.add_proto(
        "p2",
        """
        syntax = "proto2";
        message Legacy {
            required int32 needed = 1;
        }
        """,
    )

    with pytest.raises(RuntimeError) as exc_info:
        ctx.to_json("Legacy", b"")

    assert "needed" in str(exc_info.value)


def test_from_json_missing_required_field_is_named(ctx):
    ctx.add_proto(
        "p2",
        """
        syntax = "proto2";
        message Legacy {
            required int32 needed = 1;
        }
        """,
    )

    with pytest.raises(RuntimeError) as exc_info:
        ctx.from_json("Legacy", "{}")

    assert "needed" in str(exc_info.value)


# --- message_type_from_index ---


def test_index_empty_names_the_file(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.message_type_from_index("zoo", [])

    assert "zoo" in str(exc_info.value)


def test_unknown_file_is_named(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.message_type_from_index("elsewhere", [0])

    assert "elsewhere" in str(exc_info.value)


def test_index_out_of_range_shows_value_and_range(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.message_type_from_index("zoo", [7])

    message = str(exc_info.value)
    assert "7" in message
    # exactly one top-level message is defined
    assert "1" in message


def test_nested_index_out_of_range_shows_position(zoo):
    with pytest.raises(RuntimeError) as exc_info:
        zoo.message_type_from_index("zoo", [0, 3])

    message = str(exc_info.value)
    assert "position 1" in message
    assert "3" in message
