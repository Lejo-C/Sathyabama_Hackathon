import React from 'react';
import {
  ShieldAlert,
  Search,
  Plus,
  Download,
  Bell,
  Settings,
  ChevronDown,
  Filter
} from 'lucide-react';

export default function Header({ onNewAnalysis }) {
  return (
    <header className="bg-white border-b border-[#E5E7EB] sticky top-0 z-20 px-6 py-3 flex items-center justify-between gap-4 shadow-xs">
      {/* Left Branding & Filters */}
      <div className="flex items-center gap-6">
        {/* Brand Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#F97316] flex items-center justify-center text-white font-bold shadow-xs">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1">
              <span className="font-bold text-lg text-[#171A1F] tracking-tight">Job</span>
              <span className="font-bold text-lg text-[#F97316] tracking-tight">Guard</span>
            </div>
            <span className="text-[10px] text-[#667085] block font-medium uppercase tracking-wider -mt-1">
              Risk Intelligence
            </span>
          </div>
        </div>

        {/* Dropdown Filters */}
        <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-[#E5E7EB]">
          <div className="relative">
            <select className="appearance-none bg-[#F8FAFC] border border-[#E5E7EB] text-xs font-medium text-[#171A1F] py-1.5 pl-3 pr-8 rounded-md cursor-pointer hover:border-[#D1D5DB] focus:outline-none focus:ring-1 focus:ring-[#F97316]">
              <option>All Sectors</option>
              <option>IT & Software</option>
              <option>Data Entry & BPO</option>
              <option>Finance & Banking</option>
              <option>Remote Internships</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#667085] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <div className="relative">
            <select className="appearance-none bg-[#F8FAFC] border border-[#E5E7EB] text-xs font-medium text-[#171A1F] py-1.5 pl-3 pr-8 rounded-md cursor-pointer hover:border-[#D1D5DB] focus:outline-none focus:ring-1 focus:ring-[#F97316]">
              <option>Last 24 hours</option>
              <option>Last 7 days</option>
              <option>Last 30 days</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#667085] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <div className="relative">
            <select className="appearance-none bg-[#F8FAFC] border border-[#E5E7EB] text-xs font-medium text-[#171A1F] py-1.5 pl-3 pr-8 rounded-md cursor-pointer hover:border-[#D1D5DB] focus:outline-none focus:ring-1 focus:ring-[#F97316]">
              <option>INR (₹)</option>
              <option>USD ($)</option>
              <option>EUR (€)</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#667085] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Middle Search Bar */}
      <div className="flex-1 max-w-md hidden md:block">
        <div className="relative">
          <Search className="w-4 h-4 text-[#667085] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search job postings, companies, scam patterns..."
            className="w-full bg-[#F8FAFC] border border-[#E5E7EB] text-xs rounded-md pl-9 pr-4 py-1.5 text-[#171A1F] placeholder-[#667085] focus:outline-none focus:ring-1 focus:ring-[#F97316] focus:border-[#F97316] transition-all"
          />
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={onNewAnalysis}
          className="flex items-center gap-1.5 bg-[#F97316] hover:bg-[#EA580C] text-white text-xs font-semibold px-3.5 py-2 rounded-md shadow-xs transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Analysis</span>
        </button>

        <div className="flex items-center gap-1 border-l border-[#E5E7EB] pl-3">
          <button
            className="p-2 text-[#667085] hover:text-[#171A1F] hover:bg-[#F8FAFC] rounded-md transition-colors"
            title="Download Risk Report"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            className="p-2 text-[#667085] hover:text-[#171A1F] hover:bg-[#F8FAFC] rounded-md transition-colors relative"
            title="Alerts & Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="w-2 h-2 bg-[#F97316] rounded-full absolute top-1.5 right-1.5 border border-white"></span>
          </button>
          <button
            className="p-2 text-[#667085] hover:text-[#171A1F] hover:bg-[#F8FAFC] rounded-md transition-colors"
            title="System Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
