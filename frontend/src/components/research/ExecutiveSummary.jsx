import React from 'react';
import {
  Building2,
  Globe2,
  MapPin,
  Users,
} from 'lucide-react';

export default function ExecutiveSummary({ company, summary }) {
  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-[#98A2B3]">
            Research
          </p>

          <h3 className="text-sm font-bold text-[#171A1F] mt-0.5">
            Executive Summary
          </h3>
        </div>

        <div className="w-8 h-8 rounded-lg bg-[#FFF7ED] flex items-center justify-center">
          <Building2 className="w-4 h-4 text-[#F97316]" />
        </div>
      </div>

      <p className="text-xs leading-6 text-[#475467] max-w-4xl">
        {summary}
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4">

        <InfoItem
          icon={Building2}
          label="Company"
          value={company.name}
        />

        <InfoItem
          icon={Globe2}
          label="Industry"
          value={company.industry}
        />

        <InfoItem
          icon={MapPin}
          label="Headquarters"
          value={company.headquarters}
        />

        <InfoItem
          icon={Users}
          label="Employees"
          value={company.employees}
        />

      </div>
    </section>
  );
}

function InfoItem({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg bg-[#F8FAFC] border border-[#EEF2F6] px-3 py-2.5">
      <div className="flex items-center gap-1.5">
        <Icon className="w-3 h-3 text-[#98A2B3]" />

        <span className="text-[8px] uppercase tracking-wider font-medium text-[#98A2B3]">
          {label}
        </span>
      </div>

      <p className="text-[10px] font-semibold text-[#171A1F] mt-1 truncate">
        {value}
      </p>
    </div>
  );
}