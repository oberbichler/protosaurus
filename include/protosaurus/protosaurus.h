#pragma once

#include <google/protobuf/compiler/parser.h>          // Parser
#include <google/protobuf/descriptor.h>               // DescriptorPool, FileDescriptorProto, FileDescriptor. Descriptor
#include <google/protobuf/dynamic_message.h>          // DynamicMessageFactory
#include <google/protobuf/io/tokenizer.h>             // Tokenizer
#include <google/protobuf/io/zero_copy_stream_impl.h> // ArrayInputStream
#include <google/protobuf/message.h>                  // Message
#include <google/protobuf/util/json_util.h>           // MessageToJsonString, JsonStringToMessage

#include <memory>                                     // unique_ptr
#include <mutex>                                      // unique_lock
#include <shared_mutex>                               // shared_mutex, shared_lock
#include <stdexcept>                                  // runtime_error
#include <string>                                     // string
#include <vector>                                     // vector

namespace protosaurus {

using namespace google::protobuf;
using namespace google::protobuf::io;
using namespace google::protobuf::compiler;


class ParserErrorCollector : public google::protobuf::io::ErrorCollector {
private:
  std::string m_errors;

public:
  void RecordError(int line, int column, absl::string_view message) override {
    if (!m_errors.empty()) m_errors += "\n";
    m_errors += std::to_string(line + 1) + ":" + std::to_string(column + 1) + ": " + std::string(message);
  }

  void RecordWarning(int line, int column, absl::string_view message) override {}

  bool has_errors() const { return !m_errors.empty(); }
  const std::string& errors() const { return m_errors; }
};


class Context {
private:
  google::protobuf::DescriptorPool m_pool;
  DynamicMessageFactory m_factory;
  mutable std::shared_mutex m_mutex;

public:
  void add_proto(const std::string& filename, const std::string& content) {
    ParserErrorCollector error_collector;

    // parsing is lock-free (only local variables)
    ArrayInputStream raw_input(content.c_str(), static_cast<int>(content.size()));
    Tokenizer input(&raw_input, &error_collector);

    FileDescriptorProto file_descriptor_proto;
    Parser parser;
    parser.RecordErrorsTo(&error_collector);

    if (!parser.Parse(&input, &file_descriptor_proto)) {
      std::string msg = "Could not parse proto";
      if (error_collector.has_errors()) {
        msg += ":\n" + error_collector.errors();
      }
      throw std::runtime_error(msg);
    }

    if (!file_descriptor_proto.has_name()) {
      file_descriptor_proto.set_name(filename);
    }

    std::unique_lock lock(m_mutex);

    const FileDescriptor* file_desc = m_pool.BuildFile(file_descriptor_proto);

    if (file_desc == nullptr) {
      throw std::runtime_error("Could not get a file descriptor from .proto");
    }
  }

  std::string to_json(const std::string& message_type, const std::string& data) {
    std::shared_lock lock(m_mutex);

    // get descriptor

    const Descriptor* descriptor = m_pool.FindMessageTypeByName(message_type);

    if (descriptor == nullptr) {
      throw std::runtime_error("Could not find descriptor for message type \"" + message_type + "\"");
    }

    // generate prototype message

    const Message* prototype = m_factory.GetPrototype(descriptor);

    if (prototype == nullptr) {
      throw std::runtime_error("Could not create prototype");
    }

    // parse data
  
    std::unique_ptr<Message> message(prototype->New());

    if (message == nullptr) {
      throw std::runtime_error("Could not create empty message from prototype");
    }

    if (!message->ParseFromArray(data.data(), static_cast<int>(data.size()))) {
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

  std::string from_json(const std::string& message_type, const std::string& data) {
    std::shared_lock lock(m_mutex);

    // get descriptor

    const Descriptor* descriptor = m_pool.FindMessageTypeByName(message_type);

    if (descriptor == nullptr) {
      throw std::runtime_error("Could not find descriptor for message type \"" + message_type + "\"");
    }

    // generate prototype message

    const Message* prototype = m_factory.GetPrototype(descriptor);

    if (prototype == nullptr) {
      throw std::runtime_error("Could not create prototype");
    }

    // parse data
  
    std::unique_ptr<Message> message(prototype->New());

    if (message == nullptr) {
      throw std::runtime_error("Could not create empty message from prototype");
    }

    // parse json

    absl::Status status = util::JsonStringToMessage(data, message.get());

    if (!status.ok()) {
      throw std::runtime_error("Could not convert json to message");
    }

    std::string out;

    if (!message->SerializeToString(&out)) {
      throw std::runtime_error("Could not serialize message");
    }

    return out;
  }

  std::string message_type_from_index(const std::string& filename, const std::vector<int>& message_index) {
    if (message_index.size() == 0) {
      throw std::runtime_error("Message index is empty");
    }

    std::shared_lock lock(m_mutex);

    const FileDescriptor* file_descriptor = m_pool.FindFileByName(filename);

    if (file_descriptor == nullptr) {
      throw std::runtime_error("Could not find file descriptor");
    }

    auto it = message_index.begin();

    if (*it < 0 || file_descriptor->message_type_count() <= *it) {
      throw std::runtime_error("Index out of range at position 0");
    }

    auto* descriptor = file_descriptor->message_type(*it);

    while (++it != message_index.end()) {
      if (*it < 0 || descriptor->nested_type_count() <= *it) {
        auto position = std::distance(message_index.begin(), it);
        throw std::runtime_error("Index out of range at position " + std::to_string(position));
      }
      
      descriptor = descriptor->nested_type(*it);
    }

    return std::string(descriptor->full_name());
  }
};

}  // namespace protosaurus
