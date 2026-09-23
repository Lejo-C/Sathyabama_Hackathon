import React from 'react';
import { FolderKanban } from 'lucide-react';

export default function Projects({ projects }) {
  return (
    <section className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4">

      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#FFF7ED] flex items-center justify-center">
          <FolderKanban className="w-4 h-4 text-[#F97316]" />
        </div>

        <div>
          <h3 className="text-xs font-bold text-[#171A1F]">
            Projects
          </h3>

          <p className="text-[9px] text-[#98A2B3]">
            Known or reported projects
          </p>
        </div>
      </div>

      <div className="space-y-2">

        {projects.map((project, index) => (
          <div
            key={project}
            className="flex items-center gap-2.5 rounded-lg bg-[#F8FAFC] border border-[#EEF2F6] px-3 py-2.5"
          >
            <span className="w-5 h-5 rounded-md bg-white border border-[#E5E7EB] flex items-center justify-center text-[8px] font-bold text-[#F97316]">
              {index + 1}
            </span>

            <span className="text-[10px] font-medium text-[#475467]">
              {project}
            </span>
          </div>
        ))}

      </div>
    </section>
  );
}