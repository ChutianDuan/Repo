cmake_minimum_required(VERSION 3.16)
project(cpp_gateway LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Drogon CONFIG REQUIRED)

add_executable(cpp_gateway
    src/main.cc
    src/PythonApiClient.cc
    src/HealthService.cc
    src/DocumentService.cc
)

target_include_directories(cpp_gateway PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(cpp_gateway PRIVATE Drogon::Drogon)