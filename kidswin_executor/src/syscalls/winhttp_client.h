// KidsWin - WinHTTP Client
// HTTP client for proxy requests

#pragma once
#include <windows.h>
#include <winhttp.h>
#include <string>
#include <vector>
#include <map>
#pragma comment(lib, "winhttp.lib")

struct HttpResponse {
    int statusCode = 0;
    std::string body;
    std::map<std::string, std::string> headers;
    bool success = false;
};

class WinHttpClient {
public:
    static HttpResponse Request(const std::string& url, 
                                 const std::string& method = "GET",
                                 const std::map<std::string, std::string>& headers = {},
                                 const std::string& body = "",
                                 int timeoutMs = 5000) {
        
        HttpResponse response;
        
        // Parse URL
        URL_COMPONENTS urlComp = { sizeof(URL_COMPONENTS) };
        urlComp.dwSchemeLength = -1;
        urlComp.dwHostNameLength = -1;
        urlComp.dwUrlPathLength = -1;
        
        if (!WinHttpCrackUrl(url.c_str(), 0, 0, &urlComp)) {
            return response;
        }
        
        std::wstring hostName(urlComp.lpszHostName, urlComp.dwHostNameLength);
        std::string path(urlComp.lpszUrlPath, urlComp.dwUrlPathLength);
        INTERNET_PORT port = urlComp.nPort;
        if (port == 0) port = (wcsncmp(urlComp.lpszScheme, L"https", 5) == 0) ? 443 : 80;
        BOOL secure = (wcsncmp(urlComp.lpszScheme, L"https", 5) == 0);
        
        // Create session
        HINTERNET hSession = WinHttpOpen(L"KidsWin/1.0", 
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS,
            0);
        
        if (!hSession) return response;
        
        // Connect to host
        HINTERNET hConnect = WinHttpConnect(hSession, hostName.c_str(), port, 0);
        if (!hConnect) {
            WinHttpCloseHandle(hSession);
            return response;
        }
        
        // Create request
        std::wstring wPath(path.begin(), path.end());
        std::wstring wMethod(method.begin(), method.end());
        HINTERNET hRequest = WinHttpOpenRequest(hConnect, wMethod.c_str(), wPath.c_str(),
            nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
            secure ? WINHTTP_FLAG_SECURE : 0);
        
        if (!hRequest) {
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return response;
        }
        
        // Set timeouts
        int sendTimeout = timeoutMs;
        int receiveTimeout = timeoutMs;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SEND_TIMEOUT, &sendTimeout, sizeof(sendTimeout));
        WinHttpSetOption(hRequest, WINHTTP_OPTION_RECEIVE_TIMEOUT, &receiveTimeout, sizeof(receiveTimeout));
        
        // Add headers
        std::wstring wHeaders;
        for (const auto& [key, value] : headers) {
            std::wstring wKey(key.begin(), key.end());
            std::wstring wValue(value.begin(), value.end());
            wHeaders += wKey + L": " + wValue + L"\r\n";
        }
        
        // Send request
        std::wstring wBody(body.begin(), body.end());
        BOOL result = WinHttpSendRequest(hRequest,
            wHeaders.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : wHeaders.c_str(), -1,
            wBody.empty() ? WINHTTP_NO_REQUEST_DATA : const_cast<void*>(reinterpret_cast<const void*>(wBody.c_str())),
            wBody.empty() ? 0 : wBody.length(),
            wBody.empty() ? 0 : wBody.length(),
            0);
        
        if (!result) {
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return response;
        }
        
        // Receive response
        result = WinHttpReceiveResponse(hRequest, nullptr);
        if (!result) {
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return response;
        }
        
        // Get status code
        DWORD statusCode = 0;
        DWORD statusCodeSize = sizeof(statusCode);
        WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
            WINHTTP_HEADER_NAME_BY_INDEX, &statusCode, &statusCodeSize, WINHTTP_NO_HEADER_INDEX);
        response.statusCode = statusCode;
        
        // Query headers
        DWORD headerSize = 0;
        WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_RAW_HEADERS_CRLF, 
            WINHTTP_HEADER_NAME_BY_INDEX, nullptr, &headerSize, WINHTTP_NO_HEADER_INDEX);
        
        if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
            std::vector<wchar_t> headerBuffer(headerSize / sizeof(wchar_t) + 1);
            if (WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_RAW_HEADERS_CRLF,
                WINHTTP_HEADER_NAME_BY_INDEX, headerBuffer.data(), &headerSize, WINHTTP_NO_HEADER_INDEX)) {
                
                std::wstring wHeaderStr(headerBuffer.data());
                size_t pos = 0;
                while ((pos = wHeaderStr.find(L"\r\n", pos)) != std::wstring::npos) {
                    size_t colonPos = wHeaderStr.find(L':', pos - (pos > 0 ? pos : 0));
                    if (colonPos != std::wstring::npos && colonPos < pos) {
                        std::string key(wHeaderStr.substr(pos - (pos > 0 ? pos : 0), colonPos - (pos - (pos > 0 ? pos : 0))).begin(),
                                       wHeaderStr.substr(pos - (pos > 0 ? pos : 0), colonPos - (pos - (pos > 0 ? pos : 0))).end());
                        std::string value(wHeaderStr.substr(colonPos + 1, pos - colonPos - 2).begin(),
                                         wHeaderStr.substr(colonPos + 1, pos - colonPos - 2).end());
                        // Trim whitespace
                        size_t start = value.find_first_not_of(" \t");
                        size_t end = value.find_last_not_of(" \t\r\n");
                        if (start != std::string::npos) {
                            response.headers[key] = value.substr(start, end - start + 1);
                        }
                    }
                    pos += 2;
                }
            }
        }
        
        // Read body
        std::string responseBody;
        DWORD bytesAvailable = 0;
        DWORD bytesRead = 0;
        
        do {
            bytesAvailable = 0;
            WinHttpQueryDataAvailable(hRequest, &bytesAvailable);
            
            if (bytesAvailable > 0) {
                std::vector<char> buffer(bytesAvailable + 1);
                if (WinHttpReadData(hRequest, buffer.data(), bytesAvailable, &bytesRead)) {
                    buffer[bytesRead] = '\0';
                    responseBody.append(buffer.data(), bytesRead);
                }
            }
        } while (bytesAvailable > 0);
        
        response.body = responseBody;
        response.success = (response.statusCode >= 200 && response.statusCode < 300);
        
        // Cleanup
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        
        return response;
    }
    
    static HttpResponse Get(const std::string& url, 
                            const std::map<std::string, std::string>& headers = {},
                            int timeoutMs = 5000) {
        return Request(url, "GET", headers, "", timeoutMs);
    }
    
    static HttpResponse Post(const std::string& url,
                              const std::string& body = "",
                              const std::map<std::string, std::string>& headers = {},
                              int timeoutMs = 5000) {
        return Request(url, "POST", headers, body, timeoutMs);
    }
};
