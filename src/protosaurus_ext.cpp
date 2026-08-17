#include <protosaurus/protosaurus.h>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

namespace nb = nanobind;
using namespace nb::literals;

using protosaurus::Context;

namespace {

void add_proto(Context& self, const std::string& filename, const std::string& content) {
  nb::gil_scoped_release release;
  self.add_proto(filename, content);
}

std::string to_json(Context& self, const std::string& message_type, nb::bytes data, bool include_defaults, bool pretty,
                    bool proto_field_names, bool enums_as_ints, bool unquote_int64) {
  // copy Python bytes to std::string while the GIL is held
  std::string data_copy(data.c_str(), data.size());

  protosaurus::JsonOptions options;
  options.include_defaults = include_defaults;
  options.pretty = pretty;
  options.proto_field_names = proto_field_names;
  options.enums_as_ints = enums_as_ints;
  options.unquote_int64 = unquote_int64;

  nb::gil_scoped_release release;
  return self.to_json(message_type, data_copy, options);
}

nb::bytes from_json(Context& self, const std::string& message_type, const std::string& json,
                    bool ignore_unknown_fields) {
  protosaurus::ParseOptions options;
  options.ignore_unknown_fields = ignore_unknown_fields;

  std::string result;
  {
    nb::gil_scoped_release release;
    result = self.from_json(message_type, json, options);
  }
  // GIL re-acquired, safe to create nb::bytes
  return nb::bytes(result.data(), result.size());
}

// Returns (value, offset). The GIL is deliberately held: decoding a varint is a
// handful of byte reads, so releasing it would cost more than it saves, and
// raising EOFError below needs it anyway.
nb::object read_varint(nb::bytes data, Py_ssize_t offset, bool zigzag) {
  if (offset < 0) {
    throw nb::index_error("offset must not be negative");
  }

  const std::string_view view(data.c_str(), data.size());

  protosaurus::Varint result;

  try {
    result = protosaurus::read_varint(view, static_cast<std::size_t>(offset));
  } catch (const protosaurus::VarintOffsetOutOfRange& e) {
    throw nb::index_error(e.what());
  } catch (const protosaurus::VarintTruncated& e) {
    // nanobind has no built-in translation for EOFError, so raise it directly.
    PyErr_SetString(PyExc_EOFError, e.what());
    throw nb::python_error();
  }
  // VarintTooLong derives from std::runtime_error and reaches Python as RuntimeError.

  if (zigzag) {
    return nb::make_tuple(protosaurus::zigzag_decode(result.value), result.offset);
  }

  return nb::make_tuple(result.value, result.offset);
}

std::string message_type_from_index(Context& self, const std::string& filename, const std::vector<int>& message_index) {
  nb::gil_scoped_release release;
  return self.message_type_from_index(filename, message_index);
}

nb::dict field_to_dict(const protosaurus::FieldInfo& field) {
  nb::dict d;
  d["name"] = field.name;
  d["json_name"] = field.json_name;
  d["number"] = field.number;
  d["type"] = field.type;
  d["label"] = field.label;
  d["has_presence"] = field.has_presence;

  if (field.oneof) {
    d["oneof"] = *field.oneof;
  } else {
    d["oneof"] = nb::none();
  }

  if (field.type_name) d["type_name"] = *field.type_name;
  if (field.key_type) d["key_type"] = *field.key_type;
  if (field.value_type) d["value_type"] = *field.value_type;
  if (field.value_type_name) d["value_type_name"] = *field.value_type_name;

  if (!field.enum_values.empty()) {
    nb::list values;
    for (const auto& value : field.enum_values) {
      nb::dict v;
      v["name"] = value.name;
      v["number"] = value.number;
      values.append(v);
    }
    d["enum_values"] = values;
  }

  return d;
}

nb::dict describe(Context& self, const std::string& type_name) {
  protosaurus::DescribeResult result;
  {
    nb::gil_scoped_release release;
    result = self.describe(type_name);
  }

  nb::dict out;

  if (result.is_enum) {
    out["name"] = result.enum_info.name;
    out["kind"] = "enum";

    nb::list values;
    for (const auto& value : result.enum_info.values) {
      nb::dict v;
      v["name"] = value.name;
      v["number"] = value.number;
      values.append(v);
    }
    out["values"] = values;

    return out;
  }

  out["name"] = result.message.name;
  out["kind"] = "message";

  nb::list fields;
  for (const auto& field_info : result.message.fields) {
    fields.append(field_to_dict(field_info));
  }
  out["fields"] = fields;

  return out;
}

// Docstrings, kept out of the binding block below so that it stays readable.
// nanobind puts each one after the signature it generates, and
// nanobind_add_stub copies both into protosaurus_ext.pyi -- which is what an
// editor reads for completion and hover text. They are written flush left
// because the stub generator dedents them.

constexpr const char* CONTEXT_DOC = R"doc(
A pool of .proto schemas for converting messages between the protobuf wire
format and JSON.

The pool is thread-safe: add_proto takes an exclusive lock and the conversions
a shared one, so a single context can be shared across threads.
)doc";

constexpr const char* ADD_PROTO_DOC = R"doc(
Parse a .proto definition and add it to the pool.

`filename` is the name the file is registered under: other protos import it by
that name, and message_type_from_index looks it up by it. A proto may import
any file added before it.

Raises RuntimeError if the content does not parse or does not link, with the
parser or linker diagnostics appended.
)doc";

constexpr const char* TO_JSON_DOC = R"doc(
Decode `data` from the protobuf wire format and return it as a JSON string.

`message_type` is the fully qualified name, so "zoo.Animal" for a message in
`package zoo`. With no options set, the output is plain ProtoJSON.

Raises RuntimeError if the type is unknown -- the message then lists the known
types -- if the data is not valid wire format, or if a proto2 message is
missing required fields.
)doc";

constexpr const char* FROM_JSON_DOC = R"doc(
Encode the JSON document `json` as a protobuf message and return the wire
format bytes.

`message_type` is the fully qualified name, so "zoo.Animal" for a message in
`package zoo`. Pass ignore_unknown_fields=True to drop JSON fields the schema
does not define instead of failing on them.

Raises RuntimeError if the type is unknown, if the JSON does not match the
schema, or if required fields are missing.
)doc";

constexpr const char* MESSAGE_TYPE_FROM_INDEX_DOC = R"doc(
Resolve a Confluent message index to a fully qualified message type.

The index addresses a message by position instead of by name: the first entry
selects a top-level message of `filename`, every further entry a message nested
inside the previous one. [0] is therefore the first message in the file.

Raises RuntimeError for an unknown file, an empty index, or an entry outside
the range of messages it addresses.
)doc";

constexpr const char* DESCRIBE_DOC = R"doc(
Describe a message or enum type's shape.

`type_name` is a fully qualified message or enum name, resolved the same way
`to_json`'s `message_type` argument is. For a message, the result is
{"name", "kind": "message", "fields": [...]}, where every field has at least
name, json_name, number, type, label, has_presence and oneof, plus
type_name/enum_values/key_type/value_type/value_type_name where relevant.
For an enum, the result is {"name", "kind": "enum", "values": [...]}.

Nested message and enum types are referenced by name only, one level per
call -- call describe again to resolve them further.

Raises RuntimeError if neither a message nor an enum type of that name is
known, with a listing of known message and enum types.
)doc";

constexpr const char* READ_VARINT_DOC = R"doc(
Read one base-128 varint from `data`, starting at `offset`.

Returns the decoded value together with the position just after it, so
consecutive reads need no state of their own.

Set zigzag=True for the sint32/sint64 encoding, which maps signed values onto
unsigned ones. Field tags, lengths, int32, int64, uint64, bool and enums are
not zigzag encoded, so the default is off.

Raises EOFError if the data ends mid-varint, RuntimeError for a varint longer
than ten bytes, and IndexError for a negative offset or one past the end.
)doc";

}  // namespace

NB_MODULE(protosaurus_ext, m) {
  nb::class_<Context>(m, "Context", CONTEXT_DOC)
      .def(nb::init<>())
      .def("add_proto", &add_proto, "filename"_a, "content"_a, ADD_PROTO_DOC)
      .def("to_json", &to_json, "message_type"_a, "data"_a, nb::kw_only(), "include_defaults"_a = false,
           "pretty"_a = false, "proto_field_names"_a = false, "enums_as_ints"_a = false, "unquote_int64"_a = false,
           TO_JSON_DOC)
      .def("from_json", &from_json, "message_type"_a, "json"_a, nb::kw_only(), "ignore_unknown_fields"_a = false,
           FROM_JSON_DOC)
      .def("message_type_from_index", &message_type_from_index, "filename"_a, "message_index"_a,
           MESSAGE_TYPE_FROM_INDEX_DOC)
      .def("describe", &describe, "type_name"_a, DESCRIBE_DOC);

  // The return type is built dynamically, so nanobind would infer a bare
  // `object`. Spell the signature out instead, for the stub and the docstring.
  m.def("read_varint", &read_varint, "data"_a, "offset"_a = 0, nb::kw_only(), "zigzag"_a = false,
        nb::sig("def read_varint(data: bytes, offset: int = 0, *, zigzag: bool = False) -> "
                "tuple[int, int]"),
        READ_VARINT_DOC);
}
