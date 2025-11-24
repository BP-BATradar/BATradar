import { Activity, Radio, Shield } from 'lucide-react';

export default function Header() {
  return (
    <header className="h-16 bg-slate-950 border-b border-slate-700 flex items-center px-6">
      <div className="flex items-center gap-3">
        <div className="relative item">
          <Radio className="w-8 h-8 text-emerald-400" />
          <div className="absolute -top-1 -right-1 w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-wider text-gray-100">
            BATradar
          </h1>
          <p className="text-xs text-gray-400 tracking-wide">
            Drone Localization Engine
          </p>
        </div>
      </div>
    </header>
  );
}
