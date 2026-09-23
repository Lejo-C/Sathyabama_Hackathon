import React from 'react';
import {
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Globe,
  MapPin,
  Users,
} from 'lucide-react';

export default function CompanyDesk({ company }) {
  const details = [
    {
      label: 'Industry',
      value: company.industry,
      icon: BriefcaseBusiness,
    },
    {
      label: 'Founded',
      value: company.founded,
      icon: CalendarDays,
    },
    {
      label: 'Headquarters',
      value: company.headquarters,
      icon: MapPin,
    },
    {
      label: 'Company Type',
      value: company.type,
      icon: Building2,
    },
    {
      label: 'Employees',
      value: company.employees,
      icon: Users,
    },
    {
      label: 'Website',
      value: company.website,
      icon: Globe,
    },
  ];

  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="mb-4">
        <h3 className="text-xs font-bold text-[#171A1F]">
          Company Desk
        </h3>

        <p className="text-[9px] text-[#98A2B3] mt-0.5">
          Key company information
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">

        {details.map((item) => {
          const Icon = item.icon;

          return (
            <div
              key={item.label}
              className="rounded-lg bg-[#F8FAFC] border border-[#EEF2F6] p-2.5"
            >
              <div className="flex items-center gap-1.5">
                <Icon className="w-3 h-3 text-[#98A2B3]" />

                <span className="text-[8px] uppercase tracking-wider text-[#98A2B3]">
                  {item.label}
                </span>
              </div>

              <p
                className="text-[10px] font-semibold text-[#171A1F] mt-1 truncate"
                title={item.value}
              >
                {item.value}
              </p>
            </div>
          );
        })}

      </div>
    </section>
  );
}