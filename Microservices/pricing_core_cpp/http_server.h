#pragma once

#include <microhttpd.h>
#include <string>
#include <functional>
#include <map>

namespace magadrive {

class HttpServer {
public:
    using RequestHandler = std::function<std::string(const std::string&, const std::string&)>;
    
    HttpServer(int port = 7010);
    ~HttpServer();
    
    // Запуск и остановка сервера
    bool start();
    void stop();
    
    // Регистрация обработчиков
    void registerHandler(const std::string& path, const std::string& method, RequestHandler handler);
    
    // Геттеры
    bool isRunning() const { return running_; }
    int getPort() const { return port_; }
    
private:
    // Callback функции для libmicrohttpd
    static int requestCallback(void* cls, struct MHD_Connection* connection,
                             const char* url, const char* method,
                             const char* version, const char* upload_data,
                             size_t* upload_data_size, void** con_cls);
    
    static void requestCompletedCallback(void* cls, struct MHD_Connection* connection,
                                       void** con_cls, enum MHD_RequestTerminationCode toe);
    
    // Внутренние методы
    std::string handleRequest(const std::string& url, const std::string& method);
    std::string createResponse(const std::string& content, int status_code = 200);
    std::string createHealthResponse();
    std::string createPricingResponse(const std::string& request_body);
    
    // Парсинг JSON (упрощенный)
    bool parsePricingRequest(const std::string& json, double& distance_m, 
                           std::string& vehicle_class, int& base_price);
    
private:
    struct MHD_Daemon* daemon_;
    int port_;
    bool running_;
    
    // Обработчики запросов
    std::map<std::string, std::map<std::string, RequestHandler>> handlers_;
    
    // Статические обработчики
    static std::string healthHandler(const std::string& url, const std::string& method);
    static std::string pricingHandler(const std::string& url, const std::string& method);
};

} // namespace magadrive
