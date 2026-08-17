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

    with pytest.raises(ImportError, match=r'pyarrow'):
        importlib.import_module('protosaurus.arrow')


def test_unknown_type_propagates_describe_error(ctx):
    with pytest.raises(RuntimeError, match='Could not find'):
        derive_schema(ctx, 'Nonexistent')
