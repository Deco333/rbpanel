'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

interface FFlag {
  name: string;
  type: 'Bool' | 'Int' | 'Float' | 'String';
  value: boolean | number | string;
  default: boolean | number | string;
  category?: string;
  description?: string;
}

export default function FFlagsPage() {
  const router = useRouter();
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [flags, setFlags] = useState<FFlag[]>([]);
  const [filteredFlags, setFilteredFlags] = useState<FFlag[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('All');
  const [showModifiedOnly, setShowModifiedOnly] = useState(false);

  // Connect to WebSocket
  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8765');
    
    websocket.onopen = () => {
      setConnected(true);
      setStatusMessage('Connected to server');
      loadFlags();
    };
    
    websocket.onclose = () => {
      setConnected(false);
      setStatusMessage('Disconnected from server');
    };
    
    websocket.onerror = () => {
      setStatusMessage('Connection error');
    };
    
    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, []);

  const handleServerMessage = useCallback((data: any) => {
    switch (data.type) {
      case 'flags_list':
        setFlags(data.data || []);
        setLoading(false);
        break;
      case 'ok':
        setStatusMessage(data.message || 'Operation successful');
        loadFlags(); // Reload after modification
        break;
      case 'error':
        setStatusMessage(`Error: ${data.message}`);
        setLoading(false);
        break;
      case 'flags_export':
        downloadExport(data.data.text);
        setLoading(false);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }, []);

  const downloadExport = (text: string) => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fflags_export.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const loadFlags = () => {
    if (!ws || !connected) return;
    setLoading(true);
    setStatusMessage('Loading flags...');
    ws.send(JSON.stringify({
      command: 'flags_set',
      key: 'load',
      value: null
    }));
  };

  const setFlagValue = (name: string, value: boolean | number | string) => {
    if (!ws || !connected) return;
    setLoading(true);
    ws.send(JSON.stringify({
      command: 'flags_set',
      key: 'set_value',
      value: { name, value }
    }));
  };

  const resetFlag = (name: string) => {
    if (!ws || !connected) return;
    setLoading(true);
    ws.send(JSON.stringify({
      command: 'flags_set',
      key: 'reset_flag',
      value: name
    }));
  };

  const resetAllFlags = () => {
    if (!ws || !connected) return;
    setLoading(true);
    setStatusMessage('Resetting all flags...');
    ws.send(JSON.stringify({
      command: 'flags_set',
      key: 'reset_all',
      value: null
    }));
  };

  const exportFlags = () => {
    if (!ws || !connected) return;
    setLoading(true);
    setStatusMessage('Exporting flags...');
    ws.send(JSON.stringify({
      command: 'flags_set',
      key: 'export',
      value: null
    }));
  };

  const searchFlags = (query: string) => {
    if (!ws || !connected) return;
    setLoading(true);
    ws.send(JSON.stringify({
      command: 'flags_set',
      key: 'search',
      value: query
    }));
  };

  // Filter flags based on search and category
  useEffect(() => {
    let result = [...flags];
    
    // Filter by search query
    if (searchQuery) {
      result = result.filter(flag => 
        flag.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        flag.description?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    // Filter by category
    if (activeCategory !== 'All') {
      result = result.filter(flag => flag.category === activeCategory);
    }
    
    // Filter modified only
    if (showModifiedOnly) {
      result = result.filter(flag => flag.value !== flag.default);
    }
    
    setFilteredFlags(result);
  }, [flags, searchQuery, activeCategory, showModifiedOnly]);

  // Get unique categories
  const categories = ['All', ...Array.from(new Set(flags.map(f => f.category).filter(Boolean)))];

  const renderValueInput = (flag: FFlag) => {
    if (flag.type === 'Bool') {
      return (
        <label className="flex items-center space-x-2 cursor-pointer">
          <input
            type="checkbox"
            checked={Boolean(flag.value)}
            onChange={(e) => setFlagValue(flag.name, e.target.checked)}
            className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
          />
          <span className="text-sm">{flag.value ? 'True' : 'False'}</span>
        </label>
      );
    } else if (flag.type === 'Int' || flag.type === 'Float') {
      return (
        <input
          type="number"
          value={Number(flag.value)}
          onChange={(e) => setFlagValue(flag.name, flag.type === 'Int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
          className="w-32 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm focus:outline-none focus:border-blue-500"
        />
      );
    } else {
      return (
        <input
          type="text"
          value={String(flag.value)}
          onChange={(e) => setFlagValue(flag.name, e.target.value)}
          className="w-48 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm focus:outline-none focus:border-blue-500"
        />
      );
    }
  };

  const isModified = (flag: FFlag) => flag.value !== flag.default;

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-blue-400">FFlags Manager</h1>
            <p className="text-gray-400 mt-1">Manage Roblox Fast Flags from imtheo.lol</p>
          </div>
          <button
            onClick={() => router.back()}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            ← Back
          </button>
        </div>

        {/* Status Bar */}
        <div className="flex items-center space-x-4 bg-gray-800 rounded-lg p-3 mb-4">
          <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm">{statusMessage || (connected ? 'Connected' : 'Disconnected')}</span>
          <span className="text-xs text-gray-500 ml-auto">
            {filteredFlags.length} / {flags.length} flags
          </span>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-4">
          <input
            type="text"
            placeholder="Search flags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 min-w-[200px] px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-blue-500"
          />
          
          <select
            value={activeCategory}
            onChange={(e) => setActiveCategory(e.target.value)}
            className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-blue-500"
          >
            {categories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>

          <label className="flex items-center space-x-2 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg cursor-pointer">
            <input
              type="checkbox"
              checked={showModifiedOnly}
              onChange={(e) => setShowModifiedOnly(e.target.checked)}
              className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
            />
            <span className="text-sm">Modified Only</span>
          </label>

          <button
            onClick={loadFlags}
            disabled={!connected || loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-lg transition-colors"
          >
            Refresh
          </button>

          <button
            onClick={resetAllFlags}
            disabled={!connected || loading}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-600 rounded-lg transition-colors"
          >
            Reset All
          </button>

          <button
            onClick={exportFlags}
            disabled={!connected || loading}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg transition-colors"
          >
            Export
          </button>
        </div>
      </div>

      {/* Flags Table */}
      <div className="max-w-7xl mx-auto">
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-700">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Category</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Value</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Default</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {filteredFlags.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                      {loading ? 'Loading...' : 'No flags found'}
                    </td>
                  </tr>
                ) : (
                  filteredFlags.map((flag) => (
                    <tr 
                      key={flag.name} 
                      className={`${isModified(flag) ? 'bg-blue-900/20' : ''} hover:bg-gray-700/50 transition-colors`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center">
                          <span className="font-mono text-sm">{flag.name}</span>
                          {isModified(flag) && (
                            <span className="ml-2 px-2 py-0.5 text-xs bg-blue-600 rounded">MOD</span>
                          )}
                        </div>
                        {flag.description && (
                          <p className="text-xs text-gray-500 mt-1">{flag.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 text-xs rounded ${
                          flag.type === 'Bool' ? 'bg-purple-600' :
                          flag.type === 'Int' ? 'bg-green-600' :
                          flag.type === 'Float' ? 'bg-cyan-600' :
                          'bg-gray-600'
                        }`}>
                          {flag.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {flag.category || '-'}
                      </td>
                      <td className="px-4 py-3">
                        {renderValueInput(flag)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 font-mono">
                        {String(flag.default)}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => resetFlag(flag.name)}
                          disabled={!connected || !isModified(flag)}
                          className="px-3 py-1 text-xs bg-red-600 hover:bg-red-700 disabled:bg-gray-600 rounded transition-colors"
                        >
                          Reset
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Info Footer */}
        <div className="mt-4 text-center text-sm text-gray-500">
          <p>Data source: <a href="https://imtheo.lol/Offsets/FFlags.json" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">imtheo.lol/Offsets/FFlags.json</a></p>
          <p className="mt-1">Roblox Version: version-26c90be22e0d4758 (09/04/2026)</p>
        </div>
      </div>
    </div>
  );
}
