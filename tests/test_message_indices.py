import pytest


if __name__ == "__main__":
    pytest.main()


def test_message_type_from_index(ctx):
    ctx.add_proto('test',
    """
    syntax = "proto3";

    message main_0 {
        string data = 1;
        
        message nested_0 {
            string data = 1;
        }

        message nested_1 {
            string data = 1;
        }
    }

    message main_1 {
        string data = 1;
        
        message nested_0 {
            string data = 1;
        }
        
        message nested_1 {
            string data = 1;
        }
    }
    """)

    assert ctx.message_type_from_index('test', [0]) == "main_0"
    assert ctx.message_type_from_index('test', [1]) == "main_1"

    assert ctx.message_type_from_index('test', [0, 0]) == "main_0.nested_0"
    assert ctx.message_type_from_index('test', [0, 1]) == "main_0.nested_1"

    assert ctx.message_type_from_index('test', [1, 0]) == "main_1.nested_0"
    assert ctx.message_type_from_index('test', [1, 1]) == "main_1.nested_1"


def test_index_out_of_range_raises(ctx):
    ctx.add_proto('test',
    """
    syntax = "proto3";

    message main_0 {
        string data = 1;
        
        message nested_0 {
            string data = 1;
        }

        message nested_1 {
            string data = 1;
        }
    }
    """)

    with pytest.raises(RuntimeError, match='Index out of range at position 1'):
        ctx.message_type_from_index('test', [0, -1])

    with pytest.raises(RuntimeError, match='Index out of range at position 1'):
        ctx.message_type_from_index('test', [0, 2])
