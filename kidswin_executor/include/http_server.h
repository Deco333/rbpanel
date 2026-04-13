// KidsWin - HTTP Server Header
// Embedded C++ HTTP server using cpp-httplib

#pragma once
#include <string>
#include <vector>
#include <mutex>
#include <atomic>
#include <functional>

// Forward declare httplib types
namespace httplib {
    class Server;
    class Request;
    class Response;
}

class HttpServer {
private:
    std::unique_ptr<httplib::Server> m_server;
    std::atomic<bool> m_running{false};
    std::string m_host = "127.0.0.1";
    int m_port = 9753;
    
    std::mutex m_scriptQueueMutex;
    std::vector<std::string> m_scriptQueue;
    
    // Callbacks
    std::function<uintptr_t(std::string&)> m_findUnloadedModuleCallback;
    std::function<void()> m_restoreAllModulesCallback;
    std::function<bool(uintptr_t, const std::vector<uint8_t>&)> m_setBytecodeCallback;

public:
    HttpServer();
    ~HttpServer();
    
    bool Start(int port = 9753);
    void Stop();
    bool IsRunning() const { return m_running; }
    
    void QueueScript(const std::string& script);
    std::string DequeueScript();
    
    void SetFindUnloadedModuleCallback(std::function<uintptr_t(std::string&)> cb) {
        m_findUnloadedModuleCallback = cb;
    }
    
    void SetRestoreAllModulesCallback(std::function<void()> cb) {
        m_restoreAllModulesCallback = cb;
    }
    
    void SetSetBytecodeCallback(std::function<bool(uintptr_t, const std::vector<uint8_t>&)> cb) {
        m_setBytecodeCallback = cb;
    }

private:
    void SetupRoutes();
    
    // Endpoint handlers
    void HandlePoll(httplib::Request& req, httplib::Response& res);
    void HandleLs(httplib::Request& req, httplib::Response& res);
    void HandleReq(httplib::Request& req, httplib::Response& res);
    void HandleCleanup(httplib::Request& req, httplib::Response& res);
};

// Inline implementation (header-only for simplicity)
inline HttpServer::HttpServer() {}

inline HttpServer::~HttpServer() {
    Stop();
}

inline bool HttpServer::Start(int port) {
    if (m_running) return true;
    
    m_port = port;
    
    // Create server instance (cpp-httplib is header-only)
    // In production, include <httplib.h> from third_party/
    m_server = std::make_unique<httplib::Server>();
    
    SetupRoutes();
    
    // Start server in background thread
    m_running = true;
    
    // Note: In production, use m_server->listen() in a detached thread
    // For now, this is a placeholder
    
    return true;
}

inline void HttpServer::Stop() {
    if (!m_running) return;
    
    m_running = false;
    if (m_server) {
        m_server->stop();
        m_server.reset();
    }
}

inline void HttpServer::QueueScript(const std::string& script) {
    std::lock_guard<std::mutex> lock(m_scriptQueueMutex);
    m_scriptQueue.push_back(script);
}

inline std::string HttpServer::DequeueScript() {
    std::lock_guard<std::mutex> lock(m_scriptQueueMutex);
    if (m_scriptQueue.empty()) return "";
    std::string script = m_scriptQueue.front();
    m_scriptQueue.erase(m_scriptQueue.begin());
    return script;
}

inline void HttpServer::SetupRoutes() {
    if (!m_server) return;
    
    // GET /poll - Returns next queued script or 204 No Content
    m_server->Get("/poll", [this](const httplib::Request& req, httplib::Response& res) {
        HandlePoll(const_cast<httplib::Request&>(req), res);
    });
    
    // POST /ls - Compile and write Lua to ModuleScript
    m_server->Post("/ls", [this](const httplib::Request& req, httplib::Response& res) {
        HandleLs(const_cast<httplib::Request&>(req), res);
    });
    
    // POST /req - HTTP proxy
    m_server->Post("/req", [this](const httplib::Request& req, httplib::Response& res) {
        HandleReq(const_cast<httplib::Request&>(req), res);
    });
    
    // POST /cleanup - Restore all modules
    m_server->Post("/cleanup", [this](const httplib::Request& req, httplib::Response& res) {
        HandleCleanup(const_cast<httplib::Request&>(req), res);
    });
}

inline void HttpServer::HandlePoll(httplib::Request& req, httplib::Response& res) {
    std::string script = DequeueScript();
    
    if (script.empty()) {
        res.status = 204; // No Content
        return;
    }
    
    res.status = 200;
    res.set_content(script, "text/plain");
}

inline void HttpServer::HandleLs(httplib::Request& req, httplib::Response& res) {
    // req.body contains raw Lua source
    
    // Wrap in module format
    std::string wrappedSource = 
        "local module = {}\n"
        "module[\"KidsWin\"] = function()\n" + 
        req.body + 
        "\nend\n"
        "return module";
    
    // In production: Compile -> BLAKE3 sign -> ZSTD compress -> RSB1 encode
    std::vector<uint8_t> bytecode(wrappedSource.begin(), wrappedSource.end());
    
    // Find unloaded module
    std::string moduleName;
    uintptr_t moduleAddr = 0;
    if (m_findUnloadedModuleCallback) {
        moduleAddr = m_findUnloadedModuleCallback(moduleName);
    }
    
    if (!moduleAddr) {
        res.status = 500;
        res.set_content("{\"error\": \"No unloaded module found\"}", "application/json");
        return;
    }
    
    // Write bytecode
    if (m_setBytecodeCallback) {
        if (!m_setBytecodeCallback(moduleAddr, bytecode)) {
            res.status = 500;
            res.set_content("{\"error\": \"Failed to write bytecode\"}", "application/json");
            return;
        }
    }
    
    // Build path array from module name
    std::vector<std::string> pathParts;
    size_t start = 0;
    size_t end = moduleName.find('.');
    while (end != std::string::npos) {
        pathParts.push_back(moduleName.substr(start, end - start));
        start = end + 1;
        end = moduleName.find('.', start);
    }
    pathParts.push_back(moduleName.substr(start));
    
    // Return JSON with path
    std::string jsonPath = "[";
    for (size_t i = 0; i < pathParts.size(); ++i) {
        if (i > 0) jsonPath += ", ";
        jsonPath += "\"" + pathParts[i] + "\"";
    }
    jsonPath += "]";
    
    res.status = 200;
    res.set_content("{\"path\": " + jsonPath + "}", "application/json");
}

inline void HttpServer::HandleReq(httplib::Request& req, httplib::Response& res) {
    // Parse JSON body for {url, method, headers, body}
    // In production: Use WinHttpClient to make real HTTP request
    // Return JSON {StatusCode, Body, Headers}
    
    // Placeholder response
    res.status = 200;
    res.set_content(R"({"StatusCode": 200, "Body": "", "Headers": {}})", "application/json");
}

inline void HttpServer::HandleCleanup(httplib::Request& req, httplib::Response& res) {
    if (m_restoreAllModulesCallback) {
        m_restoreAllModulesCallback();
    }
    
    res.status = 200;
    res.set_content("{\"success\": true}", "application/json");
}
