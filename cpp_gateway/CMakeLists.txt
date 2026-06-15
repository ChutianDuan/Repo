cmake_minimum_required(VERSION 3.16)

if(NOT CMAKE_TOOLCHAIN_FILE)
    set(_vcpkg_roots)

    if(DEFINED ENV{VCPKG_ROOT})
        list(APPEND _vcpkg_roots "$ENV{VCPKG_ROOT}")
    endif()
    if(DEFINED ENV{VCPKG_INSTALLATION_ROOT})
        list(APPEND _vcpkg_roots "$ENV{VCPKG_INSTALLATION_ROOT}")
    endif()

    find_program(_vcpkg_executable NAMES vcpkg)
    if(_vcpkg_executable)
        get_filename_component(_vcpkg_root_from_executable "${_vcpkg_executable}" DIRECTORY)
        list(APPEND _vcpkg_roots "${_vcpkg_root_from_executable}")
    endif()

    if(DEFINED ENV{HOME})
        list(APPEND _vcpkg_roots "$ENV{HOME}/vcpkg")
    endif()
    list(APPEND _vcpkg_roots "/opt/vcpkg" "/usr/local/vcpkg")

    foreach(_vcpkg_root IN LISTS _vcpkg_roots)
        if(_vcpkg_root AND EXISTS "${_vcpkg_root}/scripts/buildsystems/vcpkg.cmake")
            set(
                CMAKE_TOOLCHAIN_FILE
                "${_vcpkg_root}/scripts/buildsystems/vcpkg.cmake"
                CACHE FILEPATH
                "vcpkg toolchain file"
            )
            message(STATUS "Using vcpkg toolchain: ${CMAKE_TOOLCHAIN_FILE}")
            break()
        endif()
    endforeach()

    unset(_vcpkg_executable CACHE)
    unset(_vcpkg_root_from_executable)
    unset(_vcpkg_roots)
endif()

project(cpp_gateway LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Drogon CONFIG REQUIRED)
find_package(CURL REQUIRED)

add_executable(cpp_gateway
    src/main.cc

    src/common/ErrorMapper.cc
    src/common/GatewayConfig.cc
    src/common/GatewaySecurity.cc

    src/clients/PythonApiClient.cc
    src/clients/PythonSSEClient.cc

    src/handlers/HealthHandler.cc
    src/handlers/DocumentHandler.cc
    src/handlers/SessionHandler.cc
    src/handlers/ChatHandler.cc
    src/handlers/StreamChatHandler.cc
)

target_include_directories(cpp_gateway PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(cpp_gateway PRIVATE
    Drogon::Drogon
    CURL::libcurl
)
