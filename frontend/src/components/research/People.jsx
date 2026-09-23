import React from 'react';
import { Users } from 'lucide-react';

export default function People({ people }) {
  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#FFF7ED] flex items-center justify-center">
          <Users className="w-4 h-4 text-[#F97316]" />
        </div>

        <div>
          <h3 className="text-xs font-bold text-[#171A1F]">
            People
          </h3>

          <p className="text-[9px] text-[#98A2B3]">
            Key people associated with the company
          </p>
        </div>
      </div>

      <div className="space-y-2">

        {people.map((person) => (
          <div
            key={`${person.name}-${person.role}`}
            className="flex items-center justify-between rounded-lg bg-[#F8FAFC] border border-[#EEF2F6] px-3 py-2.5"
          >
            <span className="text-[10px] font-semibold text-[#171A1F]">
              {person.name}
            </span>

            <span className="text-[9px] text-[#667085]">
              {person.role}
            </span>
          </div>
        ))}

      </div>
    </section>
  );
}