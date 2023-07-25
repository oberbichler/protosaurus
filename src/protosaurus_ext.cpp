#include <protosaurus/protosaurus.h>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

NB_MODULE(protosaurus_ext, m) {
  using protosaurus::Context;

  nb::class_<Context>(m, "Context")
    .def(nb::init<>())
    .def("add_proto", &Context::add_proto, "filename"_a, "content"_a)
    .def("to_json", &Context::to_json, "message_type"_a, "data"_a)
    .def("from_json", &Context::from_json, "message_type"_a, "json"_a)
    .def("message_type_from_index", &Context::message_type_from_index, "filename"_a, "message_index"_a);
}
