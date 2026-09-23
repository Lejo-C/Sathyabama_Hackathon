import React, { useEffect, useState } from 'react';

export default function RiskContributors({ contributors = [] }) {
  const items = contributors.slice(0, 5);

  const [animatedValues, setAnimatedValues] = useState(
    items.map(() => 0)
  );

  useEffect(() => {
    setAnimatedValues(items.map(() => 0));

    const timer = setTimeout(() => {
      setAnimatedValues(items.map((item) => item.percentage));
    }, 120);

    return () => clearTimeout(timer);
  }, [contributors]);

  const totalWeight = items.reduce(
    (sum, item) => sum + Number(item.percentage || 0),
    0
  );

  return (
    <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-sm flex flex-col h-full overflow-hidden">

      {/* Header */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <h3 className="text-sm font-semibold text-[#171A1F]">
            Top Risk Contributors
          </h3>

          <p className="text-[11px] text-[#667085] mt-0.5">
            Signals contributing to the overall risk score
          </p>
        </div>

        <div className="text-[10px] font-medium text-[#98A2B3] uppercase tracking-wider">
          Weight
        </div>
      </div>

      {/* Chart */}
      <div className="mt-4 flex-1">

        {/* Y-axis labels + chart */}
        <div className="relative h-[185px]">

          {/* Horizontal grid lines */}
          <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
            {[100, 75, 50, 25, 0].map((value) => (
              <div
                key={value}
                className="flex items-center w-full"
              >
                <span className="w-7 text-[9px] font-mono text-[#98A2B3]">
                  {value}
                </span>

                <div className="flex-1 border-t border-dashed border-[#E9EDF2]" />
              </div>
            ))}
          </div>

          {/* Bars */}
          <div className="absolute left-8 right-0 top-0 bottom-0 flex items-end gap-4 px-1">

            {items.map((item, index) => {
              const value = Number(item.percentage || 0);
              const animatedValue = animatedValues[index] || 0;

              return (
                <div
                  key={item.id || item.title}
                  className="relative h-full flex-1 flex flex-col justify-end items-center group min-w-0"
                >

                  {/* Percentage label */}
                  <div
                    className="
                      absolute
                      text-[10px]
                      font-bold
                      font-mono
                      text-[#171A1F]
                      transition-all
                      duration-700
                      ease-out
                      whitespace-nowrap
                    "
                    style={{
                      bottom: `calc(${animatedValue}% + 6px)`,
                      opacity: animatedValue > 0 ? 1 : 0,
                      transform:
                        animatedValue > 0
                          ? 'translateY(0)'
                          : 'translateY(5px)',
                    }}
                  >
                    {value}%
                  </div>

                  {/* Bar track */}
                  <div className="relative w-full max-w-[40px] h-full flex items-end">

                    {/* Background */}
                    <div className="absolute inset-x-0 bottom-0 h-full rounded-t-md bg-[#F8FAFC]" />

                    {/* Active bar */}
                    <div
                      className="
                        relative
                        w-full
                        rounded-t-md
                        overflow-hidden
                        transition-[height]
                        duration-1000
                        ease-[cubic-bezier(0.22,1,0.36,1)]
                      "
                      style={{
                        height: `${animatedValue}%`,
                        backgroundColor: item.color || '#F97316',
                      }}
                    >
                      {/* Highlight */}
                      <div className="absolute inset-x-0 top-0 h-1 bg-white/30" />

                      {/* Animated shine */}
                      <div
                        className="
                          absolute
                          inset-0
                          bg-gradient-to-r
                          from-transparent
                          via-white/20
                          to-transparent
                          -translate-x-full
                          group-hover:translate-x-full
                          transition-transform
                          duration-700
                        "
                      />
                    </div>
                  </div>

                  {/* Bottom label */}
                  <div className="absolute top-full mt-2 w-full text-center">

                    <div
                      className="
                        text-[9px]
                        font-medium
                        text-[#475467]
                        leading-tight
                        line-clamp-2
                        px-0.5
                      "
                      title={item.title}
                    >
                      {item.title}
                    </div>
                  </div>

                  {/* Hover tooltip */}
                  <div
                    className="
                      pointer-events-none
                      absolute
                      left-1/2
                      -translate-x-1/2
                      -translate-y-1
                      opacity-0
                      group-hover:opacity-100
                      group-hover:-translate-y-2
                      transition-all
                      duration-200
                      z-20
                    "
                    style={{
                      bottom: `calc(${animatedValue}% + 2rem)`,
                    }}
                  >
                    <div className="bg-[#18212B] text-white rounded-md px-2.5 py-2 shadow-lg whitespace-nowrap">
                      <p className="text-[10px] text-[#CBD5E1]">
                        {item.title}
                      </p>

                      <p className="text-xs font-bold mt-0.5">
                        {value}% contribution
                      </p>
                    </div>
                  </div>

                </div>
              );
            })}

          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-8 pt-3 border-t border-[#F1F5F9] flex items-center justify-between">

        <div>
          <span className="text-[10px] uppercase tracking-wider text-[#98A2B3]">
            Combined Weight
          </span>

          <div className="text-xs font-semibold text-[#171A1F] mt-0.5">
            {totalWeight}%
          </div>
        </div>

        {/* Mini visual indicator */}
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-[#F97316]" />

          <span className="text-[10px] text-[#667085]">
            5 strongest signals
          </span>
        </div>

      </div>
    </div>
  );
}


