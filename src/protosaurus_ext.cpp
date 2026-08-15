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

nb::bytes from_json(Context& self, const std::string& message_type, const std::string& json) {
  std::string result;
  {
    nb::gil_scoped_release release;
    result = self.from_json(message_type, json);
  }
  // GIL re-acquired, safe to create nb::bytes
  return nb::bytes(result.data(), result.size());
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
      .def("from_json", &from_json, "message_type"_a, "json"_a)
      .def("message_type_from_index", &message_type_from_index, "filename"_a, "message_index"_a);
}
