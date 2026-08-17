import importlib
import sys

import pytest

pytest.importorskip('pyarrow')

import pyarrow as pa

from protosaurus.arrow import derive_schema

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


def arrow_field(schema, name):
    return schema.field(name)


@pytest.mark.parametrize('field_name,expected_type', [
    ('f_double', pa.float64()),
    ('f_float', pa.float32()),
    ('f_int32', pa.int32()),
    ('f_int64', pa.int64()),
    ('f_uint32', pa.uint32()),
    ('f_uint64', pa.uint64()),
    ('f_sint32', pa.int32()),
    ('f_sint64', pa.int64()),
    ('f_fixed32', pa.uint32()),
    ('f_fixed64', pa.uint64()),
    ('f_sfixed32', pa.int32()),
    ('f_sfixed64', pa.int64()),
    ('f_bool', pa.bool_()),
    ('f_string', pa.string()),
    ('f_bytes', pa.binary()),
])
def test_scalar_type_mapping(scalars_ctx, field_name, expected_type):
    schema = derive_schema(scalars_ctx, 'Scalars')

    assert arrow_field(schema, field_name).type == expected_type


def test_scalar_field_is_nullable_by_default(scalars_ctx):
    schema = derive_schema(scalars_ctx, 'Scalars')

    assert arrow_field(schema, 'f_int32').nullable is True


def test_proto2_required_field_is_not_nullable(ctx):
    ctx.add_proto('legacy', """
        syntax = "proto2";
        message Legacy {
            required int32 needed = 1;
        }
        """)

    schema = derive_schema(ctx, 'Legacy')

    assert arrow_field(schema, 'needed').nullable is False


def test_import_without_pyarrow_raises_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, 'pyarrow', None)
    monkeypatch.delitem(sys.modules, 'protosaurus.arrow', raising=False)

    with pytest.raises(ImportError, match=r'protosaurus\[arrow\]'):
        importlib.import_module('protosaurus.arrow')


def test_unknown_type_propagates_describe_error(ctx):
    with pytest.raises(RuntimeError, match='Could not find'):
        derive_schema(ctx, 'Nonexistent')


def test_enum_type_name_raises_clear_error(full_zoo_ctx):
    with pytest.raises(RuntimeError, match='it is an enum, not a message'):
        derive_schema(full_zoo_ctx, 'fullzoo.Diet')


_ZOO_PROTO = """
    syntax = "proto3";
    package zoo;

    message Animal {
        string name = 1;
        Person trainer = 2;
    }

    message Person {
        string name = 1;
    }
    """


@pytest.fixture
def zoo_ctx(ctx):
    ctx.add_proto('zoo', _ZOO_PROTO)
    return ctx


def test_nested_message_becomes_struct(zoo_ctx):
    schema = derive_schema(zoo_ctx, 'zoo.Animal')

    trainer_type = arrow_field(schema, 'trainer').type

    assert pa.types.is_struct(trainer_type)
    assert trainer_type.field('name').type == pa.string()


def test_self_referential_message_without_max_depth_raises(ctx):
    ctx.add_proto('tree', """
        syntax = "proto3";
        package tree;
        message Node {
            Node child = 1;
        }
        """)

    with pytest.raises(RuntimeError, match=r'"tree\.Node" -> "tree\.Node" is a cycle'):
        derive_schema(ctx, 'tree.Node')


def test_self_referential_message_with_max_depth_drops_field(ctx):
    ctx.add_proto('tree', """
        syntax = "proto3";
        package tree;
        message Node {
            Node child = 1;
        }
        """)

    schema = derive_schema(ctx, 'tree.Node', max_depth=0)

    assert schema.names == []


def test_max_depth_also_cuts_non_cyclic_nesting(ctx):
    ctx.add_proto('chain', """
        syntax = "proto3";
        package chain;
        message A {
            B b = 1;
        }
        message B {
            C c = 1;
        }
        message C {
            string value = 1;
        }
        """)

    schema = derive_schema(ctx, 'chain.A', max_depth=1)

    b_type = arrow_field(schema, 'b').type
    assert pa.types.is_struct(b_type)
    assert b_type.names == []  # C would be depth 2, dropped


_FULL_ZOO_PROTO = """
    syntax = "proto3";
    package fullzoo;

    message Animal {
        string name = 1;
        Diet diet = 2;
        repeated string tags = 3;
        map<string, string> attributes = 4;
        map<string, Person> friends = 5;

        oneof location {
            int32 cage_id = 6;
            int32 zone_id = 7;
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
def full_zoo_ctx(ctx):
    ctx.add_proto('fullzoo', _FULL_ZOO_PROTO)
    return ctx


def test_enum_field_becomes_dictionary(full_zoo_ctx):
    schema = derive_schema(full_zoo_ctx, 'fullzoo.Animal')

    diet_type = arrow_field(schema, 'diet').type

    assert pa.types.is_dictionary(diet_type)
    assert diet_type.index_type == pa.int32()
    assert diet_type.value_type == pa.string()


def test_repeated_scalar_becomes_non_nullable_list(full_zoo_ctx):
    schema = derive_schema(full_zoo_ctx, 'fullzoo.Animal')

    tags_field = arrow_field(schema, 'tags')

    assert pa.types.is_list(tags_field.type)
    assert tags_field.type.value_type == pa.string()
    assert tags_field.type.value_field.nullable is False


def test_map_with_scalar_value(full_zoo_ctx):
    schema = derive_schema(full_zoo_ctx, 'fullzoo.Animal')

    attributes_type = arrow_field(schema, 'attributes').type

    assert pa.types.is_map(attributes_type)
    assert attributes_type.key_type == pa.string()
    assert attributes_type.item_type == pa.string()


def test_map_with_message_value(full_zoo_ctx):
    schema = derive_schema(full_zoo_ctx, 'fullzoo.Animal')

    friends_type = arrow_field(schema, 'friends').type

    assert pa.types.is_map(friends_type)
    assert friends_type.key_type == pa.string()
    assert pa.types.is_struct(friends_type.item_type)
    assert friends_type.item_type.field('name').type == pa.string()


def test_real_oneof_members_are_independent_nullable_fields(full_zoo_ctx):
    schema = derive_schema(full_zoo_ctx, 'fullzoo.Animal')

    assert arrow_field(schema, 'cage_id').type == pa.int32()
    assert arrow_field(schema, 'cage_id').nullable is True
    assert arrow_field(schema, 'zone_id').type == pa.int32()
    assert arrow_field(schema, 'zone_id').nullable is True
