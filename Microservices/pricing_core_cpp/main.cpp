#include "http_server.h"
#include <iostream>
#include <csignal>
#include <cstdlib>

namespace magadrive {

HttpServer* g_server = nullptr;

void signalHandler(int signum) {
    std::cout << "Received signal " << signum << ", shutting down..." << std::endl;
    if (g_server) {
        g_server->stop();
    }
    exit(signum);
}

} // namespace magadrive

int main(int argc, char* argv[]) {
    using namespace magadrive;
    
    // Получаем порт из аргументов или используем по умолчанию
    int port = 7010;
    if (argc > 1) {
        port = std::atoi(argv[1]);
    }
    
    // Устанавливаем обработчик сигналов
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);
    
    // Создаем и запускаем сервер
    HttpServer server(port);
    g_server = &server;
    
    if (!server.start()) {
        std::cerr << "Failed to start server" << std::endl;
        return 1;
    }
    
    std::cout << "Pricing service started on port " << port << std::endl;
    std::cout << "Press Ctrl+C to stop" << std::endl;
    
    // Основной цикл
    while (server.isRunning()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    
    std::cout << "Pricing service stopped" << std::endl;
    return 0;
}
