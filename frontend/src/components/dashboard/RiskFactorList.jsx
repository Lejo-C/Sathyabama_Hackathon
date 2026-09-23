import React, { useState } from 'react';
import RiskFactor from './RiskFactor';
import { ShieldAlert, Filter, CheckCircle } from 'lucide-react';

export default function RiskFactorList({ riskFactors }) {
  const [filter, setFilter] = useState('ALL');

  if (!riskFactors || riskFactors.length === 0) return null;

  const filteredFactors = riskFactors.filter((item) => {
    if (filter === 'ALL') return true;
    return item.severity === filter;
  });

  const criticalCount = riskFactors.filter(r => r.severity === 'CRITICAL').length;
  const highCount = riskFactors.filter(r => r.severity === 'HIGH').length;
  const mediumCount = riskFactors.filter(r => r.severity === 'MEDIUM').length;
  const lowCount = riskFactors.filter(r => r.severity === 'LOW').length;

  return (
    <div className="space-y-3">
      {/* Section Header & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-[#E5E7EB] shadow-xs">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-[#171A1F] flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[#F97316]" />
            <span>Detected Risk Signals ({riskFactors.length} Inspected)</span>
          </h2>
          <p className="text-xs text-[#667085] mt-0.5">
            Level 1 inspection breakdown for scam patterns, fraud evidence, and risk severity.
          </p>
        </div>

        {/* Severity Filter Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
          <button
            onClick={() => setFilter('ALL')}
            className={`text-xs font-semibold px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
              filter === 'ALL'
                ? 'bg-[#171A1F] text-white'
                : 'text-[#667085] hover:bg-[#F8FAFC]'
            }`}
          >
            All ({riskFactors.length})
          </button>
          <button
            onClick={() => setFilter('CRITICAL')}
            className={`text-xs font-semibold px-2.5 py-1.5 rounded-md transition-colors cursor-pointer ${
              filter === 'CRITICAL'
                ? 'bg-red-600 text-white'
                : 'text-red-700 bg-red-50 hover:bg-red-100'
            }`}
          >
            Critical ({criticalCount})
          </button>
          <button
            onClick={() => setFilter('HIGH')}
            className={`text-xs font-semibold px-2.5 py-1.5 rounded-md transition-colors cursor-pointer ${
              filter === 'HIGH'
                ? 'bg-[#F97316] text-white'
                : 'text-orange-700 bg-orange-50 hover:bg-orange-100'
            }`}
          >
            High ({highCount})
          </button>
          <button
            onClick={() => setFilter('MEDIUM')}
            className={`text-xs font-semibold px-2.5 py-1.5 rounded-md transition-colors cursor-pointer ${
              filter === 'MEDIUM'
                ? 'bg-amber-600 text-white'
                : 'text-amber-700 bg-amber-50 hover:bg-amber-100'
            }`}
          >
            Medium ({mediumCount})
          </button>
          <button
            onClick={() => setFilter('LOW')}
            className={`text-xs font-semibold px-2.5 py-1.5 rounded-md transition-colors cursor-pointer ${
              filter === 'LOW'
                ? 'bg-gray-700 text-white'
                : 'text-gray-700 bg-gray-100 hover:bg-gray-200'
            }`}
          >
            Low ({lowCount})
          </button>
        </div>
      </div>

      {/* List of Risk Factor Cards */}
      <div className="space-y-2.5">
        {filteredFactors.map((factor) => (
          <RiskFactor key={factor.id} factor={factor} />
        ))}
        {filteredFactors.length === 0 && (
          <div className="bg-white p-8 rounded-lg border border-[#E5E7EB] text-center text-xs text-[#667085]">
            No risk signals found under the selected filter.
          </div>
        )}
      </div>
    </div>
  );
}
