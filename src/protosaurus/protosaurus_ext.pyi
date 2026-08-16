from collections.abc import Sequence


class Context:
    """
    A pool of .proto schemas for converting messages between the protobuf wire
    format and JSON.

    The pool is thread-safe: add_proto takes an exclusive lock and the conversions
    a shared one, so a single context can be shared across threads.
    """

    def __init__(self) -> None: ...

    def add_proto(self, filename: str, content: str) -> None:
        """
        Parse a .proto definition and add it to the pool.

        `filename` is the name the file is registered under: other protos import it by
        that name, and message_type_from_index looks it up by it. A proto may import
        any file added before it.

        Raises RuntimeError if the content does not parse or does not link, with the
        parser or linker diagnostics appended.
        """

    def to_json(self, message_type: str, data: bytes, *, include_defaults: bool = False, pretty: bool = False, proto_field_names: bool = False, enums_as_ints: bool = False, unquote_int64: bool = False) -> str:
        """
        Decode `data` from the protobuf wire format and return it as a JSON string.

        `message_type` is the fully qualified name, so "zoo.Animal" for a message in
        `package zoo`. With no options set, the output is plain ProtoJSON.

        Raises RuntimeError if the type is unknown -- the message then lists the known
        types -- if the data is not valid wire format, or if a proto2 message is
        missing required fields.
        """

    def from_json(self, message_type: str, json: str, *, ignore_unknown_fields: bool = False) -> bytes:
        """
        Encode the JSON document `json` as a protobuf message and return the wire
        format bytes.

        `message_type` is the fully qualified name, so "zoo.Animal" for a message in
        `package zoo`. Pass ignore_unknown_fields=True to drop JSON fields the schema
        does not define instead of failing on them.

        Raises RuntimeError if the type is unknown, if the JSON does not match the
        schema, or if required fields are missing.
        """

    def message_type_from_index(self, filename: str, message_index: Sequence[int]) -> str:
        """
        Resolve a Confluent message index to a fully qualified message type.

        The index addresses a message by position instead of by name: the first entry
        selects a top-level message of `filename`, every further entry a message nested
        inside the previous one. [0] is therefore the first message in the file.

        Raises RuntimeError for an unknown file, an empty index, or an entry outside
        the range of messages it addresses.
        """

def read_varint(data: bytes, offset: int = 0, *, zigzag: bool = False) -> tuple[int, int]:
    """
    Read one base-128 varint from `data`, starting at `offset`.

    Returns the decoded value together with the position just after it, so
    consecutive reads need no state of their own.

    Set zigzag=True for the sint32/sint64 encoding, which maps signed values onto
    unsigned ones. Field tags, lengths, int32, int64, uint64, bool and enums are
    not zigzag encoded, so the default is off.

    Raises EOFError if the data ends mid-varint, RuntimeError for a varint longer
    than ten bytes, and IndexError for a negative offset or one past the end.
    """
