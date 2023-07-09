import json
import pytest

from base64 import b64decode
from deepdiff import DeepDiff


if __name__ == "__main__":
    pytest.main()


def assert_json_equals(actual_json, expected):
    __tracebackhide__ = True
    actual = json.loads(actual_json)
    assert DeepDiff(actual, expected) == {}


@pytest.fixture(params=[
    # type, data, expected
    ('bool', 'CAE=', True),
    ('int32', 'CAc=', 7),
    ('int64', 'CAc=', 7),
    ('uint32', 'CAc=', 7),
    ('uint64', 'CAc=', 7),
    ('float', 'DZqZ+UA=', 7.8),
    ('double', 'CTMzMzMzMx9A', 7.8),
    ('string', 'CgV2YWx1ZQ==', 'value'),
    ('repeated bool', 'CgMBAAE=', [True, False, True]),
    ('repeated int32', 'CgMHCAk=', [7, 8, 9]),
    ('repeated int64', 'CgMHCAk=', [7, 8, 9]),
    ('repeated uint32', 'CgMHCAk=', [7, 8, 9]),
    ('repeated uint64', 'CgMHCAk=', [7, 8, 9]),
    ('repeated float', 'CgyamflAZmYOQQAAEEE=', [7.8, 8.9, 9.0]),
    ('repeated double', 'ChgzMzMzMzMfQM3MzMzMzCFAAAAAAAAAIkA=', [7.8, 8.9, 9.0]),
    ('repeated string', 'CgFBCgFCCgFD', ['A', 'B', 'C']),
    ], ids=lambda d: d[0])
def simple_values(request):
    return request.param


def test_simple_values(ctx, simple_values):
    field_type, data, expected = simple_values

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_json = ctx.to_json('test', b64decode(data))

    assert_json_equals(actual_json, {'data': expected})


def test_enum(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        enum options {
            A = 0;
            B = 1;
            C = 2;
        }
        message test {
            options data = 1;
        }
        """)
    
    actual_json = ctx.to_json('test', b64decode('CAE='))

    assert_json_equals(actual_json, {'data': 'B'})

def test_enum_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        enum options {
            A = 0;
            B = 1;
            C = 2;
        }
        message test {
            repeated options data = 1;
        }
        """)
    
    actual_json = ctx.to_json('test', b64decode('CgMBAAI='))

    assert_json_equals(actual_json, {'data': ['B', 'A', 'C']})


def test_message(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message nested {
            int32 data = 1;
        }
        message test {
            nested data = 1;
        }
        """)
    
    actual_json = ctx.to_json('test', b64decode('CgIIBw=='))

    assert_json_equals(actual_json, {'data': {'data': 7}})

def test_message_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message nested {
            int32 data = 1;
        }
        message test {
            repeated nested data = 1;
        }
        """)
    
    actual_json = ctx.to_json('test', b64decode('CgIIBwoCCAgKAggJ'))

    assert_json_equals(actual_json, {'data': [{'data': 7}, {'data': 8}, {'data': 9}]})


def test_import(ctx):
    ctx.add_proto('diet.proto',
        """
        syntax = "proto3";
        enum Diet {
            carnivorous = 0;
            herbivorous = 1;
        }
        """)
    
    ctx.add_proto('animal.proto',
        """
        syntax = "proto3";
        import "diet.proto";
        message Animal {
            string name = 1;
            Diet diet = 2;
            double length = 3;
        }
        """)
    
    actual_json = ctx.to_json('Animal', b64decode('CglJZ3Vhbm9kb24QARkAAAAAAAAkQA=='))

    assert_json_equals(actual_json, {'name': 'Iguanodon', 'diet': 'herbivorous', 'length': 10})
