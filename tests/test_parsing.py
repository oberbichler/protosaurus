import json
import pytest

from base64 import b64decode
from deepdiff import DeepDiff


if __name__ == '__main__':
    pytest.main()


def assert_json_equals(actual_json, expected):
    __tracebackhide__ = True
    actual = json.loads(actual_json)
    assert DeepDiff(actual, expected) == {}

def assert_msg_equals(actual_msg, expected):
    __tracebackhide__ = True
    assert actual_msg == b64decode(expected)


@pytest.fixture(params=[
    # field_type, message, expected_data
    ('bool', 'CAE=', True),
    ('int32', 'CAc=', 7),
    ('int64', 'CAc=', '7'),
    ('uint32', 'CAc=', 7),
    ('uint64', 'CAc=', '7'),
    ('float', 'DZqZ+UA=', 7.8),
    ('double', 'CTMzMzMzMx9A', 7.8),
    ('string', 'CgV2YWx1ZQ==', 'value'),
    ('repeated bool', 'CgMBAAE=', [True, False, True]),
    ('repeated int32', 'CgMHCAk=', [7, 8, 9]),
    ('repeated int64', 'CgMHCAk=', ['7', '8', '9']),
    ('repeated uint32', 'CgMHCAk=', [7, 8, 9]),
    ('repeated uint64', 'CgMHCAk=', ['7', '8', '9']),
    ('repeated float', 'CgyamflAZmYOQQAAEEE=', [7.8, 8.9, 9.0]),
    ('repeated double', 'ChgzMzMzMzMfQM3MzMzMzCFAAAAAAAAAIkA=', [7.8, 8.9, 9.0]),
    ('repeated string', 'CgFBCgFCCgFD', ['A', 'B', 'C']),
    ], ids=lambda d: d[0])
def simple_values(request):
    return request.param


def test_to_json_simple_values(ctx, simple_values):
    field_type, message, expected_data = simple_values

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_json = ctx.to_json('test', b64decode(message))

    assert_json_equals(actual_json, {'data': expected_data})

def test_from_json_simple_values(ctx, simple_values):
    field_type, expected_message, data = simple_values

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_msg = ctx.from_json('test', json.dumps({'data': data}))

    assert_msg_equals(actual_msg, expected_message)


@pytest.fixture(params=[
    # field_type, message, expected_data
    ('options', 'CAE=', 'B'),
    ('repeated options', 'CgMBAAI=', ['B', 'A', 'C']),
    ], ids=lambda d: d[0])
def enums(request):
    return request.param


def test_to_json_enum(ctx, enums):
    field_type, message, expected_data = enums

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        enum options {{
            A = 0;
            B = 1;
            C = 2;
        }}
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_json = ctx.to_json('test', b64decode(message))

    assert_json_equals(actual_json, {'data': expected_data})

def test_from_json_enum(ctx, enums):
    field_type, expected_message, data = enums

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        enum options {{
            A = 0;
            B = 1;
            C = 2;
        }}
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_msg = ctx.from_json('test', json.dumps({'data': data}))

    assert_msg_equals(actual_msg, expected_message)


@pytest.fixture(params=[
    # field_type, message, expected_data
    ('nested', 'CgIIBw==', {'data': 7}),
    ('repeated nested', 'CgIIBwoCCAgKAggJ', [{'data': 7}, {'data': 8}, {'data': 9}]),
    ], ids=lambda d: d[0])
def messages(request):
    return request.param


def test_to_json_messages(ctx, messages):
    field_type, message, expected_data = messages

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        message nested {{
            int32 data = 1;
        }}
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_json = ctx.to_json('test', b64decode(message))

    assert_json_equals(actual_json, {'data': expected_data})

def test_from_json_messages(ctx, messages):
    field_type, expected_message, data = messages

    ctx.add_proto('test',
        f"""
        syntax = "proto3";
        message nested {{
            int32 data = 1;
        }}
        message test {{
            {field_type} data = 1;
        }}
        """)
    
    actual_msg = ctx.from_json('test', json.dumps({'data': data}))

    assert_msg_equals(actual_msg, expected_message)


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


def test_map(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            map<string, int32> data = 1;
        }
        """)
    
    actual_json = ctx.to_json('test', b64decode('CgUKAUEQAQoFCgFCEAIKBQoBQxAD'))

    assert_json_equals(actual_json, {'data': {'A': 1, 'B': 2, 'C': 3}})


def test_oneof(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            oneof data {
                string text = 1;
                int32 number = 2;
            }
        }
        """)
    
    actual_json = ctx.to_json('test', b64decode('EAc='))

    assert_json_equals(actual_json, {'number': 7})
    
    actual_json = ctx.to_json('test', b64decode('CgVzZXZlbg=='))

    assert_json_equals(actual_json, {'text': 'seven'})
