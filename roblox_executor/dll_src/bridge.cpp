// Roblox External Executor - Bridge DLL
// This DLL is injected into Roblox process and runs an HTTP server
// to execute Lua scripts remotely

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdio.h>
#include <string>
#include <thread>
#include <atomic>

#pragma comment(lib, "ws2_32.lib")

// Global state
static std::atomic<bool> g_running(false);
static SOCKET g_server_socket = INVALID_SOCKET;
static const char* g_last_script = "";
static std::string g_output_buffer = "";
static int g_client_count = 0;

// Lua state pointer (will be found via offsets)
static void* g_lua_state = nullptr;

// Simple HTTP response helpers
std::string http_response(int status_code, const std::string& content_type, const std::string& body) {
    std::string status_text;
    switch (status_code) {
        case 200: status_text = "OK"; break;
        case 400: status_text = "Bad Request"; break;
        case 500: status_text = "Internal Server Error"; break;
        default: status_text = "Unknown"; break;
    }
    
    return 
        "HTTP/1.1 " + std::to_string(status_code) + " " + status_text + "\r\n" +
        "Content-Type: " + content_type + "\r\n" +
        "Content-Length: " + std::to_string(body.length()) + "\r\n" +
        "Connection: close\r\n" +
        "\r\n" +
        body;
}

std::string json_response(bool success, const std::string& message) {
    return "{\"success\": " + std::string(success ? "true" : "false") + 
           ", \"message\": \"" + message + "\"}";
}

std::string json_execute_response(bool success, const std::string& message, const std::string& output) {
    return "{\"success\": " + std::string(success ? "true" : "false") + 
           ", \"message\": \"" + message + "\", " +
           "\"output\": [\"" + output + "\"]}";
}

// Parse HTTP request to get method and body
bool parse_request(const char* buffer, size_t len, std::string& method, std::string& path, std::string& body) {
    if (len < 10) return false;
    
    // Extract method
    const char* space1 = strchr(buffer, ' ');
    if (!space1) return false;
    method = std::string(buffer, space1 - buffer);
    
    // Extract path
    const char* space2 = strchr(space1 + 1, ' ');
    if (!space2) return false;
    path = std::string(space1 + 1, space2 - space1 - 1);
    
    // Find body (after \r\n\r\n)
    const char* body_start = strstr(buffer, "\r\n\r\n");
    if (body_start) {
        body = std::string(body_start + 4);
    }
    
    return true;
}

// Execute Lua script (placeholder - real implementation needs Lua VM access)
void execute_lua_script(const std::string& script) {
    g_last_script = script.c_str();
    
    // In real implementation, this would:
    // 1. Get Lua state from Roblox
    // 2. Push script to Lua stack
    // 3. Call lua_pcall or equivalent
    // 4. Capture output
    
    // For now, simulate execution
    if (script.find("print(") != std::string::npos) {
        // Extract string from print("...")
        size_t start = script.find("\"");
        size_t end = script.rfind("\"");
        if (start != std::string::npos && end != std::string::npos && start < end) {
            g_output_buffer = script.substr(start + 1, end - start - 1);
        }
    } else {
        g_output_buffer = "Script executed (no output)";
    }
}

// Handle client connection
void handle_client(SOCKET client_socket) {
    g_client_count++;
    char buffer[4096] = {0};
    
    int bytes_received = recv(client_socket, buffer, sizeof(buffer) - 1, 0);
    if (bytes_received > 0) {
        std::string method, path, body;
        if (parse_request(buffer, bytes_received, method, path, body)) {
            std::string response;
            
            if (path == "/api/status" && method == "GET") {
                response = http_response(200, "application/json",
                    "{\"status\": \"online\", \"clients\": " + std::to_string(g_client_count) + 
                    ", \"pid\": " + std::to_string(GetCurrentProcessId()) + "}");
            }
            else if (path == "/api/execute" && method == "POST") {
                // Extract script from JSON body (simple parsing)
                std::string script = body;
                size_t script_pos = body.find("\"script\":\"");
                if (script_pos != std::string::npos) {
                    size_t start = script_pos + 10;
                    size_t end = body.find("\"", start);
                    if (end != std::string::npos) {
                        script = body.substr(start, end - start);
                    }
                }
                
                execute_lua_script(script);
                response = http_response(200, "application/json",
                    json_execute_response(true, "Script executed", g_output_buffer));
            }
            else if (path == "/api/clear" && method == "POST") {
                g_output_buffer = "";
                response = http_response(200, "application/json",
                    json_response(true, "Output cleared"));
            }
            else {
                response = http_response(404, "text/plain", "Not Found");
            }
            
            send(client_socket, response.c_str(), response.length(), 0);
        }
    }
    
    closesocket(client_socket);
    g_client_count--;
}

// Server thread function
void server_thread(void* param) {
    int port = *(int*)param;
    delete (int*)param;
    
    WSADATA wsa_data;
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
        OutputDebugStringA("[Bridge] WSAStartup failed\n");
        return;
    }
    
    g_server_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_server_socket == INVALID_SOCKET) {
        OutputDebugStringA("[Bridge] Socket creation failed\n");
        WSACleanup();
        return;
    }
    
    sockaddr_in server_addr = {};
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    server_addr.sin_port = htons(port);
    
    if (bind(g_server_socket, (sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
        OutputDebugStringA("[Bridge] Bind failed\n");
        closesocket(g_server_socket);
        WSACleanup();
        return;
    }
    
    if (listen(g_server_socket, SOMAXCONN) == SOCKET_ERROR) {
        OutputDebugStringA("[Bridge] Listen failed\n");
        closesocket(g_server_socket);
        WSACleanup();
        return;
    }
    
    char msg[128];
    sprintf_s(msg, "[Bridge] Server listening on port %d\n", port);
    OutputDebugStringA(msg);
    
    g_running = true;
    
    while (g_running) {
        sockaddr_in client_addr = {};
        int client_addr_size = sizeof(client_addr);
        
        SOCKET client_socket = accept(g_server_socket, (sockaddr*)&client_addr, &client_addr_size);
        if (client_socket != INVALID_SOCKET) {
            std::thread client_handler(handle_client, client_socket);
            client_handler.detach();
        }
    }
    
    closesocket(g_server_socket);
    WSACleanup();
    OutputDebugStringA("[Bridge] Server stopped\n");
}

// Start the bridge server
extern "C" __declspec(dllexport) void StartBridge() {
    int* port = new int(6767);
    std::thread server(server_thread, port);
    server.detach();
}

// Stop the bridge server
extern "C" __declspec(dllexport) void StopBridge() {
    g_running = false;
    if (g_server_socket != INVALID_SOCKET) {
        shutdown(g_server_socket, SD_BOTH);
    }
}

// Get last output
extern "C" __declspec(dllexport) const char* GetLastOutput() {
    return g_output_buffer.c_str();
}

// DLL Entry point
BOOL APIENTRY DllMain(HMODULE h_module, DWORD ul_reason_for_call, LPVOID lp_reserved) {
    switch (ul_reason_for_call) {
        case DLL_PROCESS_ATTACH: {
            DisableThreadLibraryCalls(h_module);
            OutputDebugStringA("[Bridge] DLL attached to process\n");
            // Auto-start server on attach
            StartBridge();
            break;
        }
        case DLL_PROCESS_DETACH:
            OutputDebugStringA("[Bridge] DLL detaching from process\n");
            StopBridge();
            break;
        case DLL_THREAD_ATTACH:
        case DLL_THREAD_DETACH:
            break;
    }
    return TRUE;
}
