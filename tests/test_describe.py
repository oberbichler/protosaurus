import pytest

_ZOO_PROTO = """
    syntax = "proto3";
    package zoo;

    message Animal {
        string name = 1;
        optional string nickname = 2;
        Diet diet = 3;
        Person trainer = 4;
        repeated string tags = 5;
        map<string, string> attributes = 6;
        map<string, Person> friends = 7;

        oneof location {
            int32 cage_id = 8;
            int32 zone_id = 9;
        }
    }

    message Person {
        string name = 1;
    }

    enum Diet {
        CARNIVOROUS = 0;
        HERBIVOROUS = 1;
    }
    """


@pytest.fixture
def zoo_ctx(ctx):
    ctx.add_proto('zoo', _ZOO_PROTO)
    return ctx


def field(fields, name):
    """Find a field dict by name in a describe() fields list."""
    return next(f for f in fields if f['name'] == name)


# message shape


def test_describe_message_reports_name_and_kind(zoo_ctx):
    result = zoo_ctx.describe('zoo.Animal')

    assert result['name'] == 'zoo.Animal'
    assert result['kind'] == 'message'


def test_describe_scalar_field(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'name')

    assert f['type'] == 'string'
    assert f['number'] == 1
    assert f['json_name'] == 'name'
    assert f['label'] == 'optional'
    assert f['has_presence'] is False
    assert f['oneof'] is None


def test_describe_proto3_optional_field_has_presence_without_oneof(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'nickname')

    assert f['has_presence'] is True
    assert f['oneof'] is None


def test_describe_enum_field(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'diet')

    assert f['type'] == 'enum'
    assert f['type_name'] == 'zoo.Diet'
    assert f['enum_values'] == [
        {'name': 'CARNIVOROUS', 'number': 0},
        {'name': 'HERBIVOROUS', 'number': 1},
    ]


def test_describe_message_field(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'trainer')

    assert f['type'] == 'message'
    assert f['type_name'] == 'zoo.Person'
    assert 'enum_values' not in f


def test_describe_repeated_scalar_field(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'tags')

    assert f['type'] == 'string'
    assert f['label'] == 'repeated'


def test_describe_map_with_scalar_value(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'attributes')

    assert f['type'] == 'map'
    assert f['key_type'] == 'string'
    assert f['value_type'] == 'string'
    assert 'value_type_name' not in f


def test_describe_map_with_message_value(zoo_ctx):
    f = field(zoo_ctx.describe('zoo.Animal')['fields'], 'friends')

    assert f['type'] == 'map'
    assert f['key_type'] == 'string'
    assert f['value_type'] == 'message'
    assert f['value_type_name'] == 'zoo.Person'


def test_describe_real_oneof_group(zoo_ctx):
    fields = zoo_ctx.describe('zoo.Animal')['fields']

    assert field(fields, 'cage_id')['oneof'] == 'location'
    assert field(fields, 'zone_id')['oneof'] == 'location'


# enum type, described directly


def test_describe_enum_type_directly(zoo_ctx):
    result = zoo_ctx.describe('zoo.Diet')

    assert result == {
        'name': 'zoo.Diet',
        'kind': 'enum',
        'values': [
            {'name': 'CARNIVOROUS', 'number': 0},
            {'name': 'HERBIVOROUS', 'number': 1},
        ],
    }


# scalar type vocabulary


_SCALAR_PROTO = """
    syntax = "proto3";
    message Scalars {
        double f_double = 1;
        float f_float = 2;
        int32 f_int32 = 3;
        int64 f_int64 = 4;
        uint32 f_uint32 = 5;
        uint64 f_uint64 = 6;
        sint32 f_sint32 = 7;
        sint64 f_sint64 = 8;
        fixed32 f_fixed32 = 9;
        fixed64 f_fixed64 = 10;
        sfixed32 f_sfixed32 = 11;
        sfixed64 f_sfixed64 = 12;
        bool f_bool = 13;
        string f_string = 14;
        bytes f_bytes = 15;
    }
    """


@pytest.fixture
def scalars_ctx(ctx):
    ctx.add_proto('scalars', _SCALAR_PROTO)
    return ctx


@pytest.mark.parametrize('field_name,expected_type', [
    ('f_double', 'double'),
    ('f_float', 'float'),
    ('f_int32', 'int32'),
    ('f_int64', 'int64'),
    ('f_uint32', 'uint32'),
    ('f_uint64', 'uint64'),
    ('f_sint32', 'sint32'),
    ('f_sint64', 'sint64'),
    ('f_fixed32', 'fixed32'),
    ('f_fixed64', 'fixed64'),
    ('f_sfixed32', 'sfixed32'),
    ('f_sfixed64', 'sfixed64'),
    ('f_bool', 'bool'),
    ('f_string', 'string'),
    ('f_bytes', 'bytes'),
])
def test_describe_scalar_type_names(scalars_ctx, field_name, expected_type):
    f = field(scalars_ctx.describe('Scalars')['fields'], field_name)

    assert f['type'] == expected_type


# proto2 required


def test_describe_proto2_required_field(ctx):
    ctx.add_proto('legacy', """
        syntax = "proto2";
        message Legacy {
            required int32 needed = 1;
        }
        """)

    f = field(ctx.describe('Legacy')['fields'], 'needed')

    assert f['label'] == 'required'


# self-referential message: describe() must not recurse


def test_describe_self_referential_message_does_not_recurse(ctx):
    ctx.add_proto('tree', """
        syntax = "proto3";
        package tree;
        message Node {
            Node child = 1;
        }
        """)

    f = field(ctx.describe('tree.Node')['fields'], 'child')

    assert f['type'] == 'message'
    assert f['type_name'] == 'tree.Node'


# unknown type


def test_describe_unknown_type_lists_known_types(zoo_ctx):
    with pytest.raises(RuntimeError) as exc_info:
        zoo_ctx.describe('zoo.Nonexistent')

    message = str(exc_info.value)
    assert 'zoo.Animal' in message
    assert 'zoo.Diet' in message
