// KidsWin External Executor - CMakeLists.txt
// Build KidsWinAPI.dll

cmake_minimum_required(VERSION 3.15)
project(KidsWin VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Windows specific settings
if(WIN32)
    add_definitions(-D_WIN32_WINNT=0x0601)
    add_definitions(-DWINDOWS)
    add_definitions(-DKIDSWIN_EXPORTS)
endif()

# Third-party headers (cpp-httplib is header-only)
# Download from: https://github.com/yhirose/cpp-httplib
# Place httplib.h in third_party/ directory
include_directories(${CMAKE_SOURCE_DIR}/src/third_party)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)
include_directories(${CMAKE_SOURCE_DIR}/src)

# Create shared library (DLL on Windows)
add_library(KidsWinAPI SHARED
    src/exports.cpp
    # Add these when implementing full functionality:
    # src/executor.cpp
    # src/http_server.cpp  
    # src/luau_compiler.cpp
    # src/blake3.cpp
    # src/zstd_compress.cpp
)

# Link Windows libraries
target_link_libraries(KidsWinAPI PRIVATE
    ws2_32
    winhttp
    ntdll
)

# Set output name and properties
set_target_properties(KidsWinAPI PROPERTIES
    OUTPUT_NAME "KidsWinAPI"
    PREFIX ""
    SUFFIX ".dll"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin
)

# Optimization flags
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    if(MSVC)
        target_compile_options(KidsWinAPI PRIVATE /O2 /W4)
        target_compile_definitions(KidsWinAPI PRIVATE _CRT_SECURE_NO_WARNINGS)
    else()
        target_compile_options(KidsWinAPI PRIVATE -O2 -Wall)
    endif()
endif()

# Installation
install(TARGETS KidsWinAPI
    LIBRARY DESTINATION bin
    RUNTIME DESTINATION bin
)

# Copy DLL to UI directory (optional)
# install(FILES $<TARGET_FILE:KidsWinAPI> DESTINATION "${CMAKE_SOURCE_DIR}/../KidsWinUI/bin")
