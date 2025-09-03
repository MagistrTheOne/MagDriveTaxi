#include <iostream>
#include <string>
#include <map>
#include <cstdlib>
#include <cstring>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <sstream>
#include <fstream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

class PricingService {
private:
    std::map<std::string, double> basePrices;
    double demandMultiplier;
    
public:
    PricingService() {
        // Базовые цены по классам автомобилей (в рублях за км)
        basePrices["comfort"] = 15.0;
        basePrices["business"] = 25.0;
        basePrices["xl"] = 35.0;
        
        // Коэффициент спроса (1.0 - 1.4)
        demandMultiplier = getenv("DEMAND_MULTIPLIER") ? 
            std::stod(getenv("DEMAND_MULTIPLIER")) : 1.2;
    }
    
    double calculatePrice(const std::string& vehicleClass, double distanceM, int etaSeconds) {
        auto it = basePrices.find(vehicleClass);
        if (it == basePrices.end()) {
            return 0.0; // Неизвестный класс
        }
        
        double basePrice = it->second;
        double distanceKm = distanceM / 1000.0;
        double timeMinutes = etaSeconds / 60.0;
        
        // Формула: базовая цена * расстояние + время * коэффициент + коэффициент спроса
        double price = (basePrice * distanceKm + timeMinutes * 2.0) * demandMultiplier;
        
        // Минимальная цена
        if (price < 100.0) {
            price = 100.0;
        }
        
        return price;
    }
    
    std::string generateResponse(double price, const std::string& currency = "RUB") {
        json response;
        response["data"]["price"] = price;
        response["data"]["currency"] = currency;
        response["error"] = nullptr;
        response["traceId"] = generateTraceId();
        
        return response.dump(2);
    }
    
    std::string generateErrorResponse(const std::string& error, int statusCode) {
        json response;
        response["data"] = nullptr;
        response["error"]["code"] = "PRICING_ERROR";
        response["error"]["message"] = error;
        response["error"]["statusCode"] = statusCode;
        response["traceId"] = generateTraceId();
        
        return response.dump(2);
    }
    
private:
    std::string generateTraceId() {
        static int counter = 0;
        std::ostringstream oss;
        oss << "pricing_" << std::time(nullptr) << "_" << ++counter;
        return oss.str();
    }
};

class HttpServer {
private:
    int serverSocket;
    PricingService pricingService;
    
public:
    HttpServer(int port) {
        serverSocket = socket(AF_INET, SOCK_STREAM, 0);
        if (serverSocket < 0) {
            std::cerr << "Failed to create socket" << std::endl;
            exit(1);
        }
        
        int opt = 1;
        setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
        
        struct sockaddr_in serverAddr;
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_addr.s_addr = INADDR_ANY;
        serverAddr.sin_port = htons(port);
        
        if (bind(serverSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) < 0) {
            std::cerr << "Failed to bind socket" << std::endl;
            exit(1);
        }
        
        if (listen(serverSocket, 10) < 0) {
            std::cerr << "Failed to listen" << std::endl;
            exit(1);
        }
        
        std::cout << "Pricing service started on port " << port << std::endl;
    }
    
    void run() {
        while (true) {
            struct sockaddr_in clientAddr;
            socklen_t clientLen = sizeof(clientAddr);
            
            int clientSocket = accept(serverSocket, (struct sockaddr*)&clientAddr, &clientLen);
            if (clientSocket < 0) {
                std::cerr << "Failed to accept connection" << std::endl;
                continue;
            }
            
            handleRequest(clientSocket);
            close(clientSocket);
        }
    }
    
private:
    void handleRequest(int clientSocket) {
        char buffer[4096];
        int bytesRead = recv(clientSocket, buffer, sizeof(buffer) - 1, 0);
        
        if (bytesRead <= 0) {
            return;
        }
        
        buffer[bytesRead] = '\0';
        std::string request(buffer);
        
        // Парсим HTTP запрос
        std::istringstream requestStream(request);
        std::string method, path, version;
        requestStream >> method >> path >> version;
        
        std::cout << "Request: " << method << " " << path << std::endl;
        
        if (method == "GET" && path == "/healthz") {
            sendHealthResponse(clientSocket);
        } else if (method == "GET" && path == "/readyz") {
            sendReadyResponse(clientSocket);
        } else if (method == "POST" && path == "/price") {
            handlePricingRequest(clientSocket, request);
        } else {
            sendNotFoundResponse(clientSocket);
        }
    }
    
    void handlePricingRequest(int clientSocket, const std::string& request) {
        try {
            // Извлекаем тело запроса
            size_t bodyStart = request.find("\r\n\r\n");
            if (bodyStart == std::string::npos) {
                sendErrorResponse(clientSocket, "Invalid request format", 400);
                return;
            }
            
            std::string body = request.substr(bodyStart + 4);
            json requestData = json::parse(body);
            
            // Проверяем обязательные поля
            if (!requestData.contains("distanceM") || 
                !requestData.contains("etaSec") || 
                !requestData.contains("class")) {
                sendErrorResponse(clientSocket, "Missing required fields", 400);
                return;
            }
            
            double distanceM = requestData["distanceM"];
            int etaSeconds = requestData["etaSec"];
            std::string vehicleClass = requestData["class"];
            
            // Валидация
            if (distanceM <= 0 || etaSeconds <= 0) {
                sendErrorResponse(clientSocket, "Invalid distance or ETA", 400);
                return;
            }
            
            // Рассчитываем цену
            double price = pricingService.calculatePrice(vehicleClass, distanceM, etaSeconds);
            
            if (price <= 0) {
                sendErrorResponse(clientSocket, "Invalid vehicle class", 400);
                return;
            }
            
            // Отправляем ответ
            std::string response = pricingService.generateResponse(price);
            sendJsonResponse(clientSocket, response);
            
        } catch (const json::exception& e) {
            sendErrorResponse(clientSocket, "Invalid JSON", 400);
        } catch (const std::exception& e) {
            sendErrorResponse(clientSocket, "Internal server error", 500);
        }
    }
    
    void sendHealthResponse(int clientSocket) {
        json healthData;
        healthData["status"] = "healthy";
        healthData["timestamp"] = std::to_string(std::time(nullptr));
        healthData["service"] = "pricing-service";
        
        std::string response = healthData.dump(2);
        sendJsonResponse(clientSocket, response);
    }
    
    void sendReadyResponse(int clientSocket) {
        json readyData;
        readyData["status"] = "ready";
        readyData["timestamp"] = std::to_string(std::time(nullptr));
        readyData["service"] = "pricing-service";
        
        std::string response = readyData.dump(2);
        sendJsonResponse(clientSocket, response);
    }
    
    void sendErrorResponse(int clientSocket, const std::string& error, int statusCode) {
        std::string response = pricingService.generateErrorResponse(error, statusCode);
        sendJsonResponse(clientSocket, response, statusCode);
    }
    
    void sendNotFoundResponse(int clientSocket) {
        sendErrorResponse(clientSocket, "Not found", 404);
    }
    
    void sendJsonResponse(int clientSocket, const std::string& jsonData, int statusCode = 200) {
        std::string statusText = (statusCode == 200) ? "OK" : 
                                (statusCode == 400) ? "Bad Request" :
                                (statusCode == 404) ? "Not Found" :
                                (statusCode == 500) ? "Internal Server Error" : "Unknown";
        
        std::ostringstream response;
        response << "HTTP/1.1 " << statusCode << " " << statusText << "\r\n";
        response << "Content-Type: application/json\r\n";
        response << "Content-Length: " << jsonData.length() << "\r\n";
        response << "Access-Control-Allow-Origin: *\r\n";
        response << "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n";
        response << "Access-Control-Allow-Headers: Content-Type\r\n";
        response << "\r\n";
        response << jsonData;
        
        std::string fullResponse = response.str();
        send(clientSocket, fullResponse.c_str(), fullResponse.length(), 0);
    }
    
    ~HttpServer() {
        if (serverSocket >= 0) {
            close(serverSocket);
        }
    }
};

int main() {
    int port = getenv("PORT") ? std::stoi(getenv("PORT")) : 7010;
    
    try {
        HttpServer server(port);
        server.run();
    } catch (const std::exception& e) {
        std::cerr << "Server error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
