import React from 'react';
import { LayoutDashboard, Search } from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab }) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'job-analysis', label: 'Job Analysis', icon: Search },
  ];

  return (
    <aside className="w-55 shrink-0 h-[calc(100vh-8.75rem)] min-h-[520px] bg-[#18212B] text-[#94A3B8] rounded-2xl overflow-hidden shadow-sm border border-[#263342]">
      <div className="h-full flex flex-col px-2.5 py-3">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-4 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  isActive
                    ? 'bg-[#253243] text-white font-semibold'
                    : 'text-[#94A3B8] hover:bg-[#1F2B38] hover:text-white'
                }`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    isActive ? 'text-[#F97316]' : 'text-[#64748B]'
                  }`}
                />
                <span className="truncate text-left">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
