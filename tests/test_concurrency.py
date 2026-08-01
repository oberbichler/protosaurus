import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from protosaurus import Context

if __name__ == "__main__":
    pytest.main()


ANIMAL_PROTO = """
syntax = "proto3";
message Animal {
    string name = 1;
    int32 diet = 2;
    double length = 3;
}
"""


def test_concurrent_to_json():
    """Many threads converting messages on one shared Context."""
    ctx = Context()
    ctx.add_proto("animal.proto", ANIMAL_PROTO)
    payload = ctx.from_json("Animal", json.dumps({"name": "Iguanodon", "length": 10.0}))

    def work(_):
        return ctx.to_json("Animal", payload)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(work, range(2000)))

    assert len(results) == 2000
    assert all(json.loads(r)["name"] == "Iguanodon" for r in results)


# Each generated proto declares many messages so that BuildFile spends enough time
# inside the critical section for concurrent writers to actually overlap. With a
# single message per proto the call completes too quickly to expose a missing lock:
# verified that 1 message/proto passes even with the write lock removed, while
# 10+ messages/proto aborts reliably in protobuf's descriptor.cc consistency check.
MESSAGES_PER_PROTO = 25


def _generate_proto(index):
    body = "".join(
        f"message M{index}_{j} {{ int32 v = 1; string s = 2; }}\n"
        for j in range(MESSAGES_PER_PROTO)
    )
    return f'syntax = "proto3";\n{body}'


def test_concurrent_add_proto():
    """Concurrent writers extending the descriptor pool."""
    ctx = Context()

    def writer(i):
        ctx.add_proto(f"generated{i}.proto", _generate_proto(i))
        return ctx.message_type_from_index(f"generated{i}.proto", [0])

    with ThreadPoolExecutor(max_workers=16) as pool:
        written = list(pool.map(writer, range(200)))

    assert written == [f"M{i}_0" for i in range(200)]


def test_concurrent_writers_and_readers_interleaved():
    """Writers and readers hitting the same Context at the same time."""
    ctx = Context()
    ctx.add_proto("base.proto", ANIMAL_PROTO)
    payload = ctx.from_json("Animal", json.dumps({"name": "T-Rex"}))

    def task(i):
        if i % 2 == 0:
            ctx.add_proto(f"generated{i}.proto", _generate_proto(i))
            return ctx.message_type_from_index(f"generated{i}.proto", [0])
        return json.loads(ctx.to_json("Animal", payload))["name"]

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(task, range(400)))

    expected = [f"M{i}_0" if i % 2 == 0 else "T-Rex" for i in range(400)]
    assert results == expected


def test_concurrent_round_trip():
    """from_json and to_json interleaved across threads."""
    ctx = Context()
    ctx.add_proto("animal.proto", ANIMAL_PROTO)

    def work(i):
        blob = ctx.from_json("Animal", json.dumps({"name": f"dino-{i}", "diet": 1}))
        return json.loads(ctx.to_json("Animal", blob))["name"]

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(work, range(1000)))

    assert results == [f"dino-{i}" for i in range(1000)]
