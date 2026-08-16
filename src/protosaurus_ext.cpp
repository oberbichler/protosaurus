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

}  // namespace

NB_MODULE(protosaurus_ext, m) {
  nb::class_<Context>(m, "Context")
      .def(nb::init<>())
      .def("add_proto", &add_proto, "filename"_a, "content"_a)
      .def("to_json", &to_json, "message_type"_a, "data"_a, nb::kw_only(), "include_defaults"_a = false,
           "pretty"_a = false, "proto_field_names"_a = false, "enums_as_ints"_a = false, "unquote_int64"_a = false)
      .def("from_json", &from_json, "message_type"_a, "json"_a, nb::kw_only(), "ignore_unknown_fields"_a = false)
      .def("message_type_from_index", &message_type_from_index, "filename"_a, "message_index"_a);

  // The return type is built dynamically, so nanobind would infer a bare
  // `object`. Spell the signature out instead, for the stub and the docstring.
  m.def("read_varint", &read_varint, "data"_a, "offset"_a = 0, nb::kw_only(), "zigzag"_a = false,
        nb::sig("def read_varint(data: bytes, offset: int = 0, *, zigzag: bool = False) -> "
                "tuple[int, int]"));
}
