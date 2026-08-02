import json
import struct
from io import BytesIO

import click
import requests

from protosaurus import Context

# utility: compile protos from schema-registry

_schema_cache = {}
_session = None


def _get_session(verify_ssl):
    global _session
    if _session is None:
        _session = requests.Session()
        _session.verify = verify_ssl
    return _session


def _get_schema_by_id(url, id, verify_ssl=True):
    ctx = _schema_cache.get(id)

    if ctx is not None:
        return ctx

    ctx = Context()

    session = _get_session(verify_ssl)
    response = session.get(f"{url}/schemas/ids/{id}")
    response.raise_for_status()
    data = response.json()

    for reference in data.get("references", []):
        _get_schema(
            url,
            reference["name"],
            reference["subject"],
            reference["version"],
            ctx,
            verify_ssl,
        )

    ctx.add_proto("<<<MAIN>>>", data["schema"])

    _schema_cache[id] = ctx

    return ctx


def _get_schema(url, name, subject, version, ctx, verify_ssl=True):
    session = _get_session(verify_ssl)
    response = session.get(f"{url}/subjects/{subject}/versions/{version}")
    response.raise_for_status()
    data = response.json()

    for reference in data.get("references", []):
        _get_schema(
            url,
            reference["name"],
            reference["subject"],
            reference["version"],
            ctx,
            verify_ssl,
        )

    ctx.add_proto(name, data["schema"])


# utility: read message


def _read_byte(buffer):
    byte = buffer.read(1)
    if byte == b"":
        raise EOFError("Unexpected EOF encountered")
    return ord(byte)


_MAX_VARINT_BYTES = 10


def _read_varint(buffer):
    value = 0
    shift = 0
    try:
        for _ in range(_MAX_VARINT_BYTES):
            i = _read_byte(buffer)
            value |= (i & 0x7F) << shift
            shift += 7
            if not (i & 0x80):
                return (value >> 1) ^ -(value & 1)
    except EOFError:
        raise EOFError("Unexpected EOF while reading index") from None

    raise RuntimeError(f"Varint is too long (more than {_MAX_VARINT_BYTES} bytes)")


def _read_index_array(buffer):
    size = _read_varint(buffer)
    if size < 0 or size > 100000:
        raise RuntimeError("Invalid Protobuf message_index array length")

    if size == 0:
        return [0]

    msg_index = []
    for _ in range(size):
        msg_index.append(_read_varint(buffer))

    return msg_index


# utility: format output record


def _format_record(offset, key, message_json):
    record = {"@offset": int(offset), "@key": key}
    record.update(json.loads(message_json))
    return json.dumps(record)


@click.command()
@click.argument("file", type=click.File("rb"))
@click.option(
    "--schema-registry", type=str, help="The URL of the Schema Registry cluster."
)
@click.option(
    "--no-verify",
    is_flag=True,
    default=False,
    help="Disable SSL certificate verification (not recommended for production).",
)
def main(file, schema_registry, no_verify):
    verify_ssl = not no_verify
    while True:
        offset = file.readline().decode("utf-8")[:-1]
        key = file.readline().decode("utf-8")[:-1]

        raw_length_bytes = file.read(4)

        if len(raw_length_bytes) != 4:
            if len(raw_length_bytes) != 0:
                raise Exception("Unexpected EOF")
            break

        (raw_length,) = struct.unpack(">I", raw_length_bytes)
        raw_buffer = BytesIO(file.read(raw_length))

        # read header

        magic_byte, schema_id = struct.unpack(">bI", raw_buffer.read(5))

        if magic_byte != 0:
            raise RuntimeError(f"Incorrect magic byte ({magic_byte}).")

        message_index = _read_index_array(raw_buffer)

        # compile protos form schema-registry

        proto_ctx = _get_schema_by_id(schema_registry, schema_id, verify_ssl)

        message_buffer = raw_buffer.read()

        message_type = proto_ctx.message_type_from_index("<<<MAIN>>>", message_index)

        message = proto_ctx.to_json(message_type, message_buffer)

        print(_format_record(offset, key, message))
