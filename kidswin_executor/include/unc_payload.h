// KidsWin - UNC Payload (Lua Sandbox)
// Embedded Lua code for UNC API implementation

#pragma once

const char* UNC_PAYLOAD_PART1 = R"LUA(
-- Environment Setup
local HttpService = game:FindService("HttpService")
local CoreGui = game:GetService("CoreGui")
local Players = game:GetService("Players")
local SERVER = "http://127.0.0.1:9753"
local EXEC_NAME = "KidsWin"

-- Signal to C++ that init succeeded
local container = Instance.new("Folder")
container.Name = EXEC_NAME
container.Parent = CoreGui

-- Anchor script to prevent GC
script.Parent = container
script.Name = "_init"

-- SendRequest using RequestInternal (CoreScript-only API, no logging)
local function SendRequest(options, timeout)
    timeout = timeout or 5
    local success, result = pcall(function()
        return HttpService:RequestInternal(options)
    end)
    if success and result then
        local response = result
        if response.StatusCode == 200 then
            return {
                Success = true,
                Body = response.Body,
                StatusCode = response.StatusCode
            }
        end
    end
    return nil
end
)LUA";

const char* UNC_PAYLOAD_PART2 = R"LUA(
-- UNC Sandbox Implementation
KidsWin = {}

-- loadstring: POST to /ls, resolve path, require() the module
function KidsWin.loadstring(content)
    local response = HttpService:RequestInternal({
        Url = SERVER .. "/ls",
        Method = "POST",
        Headers = {["Content-Type"] = "text/plain"},
        Body = content
    })
    
    if response.StatusCode ~= 200 then
        warn("[KidsWin] /ls failed:", response.StatusCode)
        return nil
    end
    
    local data = game:GetService("HttpService"):JSONDecode(response.Body)
    local path = data.path
    
    -- Build instance path
    local obj = game
    for i, part in ipairs(path) do
        if part == "Game" then continue end
        obj = obj:FindFirstChild(part) or obj
    end
    
    if obj and obj:IsA("ModuleScript") then
        local module = require(obj)
        if module and module["KidsWin"] then
            local fn = module["KidsWin"]()
            return fn
        end
    end
    
    return nil
end

-- request: POST to /req proxy
function KidsWin.request(options)
    local response = HttpService:RequestInternal({
        Url = SERVER .. "/req",
        Method = "POST",
        Headers = {["Content-Type"] = "application/json"},
        Body = game:GetService("HttpService"):JSONEncode(options)
    })
    
    if response.StatusCode ~= 200 then
        return {Success = false, StatusCode = response.StatusCode}
    end
    
    local data = game:GetService("HttpService"):JSONDecode(response.Body)
    return {
        Success = true,
        StatusCode = data.StatusCode,
        Body = data.Body,
        Headers = data.Headers
    }
end

-- httpget wrapper
function KidsWin.httpget(url)
    return KidsWin.request({Url = url, Method = "GET"})
end

-- Identity functions
function KidsWin.getgenv()
    return getgenv and getgenv() or _G
end

function KidsWin.getrenv()
    return getrenv and getrenv() or getfenv()
end

function KidsWin.identifyexecutor()
    return "KidsWin"
end

function KidsWin.getidentity()
    return 8
end

-- gethui: Returns a Folder parented to PlayerGui (NOT CoreGui!)
function KidsWin.gethui()
    local player = Players.LocalPlayer
    if not player then return CoreGui end
    
    local playerGui = player:FindFirstChild("PlayerGui")
    if not playerGui then
        playerGui = Instance.new("ScreenGui")
        playerGui.Name = "KidsWinHUI"
        playerGui.ResetOnSpawn = false
        playerGui.Parent = player
    end
    
    local hui = playerGui:FindFirstChild("KidsWinHUI")
    if not hui then
        hui = Instance.new("Folder")
        hui.Name = "KidsWinHUI"
        hui.Parent = playerGui
    end
    
    return hui
end

-- Game proxy with security wrappers
local gameProxy = setmetatable({}, {
    __index = function(_, key)
        local success, result = pcall(function()
            return game[key]
        end)
        return success and result or nil
    end,
    __newindex = function(_, key, value)
        pcall(function()
            game[key] = value
        end)
    end
})

-- Global environment setup
local genv = getfenv()
setmetatable(genv, {
    __index = function(t, k)
        local v = rawget(t, k)
        if v ~= nil then return v end
        return getfenv()[k]
    end
})

shared._rblx_genv = genv
)LUA";

const char* UNC_PAYLOAD_PART3 = R"LUA(
-- Polling Loop
while task.wait(0.1) do
    local result = SendRequest({Url = SERVER .. "/poll", Method = "GET"}, 2)
    if result and result.Success and #result.Body > 0 then
        local fn = KidsWin.loadstring(result.Body)
        if fn then
            setfenv(fn, genv)
            task.spawn(fn)
        end
    end
end
)LUA";

inline const char* GetInitScript() {
    static std::string initScript;
    if (initScript.empty()) {
        initScript = std::string(UNC_PAYLOAD_PART1) + 
                     std::string(UNC_PAYLOAD_PART2) + 
                     std::string(UNC_PAYLOAD_PART3);
    }
    return initScript.c_str();
}
