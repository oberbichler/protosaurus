import json
import pytest

from protosaurus import Context
from base64 import b64decode


if __name__ == "__main__":
    pytest.main()


@pytest.fixture
def ctx():
    return Context()


def test_bool(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            bool data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CAE=')))

    assert actual['data']

def test_bool_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated bool data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CgMBAAE=')))

    assert actual['data'] == [True, False, True]


def test_int32(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            int32 data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CAc=')))

    assert actual['data'] == 7

def test_int32_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated int32 data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CgMHCAk=')))

    assert actual['data'] == [7, 8, 9]


def test_uint32(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            uint32 data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CAc=')))

    assert actual['data'] == 7

def test_uint32_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated uint32 data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CgMHCAk=')))

    assert actual['data'] == [7, 8, 9]


def test_int64(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            int64 data = 1;
        }
        """)

    actual = json.loads(ctx.to_json('test', b64decode('CAc=')))

    assert actual['data'] == 7

def test_int64_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated int64 data = 1;
        }
        """)

    actual = json.loads(ctx.to_json('test', b64decode('CgMHCAk=')))

    assert actual['data'] == [7, 8, 9]


def test_uint64(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            uint64 data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CAc=')))

    assert actual['data'] == 7

def test_uint64_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated uint64 data = 1;
        }
        """)

    actual = json.loads(ctx.to_json('test', b64decode('CgMHCAk=')))

    assert actual['data'] == [7, 8, 9]


def test_float(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            float data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('DZqZ+UA=')))

    assert actual['data'] == 7.8

def test_float_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated float data = 1;
        }
        """)

    actual = json.loads(ctx.to_json('test', b64decode('CgyamflAZmYOQQAAEEE=')))

    assert actual['data'] == [7.8, 8.9, 9.0]


def test_double(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            float data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('DZqZ+UA=')))

    assert actual['data'] == 7.8

def test_double_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated double data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('ChgzMzMzMzMfQM3MzMzMzCFAAAAAAAAAIkA=')))

    assert actual['data'] == [7.8, 8.9, 9.0]


def test_string(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            string data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CgV2YWx1ZQ==')))

    assert actual['data'] == 'value'

def test_string_repeated(ctx):
    ctx.add_proto('test',
        """
        syntax = "proto3";
        message test {
            repeated string data = 1;
        }
        """)
    
    actual = json.loads(ctx.to_json('test', b64decode('CgFBCgFCCgFD')))

    assert actual['data'] == ['A', 'B', 'C']


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