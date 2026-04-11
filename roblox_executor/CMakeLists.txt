// Roblox External Executor - CMakeLists.txt
// Build instructions for bridge.dll

cmake_minimum_required(VERSION 3.15)
project(RobloxBridge VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Windows specific settings
if(WIN32)
    add_definitions(-D_WIN32_WINNT=0x0601)
    add_definitions(-DWINDOWS)
endif()

# Create shared library (DLL on Windows)
add_library(bridge SHARED
    dll_src/bridge.cpp
)

# Include directories
target_include_directories(bridge PRIVATE
    ${CMAKE_SOURCE_DIR}/dll_src
)

# Link Windows libraries
if(WIN32)
    target_link_libraries(bridge PRIVATE
        ws2_32
    )
endif()

# Set output name
set_target_properties(bridge PROPERTIES
    OUTPUT_NAME "bridge"
    PREFIX ""
    SUFFIX ".dll"
)

# Optimization flags
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    if(MSVC)
        target_compile_options(bridge PRIVATE /O2)
    else()
        target_compile_options(bridge PRIVATE -O2)
    endif()
endif()

# Installation
install(TARGETS bridge
    LIBRARY DESTINATION bin
    RUNTIME DESTINATION bin
)
