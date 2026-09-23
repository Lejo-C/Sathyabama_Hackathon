import React, { useEffect, useState } from 'react';
import { Clock3 } from 'lucide-react';

export default function RiskScore({
  score = 0,
  level,
  levelColor,
  summary,
}) {
  const radius = 48;
  const circumference = 2 * Math.PI * radius;

  const [animatedScore, setAnimatedScore] = useState(0);

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

      const eased = 1 - Math.pow(1 - progress, 3);

      setAnimatedScore(Math.round(endValue * eased));

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

  const companyName =
    summary?.companyName ||
    summary?.company ||
    summary?.metadata?.companyName ||
    'TechNova Solutions';

  const analyzedAt =
    summary?.timestamp ||
    summary?.analyzedAt ||
    summary?.createdAt ||
    '23 Sep 2026 • 10:42 PM';

  return (
    <div className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-1.5 h-full">



        {/* Bottom information bar */}
        <div className="mx-2 mb-2 rounded-lg bg-white border border-[#E5E7EB] px-3 py-2.5">

          <div className="grid grid-cols-3 divide-x divide-[#EEF2F6]">

            {/* Company */}
            <div className="px-2 min-w-0">
              <p className="text-[8px] uppercase tracking-wider font-medium text-[#98A2B3]">
                Company
              </p>

              <p
                className="text-[10px] font-semibold text-[#171A1F] truncate mt-1"
                title={companyName}
              >
                {companyName}
              </p>
            </div>

            {/* Risk */}
            <div className="px-3 text-center">
              <p className="text-[8px] uppercase tracking-wider font-medium text-[#98A2B3]">
                Risk
              </p>

              <p className="text-[10px] font-bold text-[#F97316] mt-1">
                {score}
                <span className="text-[8px] font-medium text-[#98A2B3]">
                  {' '}
                  / 100
                </span>
              </p>
            </div>

            {/* Timestamp */}
            <div className="px-2 min-w-0">

              <div className="flex items-center gap-1.5">

                <Clock3 className="w-3 h-3 text-[#667085] shrink-0" />

                <div className="min-w-0">
                  <p className="text-[8px] uppercase tracking-wider font-medium text-[#98A2B3]">
                    Analyzed
                  </p>

                  <p className="text-[9px] font-medium text-[#475467] truncate mt-1">
                    {analyzedAt}
                  </p>
                </div>

              </div>

            </div>

          </div>

        </div>

      </div>
  
  );
}