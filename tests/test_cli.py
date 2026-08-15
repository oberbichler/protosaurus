import json
import struct
from io import BytesIO

import pytest
from click.testing import CliRunner

from protosaurus import cli
from protosaurus.cli import (
    _format_record,
    _read_byte,
    _read_index_array,
    _read_varint,
    main,
)

if __name__ == "__main__":
    pytest.main()


# --- _read_byte ---


def test_read_byte():
    buf = BytesIO(b"\x42")
    assert _read_byte(buf) == 0x42


def test_read_byte_eof():
    buf = BytesIO(b"")
    with pytest.raises(EOFError, match="Unexpected EOF encountered"):
        _read_byte(buf)


# --- _read_varint (zigzag-encoded) ---


def test_read_varint_zero():
    # zigzag(0) = 0 -> varint byte 0x00
    buf = BytesIO(b"\x00")
    assert _read_varint(buf) == 0


def test_read_varint_positive():
    # zigzag(1) = 2 -> varint byte 0x02
    buf = BytesIO(b"\x02")
    assert _read_varint(buf) == 1


def test_read_varint_negative():
    # zigzag(-1) = 1 -> varint byte 0x01
    buf = BytesIO(b"\x01")
    assert _read_varint(buf) == -1


def test_read_varint_larger_positive():
    # zigzag(150) = 300 -> varint bytes 0xAC, 0x02
    buf = BytesIO(b"\xac\x02")
    assert _read_varint(buf) == 150


def test_read_varint_larger_negative():
    # zigzag(-150) = 299 -> varint bytes 0xAB, 0x02
    buf = BytesIO(b"\xab\x02")
    assert _read_varint(buf) == -150


def test_read_varint_eof():
    # multi-byte varint truncated: high bit set but no continuation
    buf = BytesIO(b"\x80")
    with pytest.raises(EOFError, match="Unexpected EOF while reading index"):
        _read_varint(buf)


def test_read_varint_max_length_is_accepted():
    # 10 bytes is the maximum length of a varint64
    buf = BytesIO(b"\xff" * 9 + b"\x01")
    assert _read_varint(buf) == -9223372036854775808


def test_read_varint_too_long():
    # 11 continuation bytes must be rejected instead of read indefinitely
    buf = BytesIO(b"\x80" * 11 + b"\x01")
    with pytest.raises(RuntimeError, match="Varint is too long"):
        _read_varint(buf)


# --- _read_index_array ---


def test_read_index_array_size_zero():
    # size=0 (zigzag(0)=0, varint byte 0x00) -> returns [0]
    buf = BytesIO(b"\x00")
    assert _read_index_array(buf) == [0]


def test_read_index_array_single_element():
    # size=1 (zigzag(1)=2, varint 0x02), element=3 (zigzag(3)=6, varint 0x06)
    buf = BytesIO(b"\x02\x06")
    assert _read_index_array(buf) == [3]


def test_read_index_array_multiple_elements():
    # size=3 (zigzag(3)=6, varint 0x06)
    # elements: 0 (0x00), 1 (0x02), 2 (0x04)
    buf = BytesIO(b"\x06\x00\x02\x04")
    assert _read_index_array(buf) == [0, 1, 2]


def test_read_index_array_negative_size():
    # size=-1 (zigzag(-1)=1, varint 0x01) -> RuntimeError
    buf = BytesIO(b"\x01")
    with pytest.raises(RuntimeError, match="Invalid Protobuf message_index array length"):
        _read_index_array(buf)


# --- _format_record ---


def test_format_record_plain():
    result = _format_record("42", "user-1", '{"name":"Iguanodon","length":10}')
    assert json.loads(result) == {
        "@offset": 42,
        "@key": "user-1",
        "name": "Iguanodon",
        "length": 10,
    }


def test_format_record_escapes_quotes_in_key():
    result = _format_record("7", 'he said "hi"', '{"name":"Rex"}')
    assert json.loads(result) == {"@offset": 7, "@key": 'he said "hi"', "name": "Rex"}


def test_format_record_escapes_newline_and_backslash_in_key():
    result = _format_record("7", "a\\b\nc", '{"name":"Rex"}')
    assert json.loads(result) == {"@offset": 7, "@key": "a\\b\nc", "name": "Rex"}


def test_format_record_offset_is_numeric():
    result = _format_record("123", "k", "{}")
    assert json.loads(result)["@offset"] == 123


def test_format_record_preserves_key_order():
    result = _format_record("1", "k", '{"z":1}')
    assert list(json.loads(result).keys()) == ["@offset", "@key", "z"]


def test_format_record_is_single_line_by_default():
    result = _format_record("1", "k", '{"z":1}')
    assert "\n" not in result


def test_format_record_pretty_indents_output():
    result = _format_record("1", "k", '{"z":1}', pretty=True)
    assert "\n" in result
    assert json.loads(result) == {"@offset": 1, "@key": "k", "z": 1}


# --- CLI json output options ---

_ORDER_PROTO = """
    syntax = "proto3";
    message Order {
        int64 order_id = 1;
        string customer_name = 2;
        Status status = 3;
        repeated string tags = 4;
    }
    enum Status {
        STATUS_UNKNOWN = 0;
        STATUS_SHIPPED = 1;
    }
    """

_SCHEMA_ID = 7


def _frame(offset, key, payload):
    """Build one record in the format main() reads."""
    raw = struct.pack(">bI", 0, _SCHEMA_ID) + b"\x00" + payload
    return f"{offset}\n{key}\n".encode() + struct.pack(">I", len(raw)) + raw


@pytest.fixture
def order_cli(tmp_path, monkeypatch, ctx):
    """Wire the CLI to a fixed schema and return a runner for a single record."""
    monkeypatch.setattr(cli, "_schema_cache", {})
    monkeypatch.setattr(cli, "_session", None)

    ctx.add_proto("<<<MAIN>>>", _ORDER_PROTO)
    monkeypatch.setattr(cli, "_get_schema_by_id", lambda url, id, verify_ssl=True: ctx)

    def run(message, *options):
        payload = ctx.from_json("Order", json.dumps(message))
        path = tmp_path / "records.bin"
        path.write_bytes(_frame("42", "user-1", payload))

        result = CliRunner().invoke(
            main, [str(path), "--schema-registry", "http://registry", *options]
        )
        assert result.exit_code == 0, result.output
        return result.output

    return run


def test_cli_omits_default_fields_without_flag(order_cli):
    record = json.loads(order_cli({"orderId": "7"}))

    assert "customerName" not in record


def test_cli_defaults_flag_includes_default_fields(order_cli):
    record = json.loads(order_cli({"orderId": "7"}, "--defaults"))

    assert record["customerName"] == ""
    assert record["tags"] == []


def test_cli_proto_field_names_flag_keeps_snake_case(order_cli):
    record = json.loads(order_cli({"orderId": "7"}, "--proto-field-names"))

    assert record["order_id"] == "7"


def test_cli_enums_as_ints_flag_prints_number(order_cli):
    record = json.loads(order_cli({"status": "STATUS_SHIPPED"}, "--enums-as-ints"))

    assert record["status"] == 1


def test_cli_unquote_int64_flag_prints_number(order_cli):
    record = json.loads(order_cli({"orderId": "7"}, "--unquote-int64"))

    assert record["orderId"] == 7


def test_cli_pretty_flag_indents_output(order_cli):
    output = order_cli({"orderId": "7"}, "--pretty")

    assert "\n" in output.strip()
    assert json.loads(output)["orderId"] == "7"


def test_cli_output_is_single_line_without_pretty(order_cli):
    output = order_cli({"orderId": "7"})

    assert output.strip().count("\n") == 0


def test_cli_record_metadata_survives_options(order_cli):
    record = json.loads(order_cli({"orderId": "7"}, "--defaults", "--proto-field-names"))

    assert record["@offset"] == 42
    assert record["@key"] == "user-1"
