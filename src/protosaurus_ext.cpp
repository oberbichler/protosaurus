#include <protosaurus/protosaurus.h>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

NB_MODULE(protosaurus_ext, m) {
  using protosaurus::Context;

  nb::class_<Context>(m, "Context")
    .def(nb::init<>())
    .def("add_proto", &Context::add_proto, "name"_a, "content"_a)
    .def("to_json", &Context::to_json, "message_type"_a, "data"_a)
    .def("from_json", &Context::from_json, "message_type"_a, "json"_a);
}
