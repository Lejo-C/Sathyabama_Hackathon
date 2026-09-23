
import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

export default function RiskScore({ score = 0, level, levelColor }) {
  const radius = 48;
  const circumference = 2 * Math.PI * radius;

  const [animatedScore, setAnimatedScore] = useState(0);

  // Smooth score animation
  useEffect(() => {
    let frame;
    let startTime;

    const duration = 1000;
    const endValue = Number(score) || 0;

    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp;

      const progress = Math.min(
        (timestamp - startTime) / duration,
        1
      );

      // Smooth ease-out
      const eased = 1 - Math.pow(1 - progress, 3);

      setAnimatedScore(
        Math.round(endValue * eased)
      );

      if (progress < 1) {
        frame = requestAnimationFrame(animate);
      }
    };

    setAnimatedScore(0);
    frame = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(frame);
  }, [score]);

  const strokeDashoffset =
    circumference -
    (animatedScore / 100) * circumference;

  return (
    <div className="bg-white rounded-lg border border-[#E5E7EB] p-5 shadow-xs flex flex-col h-full">

      {/* Header */}
      <div className="flex items-center justify-center gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
          Overall Risk Score
        </h3>

        <span
          className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${levelColor}`}
        >
          {level}
        </span>
      </div>

      {/* Main Gauge */}
      <div className="flex flex-1 items-center justify-center py-3">

        <div className="relative w-44 h-44 flex items-center justify-center">

          {/* Very subtle orange ambient ring */}

          <svg
            className="absolute inset-0 w-full h-full -rotate-90"
            viewBox="0 0 120 120"
          >

            {/* Soft outer border */}
            <circle
              cx="60"
              cy="60"
              r="53"
              fill="none"
              stroke="#F1F5F9"
              strokeWidth="1"
            />

            {/* Background track */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#E9EDF2"
              strokeWidth="9"
            />

            {/* Orange progress ring */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#F97316"
              strokeWidth="9"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              style={{
                transition:
                  'stroke-dashoffset 80ms linear',
                filter:
                  'drop-shadow(0 0 4px rgba(249,115,22,0.22))',
              }}
            />

            {/* Small orange endpoint */}
            <circle
              cx="60"
              cy="12"
              r="2.2"
              fill="#F97316"
            />

          </svg>

          {/* Center score */}
          <div className="relative flex flex-col items-center justify-center">

            <div className="text-5xl font-black tracking-tight leading-none text-[#171A1F]">
              {animatedScore}
            </div>

            <div className="text-[10px] text-[#667085] uppercase tracking-[0.18em] mt-2">
              Risk Score
            </div>

            <div className="text-[9px] text-[#98A2B3] mt-0.5">
              / 100
            </div>

          </div>
        </div>
      </div>

      {/* Quick Context */}
      <div className="grid grid-cols-3 gap-2 mb-4">

        {/* Threat */}
        <div className="rounded-md bg-[#F8FAFC] border border-[#EEF2F6] px-2 py-2.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-[#98A2B3]">
            Threat
          </div>

          <div className="text-xs font-bold text-[#EF4444] mt-1">
            Critical
          </div>
        </div>

        {/* Signals */}
        <div className="rounded-md bg-[#F8FAFC] border border-[#EEF2F6] px-2 py-2.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-[#98A2B3]">
            Signals
          </div>

          <div className="text-xs font-bold text-[#171A1F] mt-1">
            7 Factors
          </div>
        </div>

        {/* Flagged */}
        <div className="rounded-md bg-[#F8FAFC] border border-[#EEF2F6] px-2 py-2.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-[#98A2B3]">
            Flagged
          </div>

          <div className="text-xs font-bold text-[#171A1F] mt-1">
            5 Signals
          </div>
        </div>

      </div>

      {/* Footer */}
      <div className="pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-[10px]">

        <span className="flex items-center gap-1.5 font-medium text-red-600">
          <AlertTriangle className="w-3.5 h-3.5" />

          <span>
            High Fraud Probability
          </span>
        </span>

        <span className="font-mono text-[9px] text-[#667085] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#E5E7EB]">
          Scan Engine #L1-7
        </span>

      </div>

    </div>
  );
}
