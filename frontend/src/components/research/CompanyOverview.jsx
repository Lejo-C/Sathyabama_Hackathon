import React from 'react';
import { History } from 'lucide-react';

export default function CompanyOverview({ company, history }) {
  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#FFF7ED] flex items-center justify-center">
          <History className="w-4 h-4 text-[#F97316]" />
        </div>

        <div>
          <h3 className="text-xs font-bold text-[#171A1F]">
            Company Overview & History
          </h3>

          <p className="text-[9px] text-[#98A2B3]">
            Background and major milestones
          </p>
        </div>
      </div>

      <div className="space-y-3">

        {history.map((item, index) => (
          <div
            key={`${item.year}-${index}`}
            className="flex gap-3"
          >
            <div className="w-12 shrink-0 text-[10px] font-bold text-[#F97316]">
              {item.year}
            </div>

            <div className="flex-1 border-l border-[#E5E7EB] pl-3 pb-1">
              <p className="text-[10px] leading-5 text-[#475467]">
                {item.event}
              </p>
            </div>
          </div>
        ))}

      </div>
    </section>
  );
}