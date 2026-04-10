"""
Offset Manager - Fetches and manages Roblox offsets from imtheo.lol API
"""

import requests
from typing import Optional, Dict, Any


class OffsetManager:
    """Manages Roblox memory offsets"""
    
    OFFSETS_API_URL = "https://imtheo.lol/Offsets/Offsets.json"
    
    def __init__(self):
        self.offsets: Dict[str, Any] = {}
        self.roblox_version: str = ""
        self.last_updated: Optional[str] = None
    
    def fetch_offsets(self) -> bool:
        """Fetch latest offsets from imtheo.lol API"""
        try:
            response = requests.get(self.OFFSETS_API_URL, timeout=10)
            if response.status_code != 200:
                return False
            
            data = response.json()
            
            # Parse offset data
            self.roblox_version = data.get("Roblox Version", "")
            self.last_updated = data.get("Dumped At", "")
            
            # Extract relevant offsets for executor
            raw_offsets = data.get("Offsets", {})
            
            # Map to our internal structure
            self.offsets = {
                "fake_data_model_pointer": self._get_offset(raw_offsets, "FakeDataModel", "Pointer"),
                "fake_to_real_data_model": self._get_offset(raw_offsets, "FakeDataModel", "RealDataModel"),
                "children": self._get_offset(raw_offsets, "Instance", "Children"),
                "children_end": self._get_offset(raw_offsets, "Instance", "ChildrenEnd"),
                "name": self._get_offset(raw_offsets, "Instance", "Name"),
                "value": self._get_offset(raw_offsets, "Instance", "Value"),
                "class_descriptor": self._get_offset(raw_offsets, "Instance", "ClassDescriptor"),
                "local_script_bytecode": self._get_offset(raw_offsets, "LocalScript", "Bytecode"),
                "module_script_bytecode": self._get_offset(raw_offsets, "ModuleScript", "ByteCode"),
            }
            
            return True
            
        except Exception as e:
            print(f"Failed to fetch offsets: {e}")
            return False
    
    def _get_offset(self, data: Dict, category: str, field: str) -> int:
        """Safely extract an offset value"""
        try:
            return data.get(category, {}).get(field, 0)
        except:
            return 0
    
    def get_offset(self, name: str) -> int:
        """Get a specific offset by name"""
        return self.offsets.get(name, 0)
    
    def get_all_offsets(self) -> Dict[str, int]:
        """Get all offsets"""
        return self.offsets.copy()
    
    def get_roblox_version(self) -> str:
        """Get the Roblox version these offsets are for"""
        return self.roblox_version
    
    def is_loaded(self) -> bool:
        """Check if offsets are loaded"""
        return len(self.offsets) > 0
    
    def load_default_offsets(self):
        """Load default/fallback offsets"""
        # Default offsets (may need updating)
        self.offsets = {
            "fake_data_model_pointer": 0x81D3EA8,
            "fake_to_real_data_model": 0x1C0,
            "children": 0x70,
            "children_end": 0x8,
            "name": 0xB0,
            "value": 0xD0,
            "class_descriptor": 0x18,
            "local_script_bytecode": 0x1A8,
            "module_script_bytecode": 0x150,
        }
        self.roblox_version = "unknown"
        self.last_updated = "N/A"
