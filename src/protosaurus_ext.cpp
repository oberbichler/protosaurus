#include <protosaurus/protosaurus.h>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

namespace nb = nanobind;
using namespace nb::literals;

NB_MODULE(protosaurus_ext, m) {
  using protosaurus::Context;

  nb::class_<Context>(m, "Context")
    .def(nb::init<>())
    .def("add_proto", [](Context& self, const std::string& filename, const std::string& content) {
      nb::gil_scoped_release release;
      self.add_proto(filename, content);
    }, "filename"_a, "content"_a)
    .def("to_json", [](Context& self, const std::string& message_type, nb::bytes data) {
      // copy Python bytes to std::string while GIL is held
      std::string data_copy(data.c_str(), data.size());

      nb::gil_scoped_release release;
      return self.to_json(message_type, data_copy);
    }, "message_type"_a, "data"_a)
    .def("from_json", [](Context& self, const std::string& message_type, const std::string& json) -> nb::bytes {
      std::string result;
      {
        nb::gil_scoped_release release;
        result = self.from_json(message_type, json);
      }
      // GIL re-acquired, safe to create nb::bytes
      return nb::bytes(result.data(), result.size());
    }, "message_type"_a, "json"_a)
    .def("message_type_from_index", [](Context& self, const std::string& filename, const std::vector<int>& message_index) {
      nb::gil_scoped_release release;
      return self.message_type_from_index(filename, message_index);
    }, "filename"_a, "message_index"_a);
}
