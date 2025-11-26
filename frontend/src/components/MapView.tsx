import { Crosshair } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function MapView() {
  const [label, setLabel] = useState("unknown");

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/classification");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLabel(data.label);
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    return () => ws.close();
  }, []);

  return (
    <div className="w-full h-full bg-slate-800 relative">
      <div className="absolute inset-0 opacity-20">
        <div
          className="w-full h-full"
          style={{
            backgroundImage: `
              linear-gradient(rgba(16, 185, 129, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(16, 185, 129, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px'
          }}
        ></div>
      </div>
      <Microphones label={label} />
      <Coordinates label={label} />
    </div>
  );
}

export function Coordinates({ label }: { label: string }) {
  return (
    <div className="absolute top-4 left-4 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-4 min-w-[240px]">
      <div className="flex items-center gap-2 mb-3">
        <Crosshair className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-medium text-gray-300">COORDINATES</span>
      </div>
      <div className="space-y-1 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-gray-500">LABEL</span>
          <span className={label === "drone" ? "text-emerald-400" : "text-gray-300"}>
            {label}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">ANGLE</span>
          <span className="text-gray-300">--</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">DIRECTION</span>
          <span className="text-gray-300">--</span>
        </div>
      </div>
    </div>
  )
}

export function Microphones({ label }: { label: string }) {
  const microphones = [
    { id: "M1", x: 0, y: 0 },
    { id: "M2", x: 0, y: 3 },
    { id: "M3", x: 3, y: 0 },
    { id: "M4", x: 3, y: 3 },
  ];

  const scale = 200;
  const dotSize = 24;
  const offset = dotSize / 2;
  const lineStyle = "absolute border-gray-400 border-dashed";
  return (
    <div className="absolute top-1/2 right-1/4 w-[560px] h-[650px] transform -translate-y-1/2 animate-pulse">
      {/* top */}
      <div
        className={`${lineStyle} border-t-2`}
        style={{
          left: `${microphones[0].x * scale + offset}px`,
          top: `${microphones[0].y * scale + offset}px`,
          width: `${3 * scale}px`,
        }}
      />
      {/* bottom */}
      <div
        className={`${lineStyle} border-t-2`}
        style={{
          left: `${microphones[1].x * scale + offset}px`,
          top: `${microphones[1].y * scale + offset}px`,
          width: `${3 * scale}px`,
        }}
      />
      {/* left */}
      <div
        className={`${lineStyle} border-l-2`}
        style={{
          left: `${microphones[0].x * scale + offset}px`,
          top: `${microphones[0].y * scale + offset}px`,
          height: `${3 * scale}px`,
        }}
      />
      {/* right */}
      <div
        className={`${lineStyle} border-l-2`}
        style={{
          left: `${microphones[2].x * scale + offset}px`,
          top: `${microphones[2].y * scale + offset}px`,
          height: `${3 * scale}px`,
        }}
      />  

      {microphones.map((mic) => (
        <div
          className={`absolute w-6 h-6 rounded-full border-2 border-gray-400 flex items-center justify-center text-xs font-bold ${label === "drone" ? "bg-emerald-600"  : "bg-gray-600"
            }`}
          style={{
            left: `${mic.x * scale}px`,
            top: `${mic.y * scale}px`,
          }}
        >
        </div>
      ))}
    </div>
  )
}