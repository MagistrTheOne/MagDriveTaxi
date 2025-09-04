cmake_minimum_required(VERSION 3.16)
project(pricing_core_cpp VERSION 1.0.0 LANGUAGES CXX)

# C++17 стандарт
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Настройки компилятора
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -O2")

# Поиск зависимостей
find_package(Threads REQUIRED)

# Проверяем наличие pkg-config для поиска библиотек
find_package(PkgConfig)

# Пытаемся найти OpenSSL (может потребоваться для httplib)
find_package(OpenSSL)
if(OpenSSL_FOUND)
    message(STATUS "Found OpenSSL: ${OPENSSL_VERSION}")
else()
    message(STATUS "OpenSSL not found - HTTPS support disabled")
endif()

# Создаем исполняемый файл
add_executable(pricing_service
    main.cpp
)

# Подключаем библиотеки
target_link_libraries(pricing_service 
    Threads::Threads
)

# Если найден OpenSSL, подключаем его
if(OpenSSL_FOUND)
    target_link_libraries(pricing_service OpenSSL::SSL OpenSSL::Crypto)
    target_compile_definitions(pricing_service PRIVATE CPPHTTPLIB_OPENSSL_SUPPORT)
endif()

# Настройки для Windows
if(WIN32)
    target_link_libraries(pricing_service ws2_32 wsock32)
endif()

# Настройки для Linux/Unix
if(UNIX)
    target_link_libraries(pricing_service pthread)
endif()

# Включаем заголовочные файлы из vendor
target_include_directories(pricing_service PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/vendor
)

# Компилируем с поддержкой многопоточности
target_compile_definitions(pricing_service PRIVATE 
    CPPHTTPLIB_THREAD_POOL_COUNT=4
)

# Установка
install(TARGETS pricing_service
    RUNTIME DESTINATION bin
)

# Копируем vendor файлы при сборке (если нужно)
file(GLOB VENDOR_HEADERS "vendor/*.h" "vendor/*.hpp")
if(VENDOR_HEADERS)
    message(STATUS "Found vendor headers: ${VENDOR_HEADERS}")
endif()

# Настройки для Debug/Release
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_definitions(pricing_service PRIVATE DEBUG=1)
    set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g -O0")
else()
    target_compile_definitions(pricing_service PRIVATE NDEBUG=1)
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
endif()

# Информация о сборке
message(STATUS "=== MagaDrive Pricing Service C++ ===")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
