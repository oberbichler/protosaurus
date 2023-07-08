import json
import pytest

from protosaurus import Context
from base64 import b64decode


if __name__ == "__main__":
    pytest.main()


@pytest.fixture
def ctx():
    return Context()


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
    
    actual = json.loads(ctx.to_json('test', b64decode(data)))

    assert actual['data'] == expected


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
    
    actual = json.loads(ctx.to_json('test', b64decode('CAE=')))

    assert actual['data'] == "B"

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
    
    actual = json.loads(ctx.to_json('test', b64decode('CgMBAAI=')))

    assert actual['data'] == ['B', 'A', 'C']


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
    
    actual = json.loads(ctx.to_json('test', b64decode('CgIIBw==')))

    assert actual['data']['data'] == 7

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
    
    actual = json.loads(ctx.to_json('test', b64decode('CgIIBwoCCAgKAggJ')))

    assert len(actual['data']) == 3
    assert actual['data'][0]['data'] == 7
    assert actual['data'][1]['data'] == 8
    assert actual['data'][2]['data'] == 9


def test_import(ctx):
    ctx.add_proto('diet.proto',
        """
        syntax = "proto3";
        enum Diet {
            carnivorous = 0;
            herbivorous = 1;
        }
        """)
    
    ctx.add_proto('dino.proto',
        """
        syntax = "proto3";
        import "diet.proto";
        message Dino {
            string name = 1;
            Diet diet = 2;
            double length = 3;
        }
        """)
    
    actual = json.loads(ctx.to_json('Dino', b64decode('CglJZ3Vhbm9kb24QARkAAAAAAAAkQA==')))

    assert actual['name'] == 'Iguanodon'
    assert actual['diet'] == 'herbivorous'
    assert actual['length'] == 10