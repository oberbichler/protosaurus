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
#include <optional>      // optional
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
using google::protobuf::EnumDescriptor;
using google::protobuf::EnumValueDescriptor;
using google::protobuf::FieldDescriptor;
using google::protobuf::FileDescriptor;
using google::protobuf::FileDescriptorProto;
using google::protobuf::Message;
using google::protobuf::OneofDescriptor;
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


// Collects the errors DescriptorPool produces while linking a file. Without a
// collector, BuildFile writes them to ABSL_LOG(ERROR) and merely returns null,
// so the reason -- a missing import, a duplicate symbol, an unresolved type --
// never reaches the caller.
class PoolErrorCollector : public DescriptorPool::ErrorCollector {
private:
  std::string m_errors;

public:
  void RecordError(absl::string_view filename, absl::string_view element_name, const Message* /*descriptor*/,
                   ErrorLocation /*location*/, absl::string_view message) override {
    if (!m_errors.empty()) m_errors += "\n";

    m_errors += std::string(filename);

    if (!element_name.empty()) {
      m_errors += " (" + std::string(element_name) + ")";
    }

    m_errors += ": " + std::string(message);
  }

  void RecordWarning(absl::string_view /*filename*/, absl::string_view /*element_name*/, const Message* /*descriptor*/,
                     ErrorLocation /*location*/, absl::string_view /*message*/) override {}

  bool has_errors() const { return !m_errors.empty(); }
  const std::string& errors() const { return m_errors; }
};


// protobuf assembles its status messages from fragments and leaves runs of
// blanks behind ("invalid JSON in  Animal,  near"). Collapse them so the text
// reads normally when embedded in an exception.
inline std::string collapse_spaces(absl::string_view text) {
  std::string out;
  out.reserve(text.size());

  bool previous_was_space = false;

  for (const char c : text) {
    const bool is_space = c == ' ';

    if (is_space && previous_was_space) continue;

    out += c;
    previous_was_space = is_space;
  }

  return out;
}


inline std::string join(const std::vector<std::string>& items, const std::string& separator) {
  std::string out;

  for (std::size_t i = 0; i < items.size(); ++i) {
    if (i > 0) out += separator;
    out += items[i];
  }

  return out;
}


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


// FieldDescriptor::Label has no built-in string form, unlike TypeName() for
// Type. proto2 is the only syntax that can produce LABEL_REQUIRED; proto3
// fields are always LABEL_OPTIONAL or LABEL_REPEATED.
inline std::string label_name(FieldDescriptor::Label label) {
  switch (label) {
    case FieldDescriptor::LABEL_OPTIONAL:
      return "optional";
    case FieldDescriptor::LABEL_REQUIRED:
      return "required";
    case FieldDescriptor::LABEL_REPEATED:
      return "repeated";
  }
  return "optional";  // unreachable; silences -Wreturn-type
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


// Subset of google::protobuf::json::ParseOptions exposed to callers. As with
// JsonOptions, the default matches ProtoJSON, so a default-constructed
// ParseOptions parses exactly as JsonStringToMessage does without options.
struct ParseOptions {
  // Accept JSON fields the schema does not define instead of failing. Useful
  // when a producer has already moved to a newer schema than the one at hand.
  bool ignore_unknown_fields = false;
};


struct EnumValueInfo {
  std::string name;
  int number;
};

// One field of a message, as reported by Context::describe(). Optional
// members are unset unless the comment next to them says otherwise.
struct FieldInfo {
  std::string name;
  std::string json_name;
  int number;
  // One of FieldDescriptor::TypeName()'s own strings ("int32", "string",
  // "message", "enum", "group", ...), or the synthetic "map".
  std::string type;
  // "optional", "required", or "repeated".
  std::string label;
  bool has_presence;
  // Set only for a real (non-synthetic) oneof member.
  std::optional<std::string> oneof;
  // Set when type is "message", "group", or "enum".
  std::optional<std::string> type_name;
  // Set when type is "map".
  std::optional<std::string> key_type;
  std::optional<std::string> value_type;
  // Set when type is "map" and the value is a message or enum.
  std::optional<std::string> value_type_name;
  // Non-empty only when type is "enum".
  std::vector<EnumValueInfo> enum_values;
};

struct MessageInfo {
  std::string name;
  std::vector<FieldInfo> fields;
};

struct EnumInfo {
  std::string name;
  std::vector<EnumValueInfo> values;
};

// message is valid iff !is_enum; enum_info is valid iff is_enum.
struct DescribeResult {
  bool is_enum;
  MessageInfo message;
  EnumInfo enum_info;
};


class Context {
private:
  DescriptorPool m_pool;
  DynamicMessageFactory m_factory;
  mutable std::shared_mutex m_mutex;

  // DescriptorPool cannot enumerate what it holds, so remember which files were
  // built in order to list the available message types in error messages.
  std::vector<std::string> m_filenames;

  // All of the helpers below expect m_mutex to be held by the caller.

  void collect_message_types(const Descriptor* descriptor, std::vector<std::string>& out) const {
    out.push_back(std::string(descriptor->full_name()));

    for (int i = 0; i < descriptor->nested_type_count(); ++i) {
      collect_message_types(descriptor->nested_type(i), out);
    }
  }

  std::vector<std::string> known_message_types() const {
    std::vector<std::string> out;

    for (const std::string& filename : m_filenames) {
      const FileDescriptor* file = m_pool.FindFileByName(filename);

      if (file == nullptr) continue;

      for (int i = 0; i < file->message_type_count(); ++i) {
        collect_message_types(file->message_type(i), out);
      }
    }

    return out;
  }

  // The usual cause is a missing package prefix, so name what is available.
  [[noreturn]] void throw_unknown_message_type(const std::string& message_type) const {
    std::string msg = "Could not find message type \"" + message_type + "\"";

    const std::vector<std::string> known = known_message_types();

    if (known.empty()) {
      msg += ". No protos have been added yet";
    } else {
      msg += ". Known types: " + join(known, ", ");
    }

    throw std::runtime_error(msg);
  }

  void collect_enum_types(const Descriptor* descriptor, std::vector<std::string>& out) const {
    for (int i = 0; i < descriptor->enum_type_count(); ++i) {
      out.push_back(std::string(descriptor->enum_type(i)->full_name()));
    }

    for (int i = 0; i < descriptor->nested_type_count(); ++i) {
      collect_enum_types(descriptor->nested_type(i), out);
    }
  }

  // Unlike known_message_types(), this also lists enum types -- used only by
  // describe(), which can target either. to_json/from_json/find_message_type
  // keep listing message types alone, since they can never target an enum.
  std::vector<std::string> known_types() const {
    std::vector<std::string> out = known_message_types();

    for (const std::string& filename : m_filenames) {
      const FileDescriptor* file = m_pool.FindFileByName(filename);

      if (file == nullptr) continue;

      for (int i = 0; i < file->enum_type_count(); ++i) {
        out.push_back(std::string(file->enum_type(i)->full_name()));
      }

      for (int i = 0; i < file->message_type_count(); ++i) {
        collect_enum_types(file->message_type(i), out);
      }
    }

    return out;
  }

  [[noreturn]] void throw_unknown_type(const std::string& type_name) const {
    std::string msg = "Could not find message or enum type \"" + type_name + "\"";

    const std::vector<std::string> known = known_types();

    if (known.empty()) {
      msg += ". No protos have been added yet";
    } else {
      msg += ". Known types: " + join(known, ", ");
    }

    throw std::runtime_error(msg);
  }

  const Descriptor* find_message_type(const std::string& message_type) const {
    const Descriptor* descriptor = m_pool.FindMessageTypeByName(message_type);

    if (descriptor == nullptr) {
      throw_unknown_message_type(message_type);
    }

    return descriptor;
  }

  std::unique_ptr<Message> new_message(const Descriptor* descriptor, const std::string& message_type) {
    const Message* prototype = m_factory.GetPrototype(descriptor);

    if (prototype == nullptr) {
      throw std::runtime_error("Could not create a prototype for message type \"" + message_type + "\"");
    }

    std::unique_ptr<Message> message(prototype->New());

    if (message == nullptr) {
      throw std::runtime_error("Could not create an empty message of type \"" + message_type + "\"");
    }

    return message;
  }

  static void check_initialized(const Message& message, const std::string& message_type) {
    if (message.IsInitialized()) return;

    throw std::runtime_error("Message of type \"" + message_type +
                             "\" is missing required fields: " + message.InitializationErrorString());
  }

  FieldInfo describe_field(const FieldDescriptor* field) const {
    FieldInfo info;
    info.name = field->name();
    info.json_name = field->json_name();
    info.number = field->number();
    info.has_presence = field->has_presence();

    // FieldDescriptor::label() was removed from the public API; is_required()
    // and is_repeated() are the replacement primitives it used to wrap.
    FieldDescriptor::Label label = FieldDescriptor::LABEL_OPTIONAL;
    if (field->is_required()) {
      label = FieldDescriptor::LABEL_REQUIRED;
    } else if (field->is_repeated()) {
      label = FieldDescriptor::LABEL_REPEATED;
    }
    info.label = label_name(label);

    // real_containing_oneof() is null both for fields outside any oneof and
    // for the synthetic one-field oneof proto3 uses to track `optional`
    // presence, so it already excludes what OneofDescriptor::is_synthetic()
    // (a private member here) would have.
    if (const OneofDescriptor* oneof = field->real_containing_oneof(); oneof != nullptr) {
      info.oneof = oneof->name();
    }

    if (field->is_map()) {
      info.type = "map";

      // Map entry messages are synthesized with exactly two fields, "key"
      // (number 1) and "value" (number 2), always in that declaration
      // order -- a stable protobuf invariant, not an assumption about this
      // particular schema.
      const Descriptor* entry = field->message_type();
      const FieldDescriptor* key_field = entry->field(0);
      const FieldDescriptor* value_field = entry->field(1);

      info.key_type = key_field->type_name();
      info.value_type = value_field->type_name();

      if (value_field->type() == FieldDescriptor::TYPE_MESSAGE || value_field->type() == FieldDescriptor::TYPE_GROUP) {
        info.value_type_name = std::string(value_field->message_type()->full_name());
      } else if (value_field->type() == FieldDescriptor::TYPE_ENUM) {
        info.value_type_name = std::string(value_field->enum_type()->full_name());
      }

      return info;
    }

    info.type = field->type_name();

    if (field->type() == FieldDescriptor::TYPE_MESSAGE || field->type() == FieldDescriptor::TYPE_GROUP) {
      info.type_name = std::string(field->message_type()->full_name());
    } else if (field->type() == FieldDescriptor::TYPE_ENUM) {
      const EnumDescriptor* enum_descriptor = field->enum_type();
      info.type_name = std::string(enum_descriptor->full_name());

      for (int i = 0; i < enum_descriptor->value_count(); ++i) {
        const EnumValueDescriptor* value = enum_descriptor->value(i);
        info.enum_values.push_back(EnumValueInfo{std::string(value->name()), value->number()});
      }
    }

    return info;
  }

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

    PoolErrorCollector pool_errors;

    const FileDescriptor* file_desc = m_pool.BuildFileCollectingErrors(file_descriptor_proto, &pool_errors);

    if (file_desc == nullptr) {
      std::string msg = "Could not build \"" + file_descriptor_proto.name() + "\"";

      if (pool_errors.has_errors()) {
        msg += ":\n" + pool_errors.errors();
      }

      throw std::runtime_error(msg);
    }

    m_filenames.push_back(std::string(file_desc->name()));
  }

  std::string to_json(const std::string& message_type, const std::string& data, const JsonOptions& options = {}) {
    std::shared_lock lock(m_mutex);

    // get descriptor

    const Descriptor* descriptor = find_message_type(message_type);

    // generate prototype message

    std::unique_ptr<Message> message = new_message(descriptor, message_type);

    // parse data
    //
    // Parse partially first: a plain ParseFromArray also fails on a well-formed
    // message that merely lacks required fields, and cannot tell the two apart.

    if (!message->ParsePartialFromArray(data.data(), static_cast<int>(data.size()))) {
      throw std::runtime_error("Could not parse " + std::to_string(data.size()) + " bytes as message type \"" +
                               message_type + "\": the data is not valid protobuf wire format");
    }

    check_initialized(*message, message_type);

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
      throw std::runtime_error("Could not convert message of type \"" + message_type +
                               "\" to json: " + collapse_spaces(status.message()));
    }

    return out;
  }

  std::string from_json(const std::string& message_type, const std::string& data, const ParseOptions& options = {}) {
    std::shared_lock lock(m_mutex);

    // get descriptor

    const Descriptor* descriptor = find_message_type(message_type);

    // generate prototype message

    std::unique_ptr<Message> message = new_message(descriptor, message_type);

    // parse json

    util::JsonParseOptions parse_options;
    parse_options.ignore_unknown_fields = options.ignore_unknown_fields;

    absl::Status status = util::JsonStringToMessage(data, message.get(), parse_options);

    if (!status.ok()) {
      throw std::runtime_error("Could not convert json to message type \"" + message_type +
                               "\": " + collapse_spaces(status.message()));
    }

    // Checked before serializing, not after: SerializeToString happily emits a
    // proto2 message that is missing required fields, which would hand the
    // caller bytes that to_json then refuses to read back.
    check_initialized(*message, message_type);

    std::string out;

    if (!message->SerializeToString(&out)) {
      throw std::runtime_error("Could not serialize message of type \"" + message_type + "\"");
    }

    return out;
  }

  std::string message_type_from_index(const std::string& filename, const std::vector<int>& message_index) {
    if (message_index.empty()) {
      throw std::runtime_error("Message index is empty for file \"" + filename + "\"");
    }

    std::shared_lock lock(m_mutex);

    const FileDescriptor* file_descriptor = m_pool.FindFileByName(filename);

    if (file_descriptor == nullptr) {
      std::string msg = "Could not find file \"" + filename + "\"";

      if (m_filenames.empty()) {
        msg += ". No protos have been added yet";
      } else {
        msg += ". Known files: " + join(m_filenames, ", ");
      }

      throw std::runtime_error(msg);
    }

    auto it = message_index.begin();

    if (*it < 0 || file_descriptor->message_type_count() <= *it) {
      throw std::runtime_error("Message index " + std::to_string(*it) + " at position 0 is out of range: file \"" +
                               filename + "\" defines " + std::to_string(file_descriptor->message_type_count()) +
                               " top-level message(s)");
    }

    auto* descriptor = file_descriptor->message_type(*it);

    while (++it != message_index.end()) {
      if (*it < 0 || descriptor->nested_type_count() <= *it) {
        auto position = std::distance(message_index.begin(), it);
        throw std::runtime_error("Message index " + std::to_string(*it) + " at position " + std::to_string(position) +
                                 " is out of range: \"" + std::string(descriptor->full_name()) + "\" has " +
                                 std::to_string(descriptor->nested_type_count()) + " nested message(s)");
      }

      descriptor = descriptor->nested_type(*it);
    }

    return std::string(descriptor->full_name());
  }

  DescribeResult describe(const std::string& type_name) const {
    std::shared_lock lock(m_mutex);

    if (const Descriptor* descriptor = m_pool.FindMessageTypeByName(type_name); descriptor != nullptr) {
      MessageInfo info;
      info.name = std::string(descriptor->full_name());

      for (int i = 0; i < descriptor->field_count(); ++i) {
        info.fields.push_back(describe_field(descriptor->field(i)));
      }

      return DescribeResult{false, std::move(info), {}};
    }

    if (const EnumDescriptor* enum_descriptor = m_pool.FindEnumTypeByName(type_name); enum_descriptor != nullptr) {
      EnumInfo info;
      info.name = std::string(enum_descriptor->full_name());

      for (int i = 0; i < enum_descriptor->value_count(); ++i) {
        const EnumValueDescriptor* value = enum_descriptor->value(i);
        info.values.push_back(EnumValueInfo{std::string(value->name()), value->number()});
      }

      return DescribeResult{true, {}, std::move(info)};
    }

    throw_unknown_type(type_name);
  }
};

}  // namespace protosaurus
