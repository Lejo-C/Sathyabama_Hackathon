import React from 'react';
import {
  IndianRupee,
  Wallet,
  TrendingUp,
  BarChart3,
} from 'lucide-react';

export default function FinancialSnapshot({ financials }) {
  const items = [
    {
      label: 'Revenue',
      value: financials.revenue,
      icon: IndianRupee,
    },
    {
      label: 'Funding',
      value: financials.funding,
      icon: Wallet,
    },
    {
      label: 'Valuation',
      value: financials.valuation,
      icon: BarChart3,
    },
    {
      label: 'Growth',
      value: financials.growth,
      icon: TrendingUp,
    },
  ];

  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="mb-3">
        <p className="text-[9px] font-bold uppercase tracking-wider text-[#98A2B3]">
          Company Research
        </p>

        <h3 className="text-sm font-bold text-[#171A1F] mt-0.5">
          Financial Snapshot
        </h3>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">

        {items.map((item) => {
          const Icon = item.icon;

          return (
            <div
              key={item.label}
              className="rounded-lg bg-[#F8FAFC] border border-[#EEF2F6] p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-[9px] uppercase tracking-wider font-medium text-[#98A2B3]">
                  {item.label}
                </span>

                <Icon className="w-3.5 h-3.5 text-[#F97316]" />
              </div>

              <p className="text-sm font-bold text-[#171A1F] mt-2">
                {item.value || 'Not disclosed'}
              </p>
            </div>
          );
        })}

      </div>

      <p className="text-[9px] text-[#98A2B3] mt-3">
        Financial figures should be displayed only when supported by available sources.
      </p>

    </section>
  );
}