import { Crosshair } from 'lucide-react';

export default function MapView() {
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

      <div className="absolute top-4 left-4 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-4 min-w-[240px]">
        <div className="flex items-center gap-2 mb-3">
          <Crosshair className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-gray-300">COORDINATES</span>
        </div>
        <div className="space-y-1 text-xs font-mono">
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
    </div>
  );
}
