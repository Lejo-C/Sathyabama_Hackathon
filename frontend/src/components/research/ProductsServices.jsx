import React from 'react';
import { Boxes } from 'lucide-react';

export default function ProductsServices({ products }) {
  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#FFF7ED] flex items-center justify-center">
          <Boxes className="w-4 h-4 text-[#F97316]" />
        </div>

        <div>
          <h3 className="text-xs font-bold text-[#171A1F]">
            Core Products & Services
          </h3>

          <p className="text-[9px] text-[#98A2B3]">
            Main offerings identified during research
          </p>
        </div>
      </div>

      <div className="space-y-2">

        {products.map((product, index) => (
          <div
            key={product.name}
            className="rounded-lg bg-[#F8FAFC] border border-[#EEF2F6] p-3"
          >
            <div className="flex items-start gap-3">

              <span className="text-[9px] font-bold text-[#F97316] mt-0.5">
                {String(index + 1).padStart(2, '0')}
              </span>

              <div>
                <h4 className="text-[10px] font-bold text-[#171A1F]">
                  {product.name}
                </h4>

                <p className="text-[9px] leading-4 text-[#667085] mt-1">
                  {product.description}
                </p>
              </div>

            </div>
          </div>
        ))}

      </div>
    </section>
  );
}