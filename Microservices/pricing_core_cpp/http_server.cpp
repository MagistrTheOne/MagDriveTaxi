#include "http_server.h"
#include "pricing_engine.h"
#include <iostream>
#include <sstream>
#include <cstring>
#include <ctime>

namespace magadrive {

HttpServer::HttpServer(int port) : daemon_(nullptr), port_(port), running_(false) {
    // Регистрируем стандартные обработчики
    registerHandler("/healthz", "GET", healthHandler);
    registerHandler("/readyz", "GET", healthHandler);
    registerHandler("/pricing", "POST", pricingHandler);
    registerHandler("/price", "POST", pricingHandler);
}

HttpServer::~HttpServer() {
    stop();
}

bool HttpServer::start() {
    if (running_) {
        return true;
    }
    
    daemon_ = MHD_start_daemon(MHD_USE_SELECT_INTERNALLY, port_, nullptr, nullptr,
                               &HttpServer::requestCallback, this,
                               MHD_OPTION_END);
    
    if (daemon_ == nullptr) {
        std::cerr << "Failed to start HTTP server on port " << port_ << std::endl;
        return false;
    }
    
    running_ = true;
    std::cout << "HTTP server started on port " << port_ << std::endl;
    return true;
}

void HttpServer::stop() {
    if (daemon_) {
        MHD_stop_daemon(daemon_);
        daemon_ = nullptr;
    }
    running_ = false;
}

void HttpServer::registerHandler(const std::string& path, const std::string& method, RequestHandler handler) {
    handlers_[path][method] = handler;
}

int HttpServer::requestCallback(void* cls, struct MHD_Connection* connection,
                              const char* url, const char* method,
                              const char* version, const char* upload_data,
                              size_t* upload_data_size, void** con_cls) {
    HttpServer* server = static_cast<HttpServer*>(cls);
    
    if (*con_cls == nullptr) {
        // Первый вызов - создаем контекст
        *con_cls = server;
        return MHD_YES;
    }
    
    // Обрабатываем запрос
    std::string response = server->handleRequest(url, method);
    
    // Создаем HTTP ответ
    struct MHD_Response* mhd_response = MHD_create_response_from_buffer(
        response.length(), const_cast<char*>(response.c_str()),
        MHD_RESPMEM_MUST_COPY);
    
    if (mhd_response == nullptr) {
        return MHD_NO;
    }
    
    // Добавляем заголовки
    MHD_add_response_header(mhd_response, "Content-Type", "application/json");
    MHD_add_response_header(mhd_response, "Access-Control-Allow-Origin", "*");
    
    // Отправляем ответ
    int ret = MHD_queue_response(connection, MHD_HTTP_OK, mhd_response);
    MHD_destroy_response(mhd_response);
    
    return ret;
}

void HttpServer::requestCompletedCallback(void* cls, struct MHD_Connection* connection,
                                        void** con_cls, enum MHD_RequestTerminationCode toe) {
    // Очистка ресурсов
}

std::string HttpServer::handleRequest(const std::string& url, const std::string& method) {
    auto path_it = handlers_.find(url);
    if (path_it == handlers_.end()) {
        return createResponse("{\"error\": \"Not found\"}", 404);
    }
    
    auto method_it = path_it->second.find(method);
    if (method_it == path_it->second.end()) {
        return createResponse("{\"error\": \"Method not allowed\"}", 405);
    }
    
    return method_it->second(url, method);
}

std::string HttpServer::createResponse(const std::string& content, int status_code) {
    std::ostringstream oss;
    oss << "HTTP/1.1 " << status_code << " OK\r\n";
    oss << "Content-Length: " << content.length() << "\r\n";
    oss << "Content-Type: application/json\r\n";
    oss << "\r\n";
    oss << content;
    return oss.str();
}

std::string HttpServer::createHealthResponse() {
    time_t now = time(nullptr);
    struct tm* timeinfo = localtime(&now);
    
    std::ostringstream oss;
    oss << "{";
    oss << "\"status\": \"healthy\",";
    oss << "\"timestamp\": \"" << std::put_time(timeinfo, "%Y-%m-%dT%H:%M:%SZ") << "\",";
    oss << "\"service\": \"pricing-core-cpp\"";
    oss << "}";
    
    return oss.str();
}

std::string HttpServer::createPricingResponse(const std::string& request_body) {
    // Парсим запрос
    double distance_m;
    std::string vehicle_class;
    int base_price;
    
    if (!parsePricingRequest(request_body, distance_m, vehicle_class, base_price)) {
        return "{\"error\": \"Invalid request format\"}";
    }
    
    // Создаем pricing engine и рассчитываем цену
    PricingEngine engine;
    
    PricingRequest request;
    request.distance_m = distance_m;
    request.base_price_rub = base_price;
    request.surge_multiplier = 1.0;
    request.time_of_day_multiplier = 1.0;
    
    // Определяем класс автомобиля
    if (vehicle_class == "comfort") {
        request.vehicle_class = VehicleClass::COMFORT;
    } else if (vehicle_class == "business") {
        request.vehicle_class = VehicleClass::BUSINESS;
    } else if (vehicle_class == "xl") {
        request.vehicle_class = VehicleClass::XL;
    } else {
        request.vehicle_class = VehicleClass::COMFORT;
    }
    
    PricingResponse response = engine.calculatePrice(request);
    
    // Формируем JSON ответ
    std::ostringstream oss;
    oss << "{";
    oss << "\"finalPriceRub\": " << response.final_price_rub << ",";
    oss << "\"distanceMultiplier\": " << response.distance_multiplier << ",";
    oss << "\"classMultiplier\": " << response.class_multiplier << ",";
    oss << "\"surgeMultiplier\": " << response.surge_multiplier << ",";
    oss << "\"timeMultiplier\": " << response.time_multiplier << ",";
    oss << "\"currency\": \"" << response.currency << "\"";
    oss << "}";
    
    return oss.str();
}

bool HttpServer::parsePricingRequest(const std::string& json, double& distance_m, 
                                   std::string& vehicle_class, int& base_price) {
    // Упрощенный парсинг JSON для MVP
    // В реальном приложении использовать nlohmann/json или rapidjson
    
    // Ищем ключевые значения
    size_t pos = json.find("\"distanceM\"");
    if (pos != std::string::npos) {
        pos = json.find(":", pos);
        if (pos != std::string::npos) {
            distance_m = std::stod(json.substr(pos + 1));
        }
    }
    
    pos = json.find("\"vehicleClass\"");
    if (pos != std::string::npos) {
        pos = json.find("\"", pos + 14);
        if (pos != std::string::npos) {
            size_t end_pos = json.find("\"", pos + 1);
            if (end_pos != std::string::npos) {
                vehicle_class = json.substr(pos + 1, end_pos - pos - 1);
            }
        }
    }
    
    pos = json.find("\"basePriceRub\"");
    if (pos != std::string::npos) {
        pos = json.find(":", pos);
        if (pos != std::string::npos) {
            base_price = std::stoi(json.substr(pos + 1));
        }
    }
    
    return true; // Упрощенно для MVP
}

std::string HttpServer::healthHandler(const std::string& url, const std::string& method) {
    HttpServer* server = static_cast<HttpServer*>(nullptr); // Временное решение
    return server->createHealthResponse();
}

std::string HttpServer::pricingHandler(const std::string& url, const std::string& method) {
    HttpServer* server = static_cast<HttpServer*>(nullptr); // Временное решение
    return server->createPricingResponse("{}"); // Пустой запрос для MVP
}

} // namespace magadrive
