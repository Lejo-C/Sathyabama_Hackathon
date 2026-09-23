import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Info,
  Quote,
  ShieldAlert,
  Copy,
  Check
} from 'lucide-react';

export default function RiskFactor({ factor }) {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(factor.evidence);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getSeverityStyle = (severity) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'HIGH':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      case 'MEDIUM':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'LOW':
        return 'bg-gray-100 text-gray-700 border-gray-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="bg-white rounded-lg border border-[#E5E7EB] overflow-hidden transition-all duration-200 shadow-xs hover:border-[#D1D5DB]">
      {/* Main Header Row */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer hover:bg-[#F8FAFC] transition-colors"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5">
            <ShieldAlert className={`w-5 h-5 ${
              factor.severity === 'CRITICAL' ? 'text-red-500' :
              factor.severity === 'HIGH' ? 'text-[#F97316]' :
              factor.severity === 'MEDIUM' ? 'text-amber-500' : 'text-gray-400'
            }`} />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-bold text-[#171A1F]">{factor.title}</h4>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${getSeverityStyle(factor.severity)}`}>
                {factor.severity}
              </span>
              <span className="text-[11px] text-[#667085] bg-[#F1F5F9] px-2 py-0.5 rounded">
                {factor.category}
              </span>
            </div>
            <p className="text-xs text-[#667085] mt-1 leading-relaxed">
              {factor.explanation}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
          <button
            type="button"
            className="flex items-center gap-1 text-xs font-semibold text-[#F97316] hover:text-[#EA580C] px-2.5 py-1 rounded bg-[#FFF7ED] hover:bg-[#FFEDD5] transition-colors"
          >
            <span>{expanded ? 'Hide Evidence' : 'Show Evidence'}</span>
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Expandable Evidence Drawer */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 bg-[#F8FAFC] border-t border-[#F1F5F9]">
          <div className="bg-white border border-[#E5E7EB] rounded-md p-3 relative group">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-[#667085] uppercase tracking-wider flex items-center gap-1">
                <Quote className="w-3 h-3 text-[#F97316]" />
                <span>Extracted Evidence Snippet</span>
              </span>
              <button
                onClick={handleCopy}
                className="text-[11px] text-[#667085] hover:text-[#171A1F] flex items-center gap-1 bg-[#F8FAFC] hover:bg-[#F1F5F9] px-2 py-0.5 rounded border border-[#E5E7EB] transition-colors"
                title="Copy evidence"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 text-green-600" />
                    <span className="text-green-600 font-medium">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-xs font-mono text-[#171A1F] bg-[#F1F5F9] p-2.5 rounded border border-[#E2E8F0] leading-relaxed italic">
              "{factor.evidence}"
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
