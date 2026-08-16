import json

import pytest

if __name__ == '__main__':
    pytest.main()


_ORDER_PROTO = """
    syntax = "proto3";
    message Order {
        int64 order_id = 1;
        string customer_name = 2;
        Status status = 3;
        repeated string tags = 4;
        optional string note = 5;
    }
    enum Status {
        STATUS_UNKNOWN = 0;
        STATUS_SHIPPED = 1;
    }
    """


@pytest.fixture
def order_ctx(ctx):
    ctx.add_proto('order', _ORDER_PROTO)
    return ctx


def encode(ctx, data):
    """Build a wire-format payload from a JSON dict."""
    return ctx.from_json('Order', json.dumps(data))


# include_defaults


def test_to_json_omits_defaults_by_default(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = json.loads(order_ctx.to_json('Order', data))

    assert actual == {'orderId': '7'}


def test_include_defaults_prints_implicit_presence_fields(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = json.loads(order_ctx.to_json('Order', data, include_defaults=True))

    assert actual['customerName'] == ''
    assert actual['status'] == 'STATUS_UNKNOWN'


def test_include_defaults_prints_empty_repeated_fields(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = json.loads(order_ctx.to_json('Order', data, include_defaults=True))

    assert actual['tags'] == []


def test_include_defaults_omits_unset_optional_field(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = json.loads(order_ctx.to_json('Order', data, include_defaults=True))

    assert 'note' not in actual


def test_include_defaults_keeps_explicitly_set_empty_optional_field(order_ctx):
    data = encode(order_ctx, {'orderId': '7', 'note': ''})

    actual = json.loads(order_ctx.to_json('Order', data, include_defaults=True))

    assert actual['note'] == ''


# pretty


def test_pretty_adds_whitespace(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = order_ctx.to_json('Order', data, pretty=True)

    assert '\n' in actual
    assert json.loads(actual) == {'orderId': '7'}


def test_output_is_compact_without_pretty(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = order_ctx.to_json('Order', data)

    assert '\n' not in actual


# proto_field_names


def test_proto_field_names_keeps_snake_case(order_ctx):
    data = encode(order_ctx, {'orderId': '7', 'customerName': 'ACME'})

    actual = json.loads(order_ctx.to_json('Order', data, proto_field_names=True))

    assert actual == {'order_id': '7', 'customer_name': 'ACME'}


# enums_as_ints


def test_enums_as_ints_prints_number(order_ctx):
    data = encode(order_ctx, {'status': 'STATUS_SHIPPED'})

    actual = json.loads(order_ctx.to_json('Order', data, enums_as_ints=True))

    assert actual == {'status': 1}


def test_enums_are_names_by_default(order_ctx):
    data = encode(order_ctx, {'status': 'STATUS_SHIPPED'})

    actual = json.loads(order_ctx.to_json('Order', data))

    assert actual == {'status': 'STATUS_SHIPPED'}


# unquote_int64


def test_int64_is_quoted_by_default(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    actual = json.loads(order_ctx.to_json('Order', data))

    assert actual['orderId'] == '7'


def test_unquote_int64_emits_number_when_exactly_representable(order_ctx):
    data = encode(order_ctx, {'orderId': '4503599627370496'})  # 2^52

    actual = json.loads(order_ctx.to_json('Order', data, unquote_int64=True))

    assert actual['orderId'] == 4503599627370496


def test_unquote_int64_keeps_string_when_not_representable(order_ctx):
    data = encode(order_ctx, {'orderId': '9007199254740993'})  # 2^53 + 1

    actual = json.loads(order_ctx.to_json('Order', data, unquote_int64=True))

    assert actual['orderId'] == '9007199254740993'


# combinations and argument handling


def test_options_combine(order_ctx):
    data = encode(order_ctx, {'status': 'STATUS_SHIPPED'})

    actual = json.loads(
        order_ctx.to_json(
            'Order', data, include_defaults=True, proto_field_names=True, enums_as_ints=True
        )
    )

    assert actual['order_id'] == '0'
    assert actual['customer_name'] == ''
    assert actual['status'] == 1


def test_options_are_keyword_only(order_ctx):
    data = encode(order_ctx, {'orderId': '7'})

    with pytest.raises(TypeError):
        order_ctx.to_json('Order', data, True)


# from_json: ignore_unknown_fields


def test_from_json_rejects_unknown_fields_by_default(order_ctx):
    with pytest.raises(RuntimeError, match='no such field'):
        order_ctx.from_json('Order', json.dumps({'orderId': '7', 'nope': 1}))


def test_ignore_unknown_fields_accepts_them(order_ctx):
    data = order_ctx.from_json(
        'Order', json.dumps({'orderId': '7', 'nope': 1}), ignore_unknown_fields=True
    )

    assert json.loads(order_ctx.to_json('Order', data)) == {'orderId': '7'}


def test_ignore_unknown_fields_keeps_the_known_ones(order_ctx):
    data = order_ctx.from_json(
        'Order',
        json.dumps({'orderId': '7', 'customerName': 'ACME', 'nope': 1}),
        ignore_unknown_fields=True,
    )

    assert json.loads(order_ctx.to_json('Order', data)) == {
        'orderId': '7',
        'customerName': 'ACME',
    }


def test_ignore_unknown_fields_does_not_mask_other_errors(order_ctx):
    # a malformed value must still be reported even while unknown fields pass
    with pytest.raises(RuntimeError, match='invalid'):
        order_ctx.from_json(
            'Order', json.dumps({'orderId': 'not a number'}), ignore_unknown_fields=True
        )


def test_ignore_unknown_fields_is_keyword_only(order_ctx):
    with pytest.raises(TypeError):
        order_ctx.from_json('Order', '{}', True)


def test_from_json_roundtrips_with_option_off(order_ctx):
    data = order_ctx.from_json('Order', json.dumps({'orderId': '7'}))

    assert json.loads(order_ctx.to_json('Order', data)) == {'orderId': '7'}
