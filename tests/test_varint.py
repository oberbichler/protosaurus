import pytest

from protosaurus import read_varint

if __name__ == "__main__":
    pytest.main()


# --- plain base-128 varints ---


def test_single_byte():
    assert read_varint(b"\x08") == (8, 1)


def test_zero():
    assert read_varint(b"\x00") == (0, 1)


def test_multi_byte():
    # 300 -> 0xAC 0x02
    assert read_varint(b"\xac\x02") == (300, 2)


def test_offset_defaults_to_zero():
    assert read_varint(b"\xac\x02") == read_varint(b"\xac\x02", 0)


def test_reads_at_the_given_offset():
    # a 0x08 hidden behind two bytes of padding
    assert read_varint(b"\xff\xff\x08", 2) == (8, 3)


def test_returned_offset_allows_sequential_reads():
    data = b"\xac\x02\x08"

    first, offset = read_varint(data)
    second, offset = read_varint(data, offset)

    assert (first, second) == (300, 8)
    assert offset == len(data)


def test_trailing_data_is_ignored():
    value, offset = read_varint(b"\x08rest")

    assert value == 8
    assert offset == 1


def test_max_uint64():
    # 2**64 - 1 is the largest varint: nine 0x7f groups plus one bit
    assert read_varint(b"\xff" * 9 + b"\x01") == (2**64 - 1, 10)


# --- zigzag ---


def test_zigzag_zero():
    assert read_varint(b"\x00", zigzag=True) == (0, 1)


def test_zigzag_positive():
    # zigzag(1) = 2
    assert read_varint(b"\x02", zigzag=True) == (1, 1)


def test_zigzag_negative():
    # zigzag(-1) = 1
    assert read_varint(b"\x01", zigzag=True) == (-1, 1)


def test_zigzag_larger_positive():
    # zigzag(150) = 300 -> 0xAC 0x02
    assert read_varint(b"\xac\x02", zigzag=True) == (150, 2)


def test_zigzag_larger_negative():
    # zigzag(-150) = 299 -> 0xAB 0x02
    assert read_varint(b"\xab\x02", zigzag=True) == (-150, 2)


def test_zigzag_min_int64():
    assert read_varint(b"\xff" * 9 + b"\x01", zigzag=True) == (-(2**63), 10)


def test_zigzag_is_keyword_only():
    with pytest.raises(TypeError):
        read_varint(b"\x02", 0, True)


def test_plain_and_zigzag_differ():
    assert read_varint(b"\xac\x02")[0] != read_varint(b"\xac\x02", zigzag=True)[0]


# --- errors ---


def test_empty_input_raises_eof():
    with pytest.raises(EOFError):
        read_varint(b"")


def test_truncated_varint_raises_eof():
    # continuation bit set but no following byte
    with pytest.raises(EOFError):
        read_varint(b"\x80")


def test_offset_at_end_raises_eof():
    with pytest.raises(EOFError):
        read_varint(b"\x08", 1)


def test_offset_past_end_raises_index_error():
    with pytest.raises(IndexError):
        read_varint(b"\x08", 5)


def test_too_long_varint_is_rejected():
    # eleven continuation bytes must not be read indefinitely
    with pytest.raises(RuntimeError):
        read_varint(b"\x80" * 11 + b"\x01")


def test_negative_offset_raises_index_error():
    with pytest.raises((IndexError, TypeError, OverflowError)):
        read_varint(b"\x08", -1)
