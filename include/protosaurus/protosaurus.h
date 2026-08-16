#pragma once

#include <google/protobuf/compiler/parser.h>  // Parser
#include <google/protobuf/descriptor.h>       // DescriptorPool, FileDescriptorProto, FileDescriptor. Descriptor
#include <google/protobuf/dynamic_message.h>  // DynamicMessageFactory
#include <google/protobuf/io/tokenizer.h>     // Tokenizer
#include <google/protobuf/io/zero_copy_stream_impl.h>  // ArrayInputStream
#include <google/protobuf/message.h>                   // Message
#include <google/protobuf/util/json_util.h>            // MessageToJsonString, JsonStringToMessage

#include <cstdint>       // uint64_t, int64_t, uint8_t
#include <memory>        // unique_ptr
#include <mutex>         // unique_lock
#include <shared_mutex>  // shared_mutex, shared_lock
#include <stdexcept>     // runtime_error, out_of_range
#include <string>        // string
#include <string_view>   // string_view
#include <vector>        // vector

namespace protosaurus {

// Targeted using-declarations instead of using-directives: a `using namespace` in a
// header leaks every name of those namespaces into whatever includes it.
using google::protobuf::Descriptor;
using google::protobuf::DescriptorPool;
using google::protobuf::DynamicMessageFactory;
using google::protobuf::FileDescriptor;
using google::protobuf::FileDescriptorProto;
using google::protobuf::Message;
using google::protobuf::compiler::Parser;
using google::protobuf::io::ArrayInputStream;
using google::protobuf::io::Tokenizer;

namespace util = google::protobuf::util;


class ParserErrorCollector : public google::protobuf::io::ErrorCollector {
private:
  std::string m_errors;

public:
  void RecordError(int line, int column, absl::string_view message) override {
    if (!m_errors.empty()) m_errors += "\n";
    m_errors += std::to_string(line + 1) + ":" + std::to_string(column + 1) + ": " + std::string(message);
  }

  void RecordWarning(int /*line*/, int /*column*/, absl::string_view /*message*/) override {}

  bool has_errors() const { return !m_errors.empty(); }
  const std::string& errors() const { return m_errors; }
};


// A base-128 varint holds at most 64 bits in groups of 7, so ten bytes is the
// longest well-formed encoding. Anything longer is malformed and must be
// rejected rather than read on indefinitely.
inline constexpr std::size_t MAX_VARINT_BYTES = 10;


// The data ended in the middle of a varint.
class VarintTruncated : public std::runtime_error {
public:
  VarintTruncated() : std::runtime_error("Unexpected end of data while reading varint") {}
};


// More continuation bytes than a 64-bit value can hold.
class VarintTooLong : public std::runtime_error {
public:
  VarintTooLong()
      : std::runtime_error("Varint is too long (more than " + std::to_string(MAX_VARINT_BYTES) + " bytes)") {}
};


// The starting offset is not inside the data.
class VarintOffsetOutOfRange : public std::out_of_range {
public:
  VarintOffsetOutOfRange() : std::out_of_range("offset is past the end of the data") {}
};


struct Varint {
  // The decoded bits, before any zigzag interpretation.
  std::uint64_t value;
  // Position just after the varint, so the next read can continue from here.
  std::size_t offset;
};


// Reads one base-128 varint starting at `offset`.
inline Varint read_varint(std::string_view data, std::size_t offset) {
  if (offset > data.size()) {
    throw VarintOffsetOutOfRange();
  }

  std::uint64_t value = 0;
  unsigned shift = 0;

  for (std::size_t i = 0; i < MAX_VARINT_BYTES; ++i) {
    if (offset >= data.size()) {
      throw VarintTruncated();
    }

    const auto byte = static_cast<std::uint8_t>(data[offset++]);

    value |= static_cast<std::uint64_t>(byte & 0x7F) << shift;
    shift += 7;

    // The high bit clear marks the last byte of the varint.
    if ((byte & 0x80) == 0) {
      return {value, offset};
    }
  }

  throw VarintTooLong();
}


// Protobuf's sint32/sint64 encoding maps signed values onto unsigned ones so
// that small magnitudes stay short. Only those two types use it; plain int32,
// int64, lengths and field tags are not zigzag encoded.
inline std::int64_t zigzag_decode(std::uint64_t value) {
  // Unary minus on an unsigned type is well defined and yields either all zero
  // bits or all one bits, which is exactly the mask the decoding needs.
  const std::uint64_t mask = std::uint64_t{0} - (value & 1);
  return static_cast<std::int64_t>((value >> 1) ^ mask);
}


// Subset of google::protobuf::json::PrintOptions exposed to callers. Every option
// defaults to the ProtoJSON behaviour, so a default-constructed JsonOptions
// produces exactly the output of MessageToJsonString without options.
struct JsonOptions {
  // Print fields that do not track presence even when they hold their default:
  // implicit-presence scalars, empty lists and empty maps. Fields with explicit
  // presence (proto3 `optional`, submessages, oneof members) stay omitted when
  // unset, because for them "unset" differs from "set to the default".
  bool include_defaults = false;

  // Indent and line-break the output instead of emitting a single line.
  bool pretty = false;

  // Keep the field names as written in the .proto instead of lowerCamelCase.
  bool proto_field_names = false;

  // Emit enum values as numbers instead of their names.
  bool enums_as_ints = false;

  // Emit 64-bit integers unquoted when the value round-trips through a double.
  // Values that would lose precision stay quoted, so the JSON type of a field
  // depends on its value.
  bool unquote_int64 = false;
};


class Context {
private:
  DescriptorPool m_pool;
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

  std::string to_json(const std::string& message_type, const std::string& data, const JsonOptions& options = {}) {
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

    util::JsonPrintOptions print_options;
    print_options.always_print_fields_with_no_presence = options.include_defaults;
    print_options.add_whitespace = options.pretty;
    print_options.preserve_proto_field_names = options.proto_field_names;
    print_options.always_print_enums_as_ints = options.enums_as_ints;
    print_options.unquote_int64_if_possible = options.unquote_int64;

    absl::Status status = util::MessageToJsonString(*message, &out, print_options);

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
    if (message_index.empty()) {
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
