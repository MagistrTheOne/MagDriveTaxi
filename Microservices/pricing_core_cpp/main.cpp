#include <iostream>
#include <string>
#include <map>
#include <cmath>
#include <cstdlib>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <random>
#include <thread>

// Simple HTTP server using httplib.h (header-only)
#include "httplib.h"
#include "nlohmann/json.hpp"

using json = nlohmann::json;
using namespace std;

// Конфигурация из переменных окружения
struct Config {
    int port;
    double base_price;
    double price_per_km;
    double price_per_minute;
    double demand_coefficient_min;
    double demand_coefficient_max;
    
    Config() {
        port = getenv("PORT") ? atoi(getenv("PORT")) : 8003;
        base_price = getenv("BASE_PRICE") ? atof(getenv("BASE_PRICE")) : 100.0;
        price_per_km = getenv("PRICE_PER_KM") ? atof(getenv("PRICE_PER_KM")) : 15.0;
        price_per_minute = getenv("PRICE_PER_MINUTE") ? atof(getenv("PRICE_PER_MINUTE")) : 3.0;
        demand_coefficient_min = getenv("DEMAND_COEFF_MIN") ? atof(getenv("DEMAND_COEFF_MIN")) : 1.0;
        demand_coefficient_max = getenv("DEMAND_COEFF_MAX") ? atof(getenv("DEMAND_COEFF_MAX")) : 1.4;
    }
};

// Структура запроса на расчет цены
struct PriceRequest {
    double distanceM;
    double etaSec;
    string vehicleClass;
    
    bool fromJson(const json& j) {
        try {
            distanceM = j.at("distanceM").get<double>();
            etaSec = j.at("etaSec").get<double>();
            vehicleClass = j.value("class", "economy");
            return true;
        } catch (const exception& e) {
            cerr << "Error parsing PriceRequest: " << e.what() << endl;
            return false;
        }
    }
};

// Класс для расчета цен
class PricingEngine {
private:
    Config config;
    mt19937 rng;
    
public:
    PricingEngine() : rng(chrono::steady_clock::now().time_since_epoch().count()) {}
    
    json calculatePrice(const PriceRequest& request, const string& traceId) {
        try {
            // Базовая цена
            double price = config.base_price;
            
            // Цена за расстояние
            double distanceKm = request.distanceM / 1000.0;
            price += distanceKm * config.price_per_km;
            
            // Цена за время
            double etaMinutes = request.etaSec / 60.0;
            price += etaMinutes * config.price_per_minute;
            
            // Коэффициент класса автомобиля
            double classMultiplier = getClassMultiplier(request.vehicleClass);
            price *= classMultiplier;
            
            // Коэффициент спроса (случайный в диапазоне)
            uniform_real_distribution<double> demand_dist(config.demand_coefficient_min, config.demand_coefficient_max);
            double demandCoeff = demand_dist(rng);
            price *= demandCoeff;
            
            // Округляем до рублей
            price = round(price);
            
            // Логируем расчет
            logPriceCalculation(request, price, classMultiplier, demandCoeff, traceId);
            
            return {
                {"data", {
                    {"price", price},
                    {"currency", "RUB"},
                    {"breakdown", {
                        {"base", config.base_price},
                        {"distance", round(distanceKm * config.price_per_km)},
                        {"time", round(etaMinutes * config.price_per_minute)},
                        {"classMultiplier", classMultiplier},
                        {"demandCoeff", round(demandCoeff * 100) / 100.0}
                    }}
                }},
                {"error", nullptr},
                {"traceId", traceId}
            };
            
        } catch (const exception& e) {
            cerr << "[ERROR] Price calculation failed: " << e.what() << " (traceId: " << traceId << ")" << endl;
            
            return {
                {"data", nullptr},
                {"error", {
                    {"code", "PRICE_CALCULATION_FAILED"},
                    {"message", e.what()}
                }},
                {"traceId", traceId}
            };
        }
    }
    
private:
    double getClassMultiplier(const string& vehicleClass) {
        if (vehicleClass == "economy") return 1.0;
        if (vehicleClass == "comfort") return 1.3;
        if (vehicleClass == "business") return 1.8;
        if (vehicleClass == "premium") return 2.5;
        return 1.0; // default
    }
    
    void logPriceCalculation(const PriceRequest& request, double price, double classMultiplier, double demandCoeff, const string& traceId) {
        auto now = chrono::system_clock::now();
        auto time_t = chrono::system_clock::to_time_t(now);
        
        json logEntry = {
            {"timestamp", put_time(gmtime(&time_t), "%Y-%m-%d %H:%M:%S")},
            {"level", "INFO"},
            {"message", "Price calculated"},
            {"traceId", traceId},
            {"details", {
                {"distanceKm", round((request.distanceM / 1000.0) * 10) / 10.0},
                {"etaMinutes", round((request.etaSec / 60.0) * 10) / 10.0},
                {"vehicleClass", request.vehicleClass},
                {"price", price},
                {"classMultiplier", classMultiplier},
                {"demandCoeff", demandCoeff}
            }}
        };
        
        cout << logEntry.dump() << endl;
    }
};

// Глобальный движок расчета цен
PricingEngine pricingEngine;

// Получение текущего времени в ISO формате
string getCurrentTimestamp() {
    auto now = chrono::system_clock::now();
    auto time_t = chrono::system_clock::to_time_t(now);
    stringstream ss;
    ss << put_time(gmtime(&time_t), "%Y-%m-%dT%H:%M:%SZ");
    return ss.str();
}

// Генерация UUID (простая версия)
string generateUUID() {
    random_device rd;
    mt19937 gen(rd());
    uniform_int_distribution<> dis(0, 15);
    
    const char* chars = "0123456789abcdef";
    string uuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx";
    
    for (char& c : uuid) {
        if (c == 'x') {
            c = chars[dis(gen)];
        } else if (c == 'y') {
            c = chars[(dis(gen) & 0x3) | 0x8];
        }
    }
    
    return uuid;
}

// Логирование запросов
void logRequest(const string& method, const string& path, const string& traceId) {
    json logEntry = {
        {"timestamp", getCurrentTimestamp()},
        {"level", "INFO"},
        {"message", "Request: " + method + " " + path},
        {"traceId", traceId}
    };
    cout << logEntry.dump() << endl;
}

int main() {
    Config config;
    
    cout << "🚗 MagaDrive Pricing Service T8-T10 starting on port " << config.port << endl;
    
    httplib::Server server;
    
    // CORS middleware
    server.set_pre_routing_handler([](const httplib::Request& req, httplib::Response& res) {
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id");
        return httplib::Server::HandlerResponse::Unhandled;
    });
    
    // OPTIONS handler for CORS
    server.Options(R"(.*)", [](const httplib::Request& req, httplib::Response& res) {
        res.status = 200;
        return;
    });
    
    // Health check endpoint
    server.Get("/healthz", [](const httplib::Request& req, httplib::Response& res) {
        json response = {
            {"status", "healthy"},
            {"timestamp", getCurrentTimestamp()},
            {"service", "pricing-core-cpp"}
        };
        
        res.set_content(response.dump(), "application/json");
    });
    
    // Ready check endpoint
    server.Get("/readyz", [&config](const httplib::Request& req, httplib::Response& res) {
        json response = {
            {"status", "ready"},
            {"timestamp", getCurrentTimestamp()},
            {"config", {
                {"basePrice", config.base_price},
                {"pricePerKm", config.price_per_km},
                {"pricePerMinute", config.price_per_minute}
            }}
        };
        
        res.set_content(response.dump(), "application/json");
    });
    
    // Price calculation endpoint
    server.Post("/price", [](const httplib::Request& req, httplib::Response& res) {
        // Получаем traceId из заголовка или генерируем новый
        string traceId = req.get_header_value("X-Request-Id");
        if (traceId.empty()) {
            traceId = generateUUID();
        }
        
        logRequest("POST", "/price", traceId);
        
        try {
            // Парсим JSON запрос
            json requestJson = json::parse(req.body);
            PriceRequest priceRequest;
            
            if (!priceRequest.fromJson(requestJson)) {
                json errorResponse = {
                    {"data", nullptr},
                    {"error", {
                        {"code", "INVALID_REQUEST"},
                        {"message", "Invalid request format"}
                    }},
                    {"traceId", traceId}
                };
                
                res.status = 400;
                res.set_content(errorResponse.dump(), "application/json");
                return;
            }
            
            // Валидация входных данных
            if (priceRequest.distanceM <= 0 || priceRequest.etaSec <= 0) {
                json errorResponse = {
                    {"data", nullptr},
                    {"error", {
                        {"code", "INVALID_PARAMETERS"},
                        {"message", "Distance and ETA must be positive"}
                    }},
                    {"traceId", traceId}
                };
                
                res.status = 400;
                res.set_content(errorResponse.dump(), "application/json");
                return;
            }
            
            // Расчитываем цену
            json priceResponse = pricingEngine.calculatePrice(priceRequest, traceId);
            
            // Добавляем заголовок traceId
            res.set_header("X-Request-Id", traceId);
            res.set_content(priceResponse.dump(), "application/json");
            
        } catch (const json::parse_error& e) {
            json errorResponse = {
                {"data", nullptr},
                {"error", {
                    {"code", "JSON_PARSE_ERROR"},
                    {"message", "Invalid JSON format"}
                }},
                {"traceId", traceId}
            };
            
            res.status = 400;
            res.set_content(errorResponse.dump(), "application/json");
            
        } catch (const exception& e) {
            json errorResponse = {
                {"data", nullptr},
                {"error", {
                    {"code", "INTERNAL_ERROR"},
                    {"message", e.what()}
                }},
                {"traceId", traceId}
            };
            
            res.status = 500;
            res.set_content(errorResponse.dump(), "application/json");
        }
    });
    
    // Запуск сервера
    cout << "🚀 Pricing Service listening on http://0.0.0.0:" << config.port << endl;
    
    if (!server.listen("0.0.0.0", config.port)) {
        cerr << "❌ Failed to start server on port " << config.port << endl;
        return 1;
    }
    
    return 0;
}
