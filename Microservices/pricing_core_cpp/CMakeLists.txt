cmake_minimum_required(VERSION 3.16)
project(pricing_core_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Находим необходимые пакеты
find_package(PkgConfig REQUIRED)
find_package(Threads REQUIRED)

# Находим libmicrohttpd
pkg_check_modules(MICROHTTPD REQUIRED libmicrohttpd)

# Исходные файлы
set(SOURCES
    main.cpp
    pricing_engine.cpp
    http_server.cpp
)

# Создаем исполняемый файл
add_executable(pricing_core_cpp ${SOURCES})

# Подключаем заголовочные файлы
target_include_directories(pricing_core_cpp PRIVATE ${MICROHTTPD_INCLUDE_DIRS})

# Линкуем библиотеки
target_link_libraries(pricing_core_cpp 
    ${MICROHTTPD_LIBRARIES}
    Threads::Threads
    m
)

# Флаги компиляции
target_compile_options(pricing_core_cpp PRIVATE ${MICROHTTPD_CFLAGS_OTHER})

# Устанавливаем порт
target_compile_definitions(pricing_core_cpp PRIVATE 
    DEFAULT_PORT=7010
)

# Устанавливаем права на выполнение
set_target_properties(pricing_core_cpp PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}
)
