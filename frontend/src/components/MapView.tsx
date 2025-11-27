import { Crosshair, Compass, Ruler, Radio, Locate } from 'lucide-react';
import { useEffect, useState } from 'react';
import MicrophoneIcon from './test';

const API_HOST = import.meta.env.VITE_API_HOST || window.location.hostname;
const API_PORT = import.meta.env.VITE_API_PORT || '8000';
const WS_URL = `ws://${API_HOST}:${API_PORT}/ws`;
const API_URL = `http://${API_HOST}:${API_PORT}`;

interface LocalizationData {
  azimuth: number;
  distance: number;
  position_x: number;
  position_y: number;
  mic_distances: {
    bottom_left: number;
    bottom_right: number;
    top_left: number;
    top_right: number;
  };
}

type DisplayLabel = "unknown" | "drone" | "listening";

export default function MapView() {
  const [label, setLabel] = useState<DisplayLabel>("unknown");
  const [localization, setLocalization] = useState<LocalizationData | null>(null);
  const [isLocalizing, setIsLocalizing] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === "classification") {
        if (!isLocalizing) {
          setLabel(data.label);
        }
      } else if (data.type === "localization_start") {
        setIsLocalizing(true);
        if (data.manual) {
          setLabel("listening");
        }
      } else if (data.type === "localization") {
        setLocalization({
          azimuth: data.azimuth,
          distance: data.distance,
          position_x: data.position_x,
          position_y: data.position_y,
          mic_distances: data.mic_distances,
        });
      } else if (data.type === "localization_end") {
        setIsLocalizing(false);
        if (data.manual) {
          setLabel("unknown");
        }
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    return () => ws.close();
  }, [isLocalizing]);

  const handleTriggerLocalization = async () => {
    try {
      await fetch(`${API_URL}/api/trigger-localization`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to trigger localization:", err);
    }
  };

  return (
    <div className="w-full h-full bg-slate-800 relative overflow-hidden">
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

      
      <div className="flex h-full">
        <div className="w-[280px] flex-shrink-0 p-4 space-y-3 z-10">
          <DroneBox label={label} isLocalizing={isLocalizing} />
          <DirectionBox azimuth={localization?.azimuth ?? null} />
          <DistanceBox distance={localization?.distance ?? null} />
          <MultilaterationBox micDistances={localization?.mic_distances ?? null} />
          <TriggerButton onClick={handleTriggerLocalization} isLocalizing={isLocalizing} />
        </div>
        
        <div className="flex-1 flex items-center justify-center">
          <Microphones label={label} localization={localization} />
        </div>
      </div>
    </div>
  );
}

function DroneBox({ label, isLocalizing }: { label: DisplayLabel; isLocalizing: boolean }) {
  const getDisplayText = () => {
    if (label === "listening") return "Manual Listening";
    if (label === "drone") return "Drone";
    return "Unknown";
  };

  const getTextColor = () => {
    if (label === "listening") return "text-amber-400";
    if (label === "drone") return "text-emerald-400";
    return "text-gray-300";
  };

  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Radio className={`w-4 h-4 ${isLocalizing ? "text-amber-400" : "text-emerald-400"}`} />
        <span className="text-sm font-medium text-gray-300">DRONE</span>
      </div>
      <div className="space-y-1 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-gray-500">LABEL</span>
          <span className={getTextColor()}>
            {getDisplayText()}
          </span>
        </div>
      </div>
    </div>
  );
}

function DirectionBox({ azimuth }: { azimuth: number | null }) {
  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Compass className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-medium text-gray-300">DIRECTION</span>
      </div>
      <div className="space-y-1 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-gray-500">AZIMUTH</span>
          <span className="text-gray-300">
            {azimuth !== null ? `${azimuth.toFixed(1)}` : "--"}
          </span>
        </div>
      </div>
    </div>
  );
}

function DistanceBox({ distance }: { distance: number | null }) {
  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Ruler className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-medium text-gray-300">DISTANCE</span>
      </div>
      <div className="space-y-1 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-gray-500">FROM CENTER</span>
          <span className="text-gray-300">
            {distance !== null ? `${distance.toFixed(2)} m` : "--"}
          </span>
        </div>
      </div>
    </div>
  );
}

interface MicDistances {
  bottom_left: number;
  bottom_right: number;
  top_left: number;
  top_right: number;
}

function MultilaterationBox({ micDistances }: { micDistances: MicDistances | null }) {
  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Crosshair className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-medium text-gray-300">MULTILATERATION</span>
      </div>
      <div className="space-y-1 text-xs font-mono">
        <div className="flex justify-between">
          <span className="text-gray-500">M1 (BL)</span>
          <span className="text-gray-300">
            {micDistances ? `${micDistances.bottom_left.toFixed(2)} m` : "--"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">M2 (BR)</span>
          <span className="text-gray-300">
            {micDistances ? `${micDistances.bottom_right.toFixed(2)} m` : "--"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">M3 (TL)</span>
          <span className="text-gray-300">
            {micDistances ? `${micDistances.top_left.toFixed(2)} m` : "--"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">M4 (TR)</span>
          <span className="text-gray-300">
            {micDistances ? `${micDistances.top_right.toFixed(2)} m` : "--"}
          </span>
        </div>
      </div>
    </div>
  );
}

function TriggerButton({ onClick, isLocalizing }: { onClick: () => void; isLocalizing: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={isLocalizing}
      className={`w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        isLocalizing
          ? "bg-amber-600/30 text-amber-400 cursor-not-allowed border border-amber-600/50"
          : "bg-slate-700/80 hover:bg-slate-600 text-gray-300 border border-slate-600"
      }`}
    >
      <Locate className="w-4 h-4" />
      {isLocalizing ? "Localizing..." : "Locate Sound"}
    </button>
  );
}

interface MicrophonesProps {
  label: DisplayLabel;
  localization: LocalizationData | null;
}

export function Microphones({ label, localization }: MicrophonesProps) {
  const microphones = [
    { id: "M1", x: 0, y: 0 },
    { id: "M2", x: 0, y: 3 },
    { id: "M3", x: 3, y: 0 },
    { id: "M4", x: 3, y: 3 },
  ];

  const scale = 180;
  const dotSize = 24;
  const offset = dotSize / 2;
  const lineStyle = "absolute border-gray-400 border-dashed";
  
  const arraySize = 3.0;
  
  let targetDotPosition: { left: number; top: number } | null = null;
  if (localization) {
    const posX = Math.max(0, Math.min(arraySize, localization.position_x));
    const posY = Math.max(0, Math.min(arraySize, localization.position_y));
    targetDotPosition = {
      left: posX * scale,
      top: (arraySize - posY) * scale,
    };
  }

  const isActive = label === "drone" || label === "listening";


  return (
    <div className={`relative w-[580px] h-[580px] ${isActive ? "animate-pulse" : ""}`}>
      {/* top dimension label */}
      <div
        className="absolute top-1/2 transform -translate-y-1/2 text-xs text-gray-300"
        style={{
          left: `${microphones[0].x * scale + offset + 280}px`,
          top: `${microphones[0].y * scale + offset - 10}px`
        }}
      >
        {arraySize}m
      </div>
      {/* top */}
      <div


        style={{
          left: `${microphones[0].x * scale + offset}px`,
          top: `${microphones[0].y * scale + offset}px`,
          width: widthValue,
        }}
      >
      </div>
      {/* bottom */}
      <div

        className={`${lineStyle} border-t-2 ${isActive ? "bg-emerald-600" : "bg-gray-600"}`}

        style={{
          left: `${microphones[1].x * scale + offset}px`,
          top: `${microphones[1].y * scale + offset}px`,
          width: widthValue,
        }}
      />
      {/* left */}
      <div

        className={`${lineStyle} border-l-2 ${isActive ? "bg-emerald-600" : "bg-gray-600"}`}

        style={{
          left: `${microphones[0].x * scale + offset}px`,
          top: `${microphones[0].y * scale + offset}px`,
          height: widthValue,
        }}
      />
      {/* right dimension label */}
      <div
        className="absolute top-1/2 transform -translate-y-1/2 text-xs text-gray-300"
        style={{
          left: `${microphones[2].x * scale + offset + 10}px`, 
          top: `${microphones[2].y * scale + offset + 280}px`,
        }}
      >
        {arraySize}m
      </div>
      {/* right */}
      <div

        className={`${lineStyle} border-l-2 ${isActive ? "bg-emerald-600" : "bg-gray-600"}`}

        style={{
          left: `${microphones[2].x * scale + offset}px`,
          top: `${microphones[2].y * scale + offset}px`,
          height: widthValue,
        }}
      />

      {microphones.map((mic) => (
        <div
          key={mic.id}
          className={`absolute w-6 h-6 rounded-full border-2 border-gray-400 flex items-center justify-center text-xs font-bold ${
            isActive ? "bg-emerald-600" : "bg-gray-600"
          }`}

          style={{
            left: `${mic.x * scale}px`,
            top: `${mic.y * scale}px`,
          }}
        >
          <MicrophoneIcon />
        </div>
      ))}
      
      {targetDotPosition && (
        <div
          className="absolute w-4 h-4 rounded-full bg-lime-400 animate-ping-slow"
          style={{
            left: `${targetDotPosition.left + offset - 8}px`,
            top: `${targetDotPosition.top + offset - 8}px`,
            boxShadow: '0 0 12px 4px rgba(163, 230, 53, 0.6)',
          }}
        />
      )}
      {targetDotPosition && (
        <div
          className="absolute w-3 h-3 rounded-full bg-lime-300"
          style={{
            left: `${targetDotPosition.left + offset - 6}px`,
            top: `${targetDotPosition.top + offset - 6}px`,
          }}
        />
      )}
    </div>
  );
}
