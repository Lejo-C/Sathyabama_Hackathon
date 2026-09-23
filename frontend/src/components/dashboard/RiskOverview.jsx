import React from 'react';
import RiskContributors from './RiskContributors';
import AnalysisSummary from './AnalysisSummary';

export default function RiskOverview({ result }) {
  if (!result) return null;

  return (
    <section className="space-y-2.5">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#171A1F]">
          Risk Overview & Fraud Indicators
        </h2>

        <span className="hidden sm:block text-[10px] text-[#667085]">
          ML & Pattern Analysis
        </span>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-3">
        <RiskContributors
          contributors={result.contributors}
        />

        <AnalysisSummary
          summary={result.summary}
        />
      </div>
    </section>
  );
}