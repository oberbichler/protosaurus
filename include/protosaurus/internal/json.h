#pragma once

#include <google/protobuf/descriptor.h>               // FileDescriptor
#include <google/protobuf/message.h>                  // Message, Reflection

#include <iosfwd>                                     // ostream
#include <stdexcept>                                  // runtime_error
#include <string>                                     // string

using namespace google::protobuf;
using namespace google::protobuf::io;
using namespace google::protobuf::compiler;

namespace protosaurus::internal {

  struct enumeration {};

  template <typename T>
  void push_val(std::ostream& out, const Message& message, const Reflection& reflection, const FieldDescriptor& field) {
    if constexpr(std::is_same<T, bool>::value) {
      out << reflection.GetBool(message, &field);
    }
    if constexpr(std::is_same<T, int32_t>::value) {
      out << reflection.GetInt32(message, &field);
    }
    if constexpr(std::is_same<T, uint32_t>::value) {
      out << reflection.GetUInt32(message, &field);
    }
    if constexpr(std::is_same<T, int64_t>::value) {
      out << reflection.GetInt64(message, &field);
    }
    if constexpr(std::is_same<T, uint64_t>::value) {
      out << reflection.GetUInt64(message, &field);
    }
    if constexpr(std::is_same<T, float>::value) {
        out << reflection.GetFloat(message, &field);
    }
    if constexpr(std::is_same<T, double>::value) {
        out << reflection.GetDouble(message, &field);
    }
    if constexpr(std::is_same<T, std::string>::value) {
      out << "\"" << reflection.GetString(message, &field) << "\"";
    }
    if constexpr(std::is_same<T, enumeration>::value) {
      out << "\"" << reflection.GetEnum(message, &field)->name() << "\"";
    }
  }

  template <typename T>
  void push_ith(std::ostream& out, const Message& message, const Reflection& reflection, const FieldDescriptor& field, const int i) {
      if constexpr(std::is_same<T, bool>::value) {
          out << reflection.GetRepeatedBool(message, &field, i);
      }
      if constexpr(std::is_same<T, int32_t>::value) {
          out << reflection.GetRepeatedInt32(message, &field, i);
      }
      if constexpr(std::is_same<T, uint32_t>::value) {
          out << reflection.GetRepeatedUInt32(message, &field, i);
      }
      if constexpr(std::is_same<T, int64_t>::value) {
          out << reflection.GetRepeatedInt64(message, &field, i);
      }
      if constexpr(std::is_same<T, uint64_t>::value) {
          out << reflection.GetRepeatedUInt64(message, &field, i);
      }
      if constexpr(std::is_same<T, float>::value) {
          out << reflection.GetRepeatedFloat(message, &field, i);
      }
      if constexpr(std::is_same<T, double>::value) {
          out << reflection.GetRepeatedDouble(message, &field, i);
      }
      if constexpr(std::is_same<T, enumeration>::value) {
          out << "\"" << reflection.GetRepeatedEnum(message, &field, i)->name() << "\"";
      }
      if constexpr(std::is_same<T, std::string>::value) {
          out << "\"" << reflection.GetRepeatedString(message, &field, i) << "\"";
      }
  }

  template <typename T>
  void push(std::ostream& out, const Message& message, const Reflection& reflection, const FieldDescriptor& field) {
    using protosaurus::internal::push_val;
    using protosaurus::internal::push_ith;

    if (field.is_repeated()) {
      out << "[";

      for (size_t i = 0; i < reflection.FieldSize(message, &field); i++) {
        if (i != 0) {
          out << ",";
        }

        push_ith<T>(out, message, reflection, field, i);
      }

      out << "]";
    } else {
      push_val<T>(out, message, reflection, field);
    }
  }

  void push_msg(std::ostream& out, const Message& message) {
    const Reflection* reflection = message.GetReflection();

    std::vector<const FieldDescriptor*> fields;

    reflection->ListFields(message, &fields);

    out << "{";

    for (auto field_it = fields.begin(); field_it != fields.end(); ++field_it) {
      if (field_it != fields.begin()) {
        out << ",";
      }

      const FieldDescriptor* field = *field_it;

      if (field == nullptr) {
        throw std::runtime_error("Error fieldDescriptor object is not defined");
        continue;
      }

      out << "\"" << field->name() << "\":";

      switch (field->type()) {
      case FieldDescriptor::Type::TYPE_ENUM:
        push<enumeration>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_BOOL:
        push<bool>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_DOUBLE:
        push<double>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_FLOAT:
        push<float>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_INT32:
      case FieldDescriptor::Type::TYPE_SINT32:
      case FieldDescriptor::Type::TYPE_SFIXED32:
        push<int32_t>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_INT64:
      case FieldDescriptor::Type::TYPE_SINT64:
      case FieldDescriptor::Type::TYPE_SFIXED64:
        push<int64_t>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_MESSAGE:
      case FieldDescriptor::Type::TYPE_GROUP:
        // FIXME: Unify
        if (field->is_repeated()) {
          out << "[";

          for (size_t i = 0; i < reflection->FieldSize(message, field); i++) {
            if (i != 0) {
              out << ",";
            }

            push_msg(out, reflection->GetRepeatedMessage(message, field, i));
          }

          out << "]";
        } else {
          push_msg(out, reflection->GetMessage(message, field));
        }
        break;
      case FieldDescriptor::Type::TYPE_STRING:
      case FieldDescriptor::Type::TYPE_BYTES:
        push<std::string>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_UINT32:
      case FieldDescriptor::Type::TYPE_FIXED32:
        push<uint32_t>(out, message, *reflection, *field);
        break;
      case FieldDescriptor::Type::TYPE_UINT64:
      case FieldDescriptor::Type::TYPE_FIXED64:
        push<uint64_t>(out, message, *reflection, *field);
        break;
      default:
        break;
      }
    }
  
    out << "}";
  }

}  // namespace protosaurus::internal