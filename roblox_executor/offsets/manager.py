"""
Roblox External Executor - Offsets Manager
Fetches and manages memory offsets from imtheo.lol
"""
import requests
import json
import time

class OffsetsManager:
    def __init__(self):
        self.offsets = {}
        self.last_update = 0
        self.cache_duration = 300  # 5 minutes cache
    
    def fetch_offsets(self):
        """Fetch latest offsets from imtheo.lol"""
        try:
            response = requests.get(
                "https://imtheo.lol/api/offsets",
                timeout=10,
                headers={"User-Agent": "RobloxExecutor/1.0"}
            )
            if response.status_code == 200:
                data = response.json()
                self.offsets = data.get('offsets', {})
                self.last_update = time.time()
                return True
        except Exception as e:
            print(f"Failed to fetch offsets: {e}")
        
        # Fallback to default offsets if API fails
        self.offsets = self._get_default_offsets()
        self.last_update = time.time()
        return True
    
    def _get_default_offsets(self):
        """Default offsets (may need updating)"""
        return {
            "base_address": 0x140000000,
            "workspace": 0x4E8A790,
            "players": 0x4E8B1A0,
            "localplayer": 0x1A0,
            "character": 0x1D0,
            "humanoid_root_part": 0x1E8,
            "position": 0x1C0,
            "script_context": 0x4E8C2B0,
            "lua_state": 0x8,
            "executor_function": 0x10
        }
    
    def get_offset(self, name):
        """Get specific offset value"""
        if not self.offsets or (time.time() - self.last_update > self.cache_duration):
            self.fetch_offsets()
        return self.offsets.get(name, 0)
    
    def get_all_offsets(self):
        """Get all offsets"""
        if not self.offsets or (time.time() - self.last_update > self.cache_duration):
            self.fetch_offsets()
        return self.offsets.copy()
