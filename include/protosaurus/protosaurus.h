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
#include <google/protobuf/util/json_util.h>           // MessageToJsonString, JsonStringToMessage

#include <memory>                                     // unique_ptr
#include <stdexcept>                                  // runtime_error
#include <string>                                     // string
#include <vector>                                     // vector

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
  void add_proto(const std::string& filename, const std::string& content) {
    ArrayInputStream raw_input(content.c_str(), strlen(content.c_str()));
    Tokenizer input(&raw_input, nullptr);

    FileDescriptorProto file_descriptor_proto;
    Parser parser;

    if (!parser.Parse(&input, &file_descriptor_proto)) {
      throw std::runtime_error("Could not parse proto");
    }

    if (!file_descriptor_proto.has_name()) {
      file_descriptor_proto.set_name(filename);
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

    if (!status.ok()) {
      throw std::runtime_error("Could not convert message to json");
    }
    
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

    // parse json

    std::string out;

    absl::Status status = util::JsonStringToMessage(data, message.get());

    if (!status.ok()) {
      throw std::runtime_error("Could not convert json to message");
    }

    message->SerializeToString(&out);

    return nb::bytes(out.c_str(), out.size());
  }

  std::string message_type_from_index(const std::string& filename, const std::vector<int> message_index) {
    if (message_index.size() == 0) {
      throw std::runtime_error("Message index is empty");
    }

    const FileDescriptor* file_descriptor = m_pool.FindFileByName(filename);

    if (file_descriptor == nullptr) {
      throw std::runtime_error("Could not find file descriptor");
    }

    auto it = message_index.begin();

    auto* descriptor = file_descriptor->message_type(*it);

    while (++it != message_index.end()) {
      if (*it < 0 || descriptor->nested_type_count() <= *it) {
        auto position = std::distance(message_index.begin(), it);
        throw std::runtime_error("Index out of range at position " + std::to_string(position));
      }
      
      descriptor = descriptor->nested_type(*it);
    }

    return descriptor->full_name();
  }
};

}  // namespace protosaurus
