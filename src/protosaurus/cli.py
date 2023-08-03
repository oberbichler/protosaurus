from .protosaurus_ext import Context

from io import BytesIO
from urllib3.exceptions import InsecureRequestWarning

import click
import json
import requests
import struct
import sys

# utility: compile protos from schema-registry

# Disble SSH warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

_schema_cache = {}

def _get_schema_by_id(url, id):
    ctx = _schema_cache.get(id, None)

    if ctx is not None:
        return ctx
    
    _schema_cache[id] = ctx = Context()

    data = requests.get(f'{url}/schemas/ids/{id}', verify=False).json()

    for reference in data.get('references', []):
        _get_schema(url, reference['name'], reference['subject'], reference['version'], ctx)

    ctx.add_proto('<<<MAIN>>>', data['schema'])

    return ctx

def _get_schema(url, name, subject, version, ctx):
    data = requests.get(f'{url}/subjects/{subject}/versions/{version}', verify=False).json()

    for reference in data.get('references', []):
        _get_schema(url, reference['name'], reference['subject'], reference['version'], ctx)

    ctx.add_proto(name, data['schema'])


# utility: read message

def _read_byte(buffer):
    byte = buffer.read(1)
    if byte == b'':
        raise EOFError('Unexpected EOF encountered')
    return ord(byte)

def _read_varint(buffer):
    value = 0
    shift = 0
    try:
        while True:
            i = _read_byte(buffer)
            value |= (i & 0x7f) << shift
            shift += 7
            if not (i & 0x80):
                break
        value = (value >> 1) ^ -(value & 1)
        return value
    except EOFError:
        raise EOFError('Unexpected EOF while reading index')

def _read_index_array(buffer):
    size = _read_varint(buffer)
    if size < 0 or size > 100000:
        raise RuntimeError('Invalid Protobuf message_index array length')

    if size == 0:
        return [0]

    msg_index = []
    for _ in range(size):
        msg_index.append(_read_varint(buffer))

    return msg_index


@click.command()
@click.argument('file', type=click.File('rb'))
@click.option('--schema-registry', type=str, help='The URL of the Schema Registry cluster.')
def main(file, schema_registry):
    while True:
        offset = file.readline().decode('utf-8')[:-1]
        key = file.readline().decode('utf-8')[:-1]

        raw_length_bytes = file.read(4)

        if len(raw_length_bytes) != 4:
            if len(raw_length_bytes) != 0:
                raise Exception('Unexpected EOF')
            break

        raw_length, = struct.unpack('>I', raw_length_bytes)
        raw_buffer = BytesIO(file.read(raw_length))

        # read header

        magic_byte, schema_id = struct.unpack('>bI', raw_buffer.read(5))

        if magic_byte != 0:
            raise RuntimeError(f"Incorrect magic byte ({magic_byte}).")

        message_index = _read_index_array(raw_buffer)

        # compile protos form schema-registry

        proto_ctx = _get_schema_by_id(schema_registry, schema_id)
        
        message_buffer = raw_buffer.read()

        message_type = proto_ctx.message_type_from_index('<<<MAIN>>>', message_index)

        message = proto_ctx.to_json(message_type, message_buffer)

        output = f'{{"@offset": {offset}, "@key": "{key}", ' + message[1:]

        print(output)