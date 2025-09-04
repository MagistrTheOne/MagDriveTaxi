//
//  nlohmann/json.hpp - JSON for Modern C++
//  
//  NOTE: This is a STUB for MagaDrive T8-T10 demo
//  In production, use the full nlohmann/json.hpp from: https://github.com/nlohmann/json
//

#pragma once

#include <string>
#include <map>
#include <vector>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace nlohmann {

// Simplified JSON class for demo purposes
class json {
private:
    enum class value_type { null, boolean, number, string, array, object };
    
    value_type type = value_type::null;
    std::string string_value;
    double number_value = 0.0;
    bool boolean_value = false;
    std::map<std::string, json> object_value;
    std::vector<json> array_value;

public:
    // Constructors
    json() : type(value_type::null) {}
    json(std::nullptr_t) : type(value_type::null) {}
    json(bool b) : type(value_type::boolean), boolean_value(b) {}
    json(int i) : type(value_type::number), number_value(static_cast<double>(i)) {}
    json(double d) : type(value_type::number), number_value(d) {}
    json(const std::string& s) : type(value_type::string), string_value(s) {}
    json(const char* s) : type(value_type::string), string_value(s) {}
    
    // Initializer list constructor for objects
    json(std::initializer_list<std::pair<std::string, json>> init) : type(value_type::object) {
        for (const auto& pair : init) {
            object_value[pair.first] = pair.second;
        }
    }
    
    // Array access
    json& operator[](size_t index) {
        if (type != value_type::array) {
            type = value_type::array;
            array_value.clear();
        }
        if (index >= array_value.size()) {
            array_value.resize(index + 1);
        }
        return array_value[index];
    }
    
    // Object access
    json& operator[](const std::string& key) {
        if (type != value_type::object) {
            type = value_type::object;
            object_value.clear();
        }
        return object_value[key];
    }
    
    const json& operator[](const std::string& key) const {
        if (type != value_type::object) {
            throw std::runtime_error("Not an object");
        }
        auto it = object_value.find(key);
        if (it == object_value.end()) {
            throw std::runtime_error("Key not found: " + key);
        }
        return it->second;
    }
    
    // at() methods
    const json& at(const std::string& key) const {
        return (*this)[key];
    }
    
    json& at(const std::string& key) {
        return (*this)[key];
    }
    
    // Type checking
    bool contains(const std::string& key) const {
        return type == value_type::object && object_value.find(key) != object_value.end();
    }
    
    bool is_null() const { return type == value_type::null; }
    bool is_boolean() const { return type == value_type::boolean; }
    bool is_number() const { return type == value_type::number; }
    bool is_string() const { return type == value_type::string; }
    bool is_array() const { return type == value_type::array; }
    bool is_object() const { return type == value_type::object; }
    
    // Value extraction
    template<typename T>
    T get() const;
    
    template<typename T>
    T value(const std::string& key, const T& default_value) const {
        if (type == value_type::object) {
            auto it = object_value.find(key);
            if (it != object_value.end()) {
                return it->second.get<T>();
            }
        }
        return default_value;
    }
    
    // Serialization
    std::string dump(int indent = -1) const {
        std::ostringstream oss;
        dump_to_stream(oss, indent, 0);
        return oss.str();
    }
    
    // Static parsing method
    static json parse(const std::string& str) {
        // Simplified parser - in real implementation this would be much more complex
        json result;
        
        // For demo purposes, just handle basic cases
        if (str.find("distanceM") != std::string::npos) {
            // Simulate parsing price request
            result.type = value_type::object;
            result["distanceM"] = 5000.0;
            result["etaSec"] = 600.0;
            result["class"] = std::string("comfort");
        }
        
        return result;
    }
    
private:
    void dump_to_stream(std::ostringstream& oss, int indent, int current_indent) const {
        auto add_indent = [&]() {
            if (indent >= 0) {
                oss << std::string(current_indent, ' ');
            }
        };
        
        switch (type) {
            case value_type::null:
                oss << "null";
                break;
                
            case value_type::boolean:
                oss << (boolean_value ? "true" : "false");
                break;
                
            case value_type::number:
                oss << number_value;
                break;
                
            case value_type::string:
                oss << "\"" << string_value << "\"";
                break;
                
            case value_type::array:
                oss << "[";
                if (indent >= 0) oss << "\n";
                
                for (size_t i = 0; i < array_value.size(); ++i) {
                    if (i > 0) {
                        oss << ",";
                        if (indent >= 0) oss << "\n";
                    }
                    if (indent >= 0) add_indent();
                    array_value[i].dump_to_stream(oss, indent, current_indent + indent);
                }
                
                if (indent >= 0) {
                    oss << "\n";
                    add_indent();
                }
                oss << "]";
                break;
                
            case value_type::object:
                oss << "{";
                if (indent >= 0) oss << "\n";
                
                bool first = true;
                for (const auto& pair : object_value) {
                    if (!first) {
                        oss << ",";
                        if (indent >= 0) oss << "\n";
                    }
                    first = false;
                    
                    if (indent >= 0) {
                        oss << std::string(current_indent + indent, ' ');
                    }
                    
                    oss << "\"" << pair.first << "\":";
                    if (indent >= 0) oss << " ";
                    
                    pair.second.dump_to_stream(oss, indent, current_indent + indent);
                }
                
                if (indent >= 0) {
                    oss << "\n";
                    add_indent();
                }
                oss << "}";
                break;
        }
    }
};

// Template specializations for get<T>()
template<>
inline double json::get<double>() const {
    if (type != value_type::number) {
        throw std::runtime_error("Not a number");
    }
    return number_value;
}

template<>
inline int json::get<int>() const {
    if (type != value_type::number) {
        throw std::runtime_error("Not a number");
    }
    return static_cast<int>(number_value);
}

template<>
inline std::string json::get<std::string>() const {
    if (type != value_type::string) {
        throw std::runtime_error("Not a string");
    }
    return string_value;
}

template<>
inline bool json::get<bool>() const {
    if (type != value_type::boolean) {
        throw std::runtime_error("Not a boolean");
    }
    return boolean_value;
}

// Exception class
class parse_error : public std::runtime_error {
public:
    explicit parse_error(const std::string& msg) : std::runtime_error(msg) {}
};

} // namespace nlohmann
