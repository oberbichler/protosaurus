#pragma once

#include <protosaurus/protosaurus.h>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <google/protobuf/compiler/parser.h>          // Parser
#include <google/protobuf/descriptor.h>               // DescriptorPool, FileDescriptorProto, FileDescriptor. Descriptor
#include <google/protobuf/dynamic_message.h>          // DynamicMessageFactory
#include <google/protobuf/io/tokenizer.h>             // Tokenizer
#include <google/protobuf/io/zero_copy_stream_impl.h> // ArrayInputStream
#include <google/protobuf/message.h>                  // Message
#include <google/protobuf/util/json_util.h>           // MessageToJsonString, 

#include <ios>                                        // boolalpha
#include <iosfwd>                                     // ostream
#include <sstream>                                    // stringstream
#include <stdexcept>                                  // runtime_error
#include <string>                                     // string
#include <memory>                                     // unique_ptr

namespace nb = nanobind;

using namespace nb::literals;

namespace protosaurus {

using namespace google::protobuf;
using namespace google::protobuf::io;
using namespace google::protobuf::compiler;


class Context {
private:
  google::protobuf::DescriptorPool m_pool;

public:
  void add_proto(const std::string& name, const std::string& content) {
    ArrayInputStream raw_input(content.c_str(), strlen(content.c_str()));
    Tokenizer input(&raw_input, nullptr);

    FileDescriptorProto file_descriptor_proto;
    Parser parser;

    if (!parser.Parse(&input, &file_descriptor_proto)) {
      throw std::runtime_error("Could not parse proto");
    }

    if (!file_descriptor_proto.has_name()) {
      file_descriptor_proto.set_name(name);
    }

    const FileDescriptor* file_desc = m_pool.BuildFile(file_descriptor_proto);

    if (file_desc == nullptr) {
      throw std::runtime_error("Could not get a file descriptor from .proto");
    }
  }

  std::string to_json(std::string message_type, nb::bytes data) {
    // get descriptor

    const Descriptor* descriptor = m_pool.FindMessageTypeByName(message_type);

    if (descriptor == nullptr) {
      throw std::runtime_error("Could not find descriptor for message type \"" + message_type + "\"");
    }

    // generate prototype message
  
    DynamicMessageFactory factory;

    const Message* prototype = factory.GetPrototype(descriptor);

    if (prototype == nullptr) {
      throw std::runtime_error("Could not create prototype");
    }

    // parse data
  
    std::unique_ptr<Message> message(prototype->New());

    if (message == nullptr) {
      throw std::runtime_error("Could not create empty message from prototype");
    }

    if (!message->ParseFromArray(data.c_str(), data.size())) {
      throw std::runtime_error("Could not parse value in buffer");
    }

    // write json

    std::string out;

    absl::Status status = util::MessageToJsonString(*message, &out);

    return out;
  }

  nb::bytes from_json(std::string message_type, std::string data) {
    // get descriptor

    const Descriptor* descriptor = m_pool.FindMessageTypeByName(message_type);

    if (descriptor == nullptr) {
      throw std::runtime_error("Could not find descriptor for message type \"" + message_type + "\"");
    }

    // generate prototype message
  
    DynamicMessageFactory factory;

    const Message* prototype = factory.GetPrototype(descriptor);

    if (prototype == nullptr) {
      throw std::runtime_error("Could not create prototype");
    }

    // parse data
  
    std::unique_ptr<Message> message(prototype->New());

    if (message == nullptr) {
      throw std::runtime_error("Could not create empty message from prototype");
    }

    // write json

    std::string out;

    absl::Status status = util::JsonStringToMessage(data, message.get());

    message->SerializeToString(&out);

    return nb::bytes(out.c_str(), out.size());
  }
};

}  // namespace protosaurus