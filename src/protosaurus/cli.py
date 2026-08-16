import json
import struct

import click
import requests

from protosaurus import Context, read_varint

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


# The message index is a zigzag-encoded varint array, so read_varint is called
# with zigzag=True here. Returns the index together with the offset just after
# it, so the caller can slice off the message that follows.
def _read_index_array(data, offset):
    size, offset = read_varint(data, offset, zigzag=True)

    if size < 0 or size > 100000:
        raise RuntimeError("Invalid Protobuf message_index array length")

    if size == 0:
        return [0], offset

    msg_index = []

    for _ in range(size):
        value, offset = read_varint(data, offset, zigzag=True)
        msg_index.append(value)

    return msg_index, offset


# utility: format output record


def _format_record(offset, key, message_json, pretty=False):
    record = {"@offset": int(offset), "@key": key}
    record.update(json.loads(message_json))
    # The record wraps the message in @offset/@key and is re-serialised here, so
    # indentation has to be applied at this step rather than by to_json.
    return json.dumps(record, indent=2 if pretty else None)


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
@click.option(
    "--defaults",
    is_flag=True,
    default=False,
    help="Print fields that do not track presence even when they hold their default.",
)
@click.option("--pretty", is_flag=True, default=False, help="Indent the output.")
@click.option(
    "--proto-field-names",
    is_flag=True,
    default=False,
    help="Keep the field names as written in the .proto instead of lowerCamelCase.",
)
@click.option(
    "--enums-as-ints",
    is_flag=True,
    default=False,
    help="Print enum values as numbers instead of their names.",
)
@click.option(
    "--unquote-int64",
    is_flag=True,
    default=False,
    help="Print 64-bit integers unquoted when the value fits a double exactly.",
)
def main(
    file,
    schema_registry,
    no_verify,
    defaults,
    pretty,
    proto_field_names,
    enums_as_ints,
    unquote_int64,
):
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
        raw = file.read(raw_length)

        # read header

        magic_byte, schema_id = struct.unpack_from(">bI", raw, 0)

        if magic_byte != 0:
            raise RuntimeError(f"Incorrect magic byte ({magic_byte}).")

        # Not named `offset`: that already holds the Kafka record offset here.
        message_index, message_start = _read_index_array(raw, 5)

        # compile protos form schema-registry

        proto_ctx = _get_schema_by_id(schema_registry, schema_id, verify_ssl)

        message_buffer = raw[message_start:]

        message_type = proto_ctx.message_type_from_index("<<<MAIN>>>", message_index)

        message = proto_ctx.to_json(
            message_type,
            message_buffer,
            include_defaults=defaults,
            proto_field_names=proto_field_names,
            enums_as_ints=enums_as_ints,
            unquote_int64=unquote_int64,
        )

        print(_format_record(offset, key, message, pretty=pretty))
