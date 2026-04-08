'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { HoloSection } from '../holo/HoloSection';
import { ToggleSwitch } from '../holo/ToggleSwitch';
import { HoloSlider } from '../holo/HoloSlider';
import { HoloSelect } from '../holo/HoloSelect';
import { HoloPanel } from '../holo/HoloPanel';
import { RadarCanvas } from '../holo/RadarCanvas';
import { CombatLog } from '../holo/CombatLog';

interface LogEntry {
  text: string;
  color: string;
  timestamp: string;
}

interface RadarBlip {
  name: string;
  dx: number;
  dy: number;
  dz: number;
  dist: number;
  hp: number | null;
  is_team: boolean;
  is_npc: boolean;
}

interface RadarData {
  targets: RadarBlip[];
  camera_yaw: number;
  range: number;
}

interface RobloxWS {
  robloxConnected: boolean;
  wsConnected: boolean;
  state: any;
  sendCommand: (cmd: string, data?: Record<string, any>) => boolean;
  onMessage: (type: string, handler: (data: any) => void) => () => void;
}

interface CombatTabProps {
  connected: boolean;
  ws: RobloxWS;
}

export function CombatTab({ connected, ws }: CombatTabProps) {
  // ── Aimbot ──
  const [aimbotEnabled, setAimbotEnabled] = useState(false);
  const [aimbotFov, setAimbotFov] = useState(120);
  const [aimbotSens, setAimbotSens] = useState(5);
  const [aimbotBone, setAimbotBone] = useState('Head');
  const [aimbotTeam, setAimbotTeam] = useState(false);
  const [aimbotNPC, setAimbotNPC] = useState(true);
  const [aimbotAlive, setAimbotAlive] = useState(true);

  // ── Head Lock ──
  const [headLockEnabled, setHeadLockEnabled] = useState(false);
  const [headLockSmooth, setHeadLockSmooth] = useState(8);
  const [headLockFov, setHeadLockFov] = useState(200);
  const [headLockTeam, setHeadLockTeam] = useState(false);
  const [headLockNPC, setHeadLockNPC] = useState(true);

  // ── Silent Aim ──
  const [silentAimEnabled, setSilentAimEnabled] = useState(false);
  const [silentAimTeam, setSilentAimTeam] = useState(false);

  // ── Triggerbot ──
  const [triggerEnabled, setTriggerEnabled] = useState(false);
  const [triggerDelay, setTriggerDelay] = useState(50);

  // ── Kill Aura ──
  const [killAuraEnabled, setKillAuraEnabled] = useState(false);
  const [killAuraRange, setKillAuraRange] = useState(50);

  // ── Radar ──
  const [radarEnabled, setRadarEnabled] = useState(false);
  const [radarRange, setRadarRange] = useState(500);
  const [radarNPC, setRadarNPC] = useState(true);
  const [radarNames, setRadarNames] = useState(true);
  const [radarHP, setRadarHP] = useState(true);
  const [radarData, setRadarData] = useState<RadarData | null>(null);

  // ── Combat Log ──
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const syncedRef = useRef(false);

  const getTimestamp = () => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
  };

  const addLog = useCallback((text: string, color: string) => {
    setLogEntries(prev => [...prev.slice(-99), { text, color, timestamp: getTimestamp() }]);
  }, []);

  // ═══════════════════════════════════════════════════════════════
  //  SYNC STATE FROM SERVER (fixes "need reload" bug)
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    const c = ws.state?.combat;
    if (!c) return;

    setAimbotEnabled(c.aimbot_enabled ?? false);
    setAimbotFov(c.aimbot_fov ?? 120);
    setAimbotSens(c.aimbot_sens ?? 5);
    setAimbotBone(c.aimbot_bone ?? 'Head');
    setAimbotTeam(c.aimbot_team_check ?? false);
    setAimbotNPC(c.aimbot_npc_check ?? true);
    setAimbotAlive(c.aimbot_alive_check ?? true);

    setHeadLockEnabled(c.headlock_enabled ?? false);
    setHeadLockSmooth(c.headlock_smooth ?? 8);
    setHeadLockFov(c.headlock_fov ?? 200);
    setHeadLockTeam(c.headlock_team_check ?? false);
    setHeadLockNPC(c.headlock_npc_check ?? true);

    setSilentAimEnabled(c.silent_aim_enabled ?? false);
    setSilentAimTeam(c.silent_aim_team_check ?? false);

    setTriggerEnabled(c.triggerbot_enabled ?? false);
    setTriggerDelay(c.triggerbot_delay ?? 50);

    setKillAuraEnabled(c.kill_aura_enabled ?? false);
    setKillAuraRange(c.kill_aura_range ?? 50);

    setRadarEnabled(c.radar_enabled ?? false);
    setRadarRange(c.radar_range ?? 500);
    setRadarNPC(c.radar_npc ?? true);
    setRadarNames(c.radar_names ?? true);
    setRadarHP(c.radar_hp ?? true);

    if (!syncedRef.current && ws.state?.connected) {
      syncedRef.current = true;
      addLog('State synced from server', '#00d4ff');
    }
  }, [ws.state, addLog]);

  // ═══════════════════════════════════════════════════════════════
  //  RECEIVE RADAR DATA FROM SERVER (fixes "radar not working" bug)
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    const unsub = ws.onMessage('radar_data', (data: RadarData) => {
      setRadarData(data);
    });
    return unsub;
  }, [ws]);

  // ═══════════════════════════════════════════════════════════════
  //  RECEIVE COMBAT LOG FROM SERVER
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    const unsub = ws.onMessage('combat_log', (entries: any[]) => {
      if (!Array.isArray(entries)) return;
      const colorMap: Record<string, string> = {
        info: '#00d4ff',
        good: '#00ff88',
        warn: '#ffcc00',
        error: '#ff3366',
      };
      setLogEntries(prev => {
        const newEntries = entries.map((e: any) => ({
          text: e.text || '',
          color: colorMap[e.tag] || '#00d4ff',
          timestamp: e.time || getTimestamp(),
        }));
        const combined = [...prev, ...newEntries].slice(-99);
        return combined;
      });
    });
    return unsub;
  }, [ws]);

  // ═══════════════════════════════════════════════════════════════
  //  SEND COMBAT COMMANDS TO SERVER
  // ═══════════════════════════════════════════════════════════════
  const sendCombat = useCallback((key: string, value: any) => {
    const sent = ws.sendCommand('combat_set', { key, value });
    if (!sent) {
      addLog(`Server offline: ${key}`, '#ff3366');
      return;
    }
    addLog(`${key}: ${value}`, '#00d4ff');
  }, [ws, addLog]);

  const boneOptions = [
    { label: '🎯 Head', value: 'Head' },
    { label: '🧍 HumanoidRootPart', value: 'HumanoidRootPart' },
    { label: '🫁 Torso', value: 'Torso' },
    { label: '💪 Arms', value: 'Arms' },
    { label: '🦵 Legs', value: 'Legs' },
  ];

  // Connection warning
  if (!connected) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        height: 'calc(100vh - 160px)', gap: 16,
      }}>
        <div style={{
          fontSize: 48, opacity: 0.3,
          filter: 'drop-shadow(0 0 10px rgba(0, 212, 255, 0.3))',
        }}>⚔</div>
        <div style={{
          fontFamily: 'var(--holo-font-mono)', fontSize: 13,
          color: 'var(--holo-text-muted)', textAlign: 'center',
        }}>
          Подключитесь к Roblox для управления Combat функциями
        </div>
        <div style={{
          fontFamily: 'var(--holo-font-mono)', fontSize: 11,
          color: 'var(--holo-yellow)', opacity: 0.7, textAlign: 'center',
        }}>
          WS: {ws.wsConnected ? 'ONLINE' : 'OFFLINE'} | Roblox: DISCONNECTED
        </div>
      </div>
    );
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 320px',
      gap: 12,
      height: '100%',
    }}>
      {/* Left Column */}
      <div className="holo-scroll" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)', paddingRight: 4 }}>
        {/* AIMBOT */}
        <HoloSection title="🎯 AIMBOT">
          <ToggleSwitch
            label="Enabled"
            checked={aimbotEnabled}
            onChange={(v) => { setAimbotEnabled(v); sendCombat('aimbot_enabled', v); }}
            color="cyan"
          />
          <HoloSlider
            label="FOV"
            value={aimbotFov}
            min={30}
            max={800}
            step={10}
            onChange={(v) => { setAimbotFov(v); sendCombat('aimbot_fov', v); }}
            unit="°"
          />
          <HoloSlider
            label="Sensitivity"
            value={aimbotSens}
            min={0.5}
            max={20}
            step={0.5}
            onChange={(v) => { setAimbotSens(v); sendCombat('aimbot_sens', v); }}
            color="green"
          />
          <HoloSelect
            label="Target Bone"
            value={aimbotBone}
            onChange={(v) => { setAimbotBone(v); sendCombat('aimbot_bone', v); }}
            options={boneOptions}
          />
          <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
            <ToggleSwitch
              label="Team Check"
              checked={aimbotTeam}
              onChange={(v) => { setAimbotTeam(v); sendCombat('aimbot_team_check', v); }}
              color="red"
            />
            <ToggleSwitch
              label="NPC Check"
              checked={aimbotNPC}
              onChange={(v) => { setAimbotNPC(v); sendCombat('aimbot_npc_check', v); }}
              color="purple"
            />
          </div>
          <ToggleSwitch
            label="Alive Check"
            checked={aimbotAlive}
            onChange={(v) => { setAimbotAlive(v); sendCombat('aimbot_alive_check', v); }}
            color="green"
          />
        </HoloSection>

        {/* HEAD LOCK */}
        <HoloSection title="🎯 HEAD LOCK">
          <ToggleSwitch
            label="Enabled"
            checked={headLockEnabled}
            onChange={(v) => { setHeadLockEnabled(v); sendCombat('headlock_enabled', v); }}
            color="purple"
          />
          <HoloSlider
            label="Smoothing"
            value={headLockSmooth}
            min={1}
            max={30}
            step={1}
            onChange={(v) => { setHeadLockSmooth(v); sendCombat('headlock_smooth', v); }}
            unit="x"
            color="purple"
          />
          <HoloSlider
            label="FOV"
            value={headLockFov}
            min={50}
            max={1200}
            step={10}
            onChange={(v) => { setHeadLockFov(v); sendCombat('headlock_fov', v); }}
            unit="°"
          />
          <div style={{ display: 'flex', gap: 16 }}>
            <ToggleSwitch
              label="Team Check"
              checked={headLockTeam}
              onChange={(v) => { setHeadLockTeam(v); sendCombat('headlock_team_check', v); }}
              color="red"
            />
            <ToggleSwitch
              label="NPC Check"
              checked={headLockNPC}
              onChange={(v) => { setHeadLockNPC(v); sendCombat('headlock_npc_check', v); }}
              color="purple"
            />
          </div>
        </HoloSection>

        {/* SILENT AIM */}
        <HoloSection title="👤 SILENT AIM">
          <ToggleSwitch
            label="Enabled"
            checked={silentAimEnabled}
            onChange={(v) => { setSilentAimEnabled(v); sendCombat('silent_aim_enabled', v); }}
            color="red"
          />
          <ToggleSwitch
            label="Team Check"
            checked={silentAimTeam}
            onChange={(v) => { setSilentAimTeam(v); sendCombat('silent_aim_team_check', v); }}
            color="red"
          />
        </HoloSection>

        {/* TRIGGERBOT */}
        <HoloSection title="⚡ TRIGGERBOT">
          <ToggleSwitch
            label="Enabled"
            checked={triggerEnabled}
            onChange={(v) => { setTriggerEnabled(v); sendCombat('triggerbot_enabled', v); }}
            color="cyan"
          />
          <HoloSlider
            label="Delay"
            value={triggerDelay}
            min={10}
            max={500}
            step={10}
            onChange={(v) => { setTriggerDelay(v); sendCombat('triggerbot_delay', v); }}
            unit="ms"
            color="green"
          />
        </HoloSection>

        {/* KILL AURA */}
        <HoloSection title="💀 KILL AURA">
          <ToggleSwitch
            label="Enabled"
            checked={killAuraEnabled}
            onChange={(v) => { setKillAuraEnabled(v); sendCombat('kill_aura_enabled', v); }}
            color="red"
          />
          <HoloSlider
            label="Range"
            value={killAuraRange}
            min={10}
            max={200}
            step={5}
            onChange={(v) => { setKillAuraRange(v); sendCombat('kill_aura_range', v); }}
            unit="m"
            color="red"
          />
        </HoloSection>
      </div>

      {/* Right Column */}
      <div className="holo-scroll" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)', paddingLeft: 4 }}>
        {/* RADAR */}
        <HoloPanel title="📡 RADAR (MiniMap)">
          <ToggleSwitch
            label="Show Radar"
            checked={radarEnabled}
            onChange={(v) => { setRadarEnabled(v); sendCombat('radar_enabled', v); }}
            color="green"
          />
          <HoloSlider
            label="Range"
            value={radarRange}
            min={100}
            max={2000}
            step={50}
            onChange={(v) => { setRadarRange(v); sendCombat('radar_range', v); }}
            unit="m"
            color="green"
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <ToggleSwitch
              label="NPC"
              checked={radarNPC}
              onChange={(v) => { setRadarNPC(v); sendCombat('radar_npc', v); }}
              color="yellow"
            />
            <ToggleSwitch
              label="Names"
              checked={radarNames}
              onChange={(v) => { setRadarNames(v); sendCombat('radar_names', v); }}
              color="cyan"
            />
            <ToggleSwitch
              label="Health"
              checked={radarHP}
              onChange={(v) => { setRadarHP(v); sendCombat('radar_hp', v); }}
              color="green"
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
            {radarEnabled && (
              <RadarCanvas
                size={280}
                range={radarRange}
                showNPC={radarNPC}
                showNames={radarNames}
                showHealth={radarHP}
                radarData={radarData}
              />
            )}
          </div>
        </HoloPanel>

        {/* COMBAT LOG */}
        <HoloPanel title="📋 COMBAT LOG" style={{ marginTop: 8 }}>
          <CombatLog entries={logEntries} />
        </HoloPanel>
      </div>
    </div>
  );
}
