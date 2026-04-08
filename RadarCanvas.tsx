'use client';

import React, { useRef, useEffect } from 'react';

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

interface RadarCanvasProps {
  size?: number;
  range?: number;
  showNPC?: boolean;
  showNames?: boolean;
  showHealth?: boolean;
  radarData?: RadarData | null;
}

export function RadarCanvas({
  size = 280,
  range = 500,
  showNPC = true,
  showNames = true,
  showHealth = true,
  radarData = null,
}: RadarCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const propsRef = useRef({ size, range, showNPC, showNames, showHealth });
  const angleRef = useRef(0);
  const dataRef = useRef<RadarData | null>(radarData);
  const animFrameRef = useRef<number>(0);

  // Keep refs in sync
  useEffect(() => {
    propsRef.current = { size, range, showNPC, showNames, showHealth };
  }, [size, range, showNPC, showNames, showHealth]);

  // Keep radar data ref in sync (no re-render needed)
  useEffect(() => {
    dataRef.current = radarData;
  }, [radarData]);

  // Main draw loop
  useEffect(() => {
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) { animFrameRef.current = requestAnimationFrame(draw); return; }
      const ctx = canvas.getContext('2d');
      if (!ctx) { animFrameRef.current = requestAnimationFrame(draw); return; }

      const { size: s, range: r, showNPC: sn, showNames: snm, showHealth: sh } = propsRef.current;
      const center = s / 2;
      const radius = s / 2 - 8;

      // Clear
      ctx.clearRect(0, 0, s, s);

      // Background
      ctx.fillStyle = 'rgba(5, 8, 15, 0.95)';
      ctx.beginPath();
      ctx.arc(center, center, radius, 0, Math.PI * 2);
      ctx.fill();

      // Grid circles
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.08)';
      ctx.lineWidth = 1;
      for (let i = 1; i <= 4; i++) {
        ctx.beginPath();
        ctx.arc(center, center, (radius / 4) * i, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Grid lines (cross)
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.06)';
      ctx.beginPath();
      ctx.moveTo(center - radius, center);
      ctx.lineTo(center + radius, center);
      ctx.moveTo(center, center - radius);
      ctx.lineTo(center, center + radius);
      ctx.stroke();

      // Diagonal lines
      ctx.beginPath();
      const diag = radius * 0.707;
      ctx.moveTo(center - diag, center - diag);
      ctx.lineTo(center + diag, center + diag);
      ctx.moveTo(center + diag, center - diag);
      ctx.lineTo(center - diag, center + diag);
      ctx.stroke();

      // Radar sweep
      angleRef.current += 0.02;
      const sweepAngle = angleRef.current;

      // Sweep arc
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.arc(center, center, radius, sweepAngle - 0.5, sweepAngle, false);
      ctx.closePath();
      const sweepGrad = ctx.createRadialGradient(center, center, 0, center, center, radius);
      sweepGrad.addColorStop(0, 'rgba(0, 212, 255, 0.15)');
      sweepGrad.addColorStop(1, 'rgba(0, 212, 255, 0.02)');
      ctx.fillStyle = sweepGrad;
      ctx.fill();
      ctx.restore();

      // Sweep line
      ctx.save();
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.5)';
      ctx.lineWidth = 1.5;
      ctx.shadowColor = 'rgba(0, 212, 255, 0.5)';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.lineTo(
        center + Math.cos(sweepAngle) * radius,
        center + Math.sin(sweepAngle) * radius
      );
      ctx.stroke();
      ctx.restore();

      // Draw blips from real data
      const data = dataRef.current;
      if (data && data.targets && data.targets.length > 0) {
        const yaw = data.camera_yaw || 0;
        const radarRange = data.range || r;
        const cosY = Math.cos(yaw);
        const sinY = Math.sin(yaw);

        const blips = data.targets.filter((t: RadarBlip) => sn || !t.is_npc);

        blips.forEach((blip: RadarBlip) => {
          // Transform world-relative coords to radar-relative
          // Forward direction = (sin(yaw), cos(yaw)) in (X,Z)
          // Right direction = (cos(yaw), -sin(yaw)) in (X,Z)
          const radarRight = blip.dx * cosY - blip.dz * sinY;
          const radarForward = blip.dx * sinY + blip.dz * cosY;

          // Normalize to radar range
          const normX = radarRight / radarRange;
          const normY = -radarForward / radarRange; // negate: forward = up on radar

          const bx = center + normX * radius;
          const by = center + normY * radius;

          // Check if in radar circle
          const dist = Math.sqrt((bx - center) ** 2 + (by - center) ** 2);
          if (dist > radius) return;

          // Determine color
          let color: string;
          if (blip.is_team) {
            color = '#00ff88'; // green for teammates
          } else if (blip.is_npc) {
            color = '#ffcc00'; // yellow for NPCs
          } else {
            color = '#ff3366'; // red for enemies
          }

          // Blip dot
          ctx.save();
          ctx.fillStyle = color;
          ctx.shadowColor = color;
          ctx.shadowBlur = 8;
          ctx.beginPath();
          ctx.arc(bx, by, 3.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();

          // Names
          if (snm) {
            ctx.save();
            ctx.font = '9px "JetBrains Mono", monospace';
            ctx.fillStyle = color;
            ctx.textAlign = 'center';
            const displayName = blip.name.length > 12 ? blip.name.slice(0, 11) + '..' : blip.name;
            ctx.fillText(displayName, bx, by - 8);
            ctx.restore();
          }

          // Health bar
          if (sh && blip.hp !== null && blip.hp !== undefined && blip.hp < 100) {
            const barWidth = 20;
            const barHeight = 2;
            const healthWidth = (blip.hp / 100) * barWidth;
            ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
            ctx.fillRect(bx - barWidth / 2, by + 7, barWidth, barHeight);
            ctx.fillStyle = blip.hp > 50 ? '#00ff88' : blip.hp > 25 ? '#ffcc00' : '#ff3366';
            ctx.fillRect(bx - barWidth / 2, by + 7, healthWidth, barHeight);
          }

          // Distance label
          ctx.save();
          ctx.font = '8px "JetBrains Mono", monospace';
          ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
          ctx.textAlign = 'center';
          ctx.fillText(`${Math.round(blip.dist)}m`, bx, by + 16);
          ctx.restore();
        });
      } else if (!data) {
        // No data yet - show "waiting" text
        ctx.save();
        ctx.font = '11px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgba(0, 212, 255, 0.3)';
        ctx.textAlign = 'center';
        ctx.fillText('WAITING DATA...', center, center + 30);
        ctx.restore();
      }

      // Center dot (player)
      ctx.save();
      ctx.fillStyle = '#00d4ff';
      ctx.shadowColor = '#00d4ff';
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(center, center, 4, 0, Math.PI * 2);
      ctx.fill();
      // White center
      ctx.fillStyle = '#ffffff';
      ctx.shadowBlur = 0;
      ctx.beginPath();
      ctx.arc(center, center, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // North indicator (small triangle at top)
      ctx.save();
      ctx.fillStyle = 'rgba(0, 212, 255, 0.6)';
      ctx.beginPath();
      ctx.moveTo(center, center - radius + 2);
      ctx.lineTo(center - 4, center - radius + 10);
      ctx.lineTo(center + 4, center - radius + 10);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      // Range text
      ctx.save();
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(0, 212, 255, 0.5)';
      ctx.textAlign = 'center';
      ctx.fillText(`${r}m`, center, center + radius - 4);
      ctx.restore();

      // Target count
      const targetCount = data?.targets?.length || 0;
      if (targetCount > 0) {
        ctx.save();
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgba(255, 51, 102, 0.6)';
        ctx.textAlign = 'right';
        ctx.fillText(`${targetCount} tgt`, center + radius - 4, center - radius + 14);
        ctx.restore();
      }

      // Border
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.25)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(center, center, radius, 0, Math.PI * 2);
      ctx.stroke();

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      className="holo-canvas"
      style={{ width: size, height: size }}
    />
  );
}
