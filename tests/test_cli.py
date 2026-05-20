import pytest

from io import BytesIO

from protosaurus.cli import _read_byte, _read_varint, _read_index_array


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
