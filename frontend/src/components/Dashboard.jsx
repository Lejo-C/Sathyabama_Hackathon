import React, { useState } from 'react';
import Sidebar from './Sidebar';
import JobInput from './JobInput';
import RiskOverview from './RiskOverview';
import { SAMPLE_HIGH_RISK_JOB, MOCK_ANALYSIS_RESULT } from '../data/mockJobData';
import { ShieldCheck, Sparkles, Bell, Settings } from 'lucide-react';
import RiskScore from './RiskScore';
import Research from './research/Research';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('job-analysis');
  const [jobText, setJobText] = useState(SAMPLE_HIGH_RISK_JOB);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(MOCK_ANALYSIS_RESULT);

  const handleAnalyze = () => {
    if (!jobText.trim()) return;

    setIsAnalyzing(true);

    setTimeout(() => {
      setIsAnalyzing(false);
      setAnalysisResult(MOCK_ANALYSIS_RESULT);
    }, 700);
  };

  const handleUseSample = () => {
    setJobText(SAMPLE_HIGH_RISK_JOB);
    setIsAnalyzing(true);

    setTimeout(() => {
      setIsAnalyzing(false);
      setAnalysisResult(MOCK_ANALYSIS_RESULT);
    }, 600);
  };

  const handleClear = () => {
    setJobText('');
    setAnalysisResult(null);
  };

  return (
    <div className="min-h-screen bg-[#F5F6F8] font-sans antialiased text-[#171A1F] p-4 md:p-6">

      {/* Top Navigation */}
      <header className="h-[68px] rounded-2xl border border-[#E5E7EB] bg-white px-5 md:px-6 flex items-center justify-between shadow-sm">

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#FFF4E8] flex items-center justify-center">
            <ShieldCheck className="w-[18px] h-[18px] text-[#F97316]" />
          </div>

          <div className="text-[15px] font-bold tracking-tight text-[#171A1F]">
            JobShield
          </div>
        </div>

        <div className="flex items-center gap-2">

          <button
            type="button"
            aria-label="Notifications"
            className="w-9 h-9 rounded-lg border border-transparent hover:border-[#E5E7EB] hover:bg-[#F8FAFC] flex items-center justify-center text-[#667085] transition-colors cursor-pointer"
          >
            <Bell className="w-[17px] h-[17px]" />
          </button>

          <button
            type="button"
            aria-label="Settings"
            className="w-9 h-9 rounded-lg border border-transparent hover:border-[#E5E7EB] hover:bg-[#F8FAFC] flex items-center justify-center text-[#667085] transition-colors cursor-pointer"
          >
            <Settings className="w-[17px] h-[17px]" />
          </button>

        </div>
      </header>

      {/* Sidebar + Main Content */}
      <div className="flex items-start gap-5 mt-4">

        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />

        <main className="flex-1 p-6 md:p-8 space-y-6 w-full min-w-0">

          <div className="space-y-5">

            {/* =====================================================
                JOB ANALYSIS
                ===================================================== */}
            {activeTab === 'job-analysis' && (
              <>

                {/* Job Input + Risk Score */}
                <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-5 items-stretch">

                  {/* Job Input */}
                  <div className="min-w-0">
                    <JobInput
                      jobText={jobText}
                      setJobText={setJobText}
                      onAnalyze={handleAnalyze}
                      onUseSample={handleUseSample}
                      onClear={handleClear}
                      isAnalyzing={isAnalyzing}
                    />
                  </div>

                  {/* Overall Risk Score */}
                  {analysisResult && (
                    <div className="min-w-0">
                      <RiskScore
                        score={analysisResult.score}
                        level={analysisResult.level}
                        levelColor={analysisResult.levelColor}
                        summary={analysisResult.summary}
                      />
                    </div>
                  )}

                </div>

                {/* =================================================
                    ANALYSIS + RESEARCH
                    ================================================= */}
                {analysisResult && !isAnalyzing && (
                  <div className="space-y-6 animate-in fade-in duration-300">

                    {/* Existing Risk Analysis */}
                    <RiskOverview result={analysisResult} />

                    {/* Company Research */}
                    <Research
                      data={analysisResult?.research}
                    />

                  </div>
                )}

                {/* =================================================
                    ANALYZING STATE
                    ================================================= */}
                {isAnalyzing && (
                  <div className="bg-white rounded-2xl border border-[#E5E7EB] p-12 text-center shadow-sm">

                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[#FFF7ED] text-[#F97316] mb-4 animate-bounce">
                      <Sparkles className="w-6 h-6" />
                    </div>

                    <h3 className="text-sm font-bold text-[#171A1F]">
                      Evaluating Job Signals
                    </h3>

                    <p className="text-xs text-[#667085] mt-1">
                      Analyzing text across 7 risk modules: Upfront fees, Salary anomaly, Urgency, Contact verification...
                    </p>

                  </div>
                )}

              </>
            )}

            {/* =====================================================
                OVERVIEW
                ===================================================== */}
            {activeTab === 'overview' && (
              <div className="bg-white rounded-2xl border border-[#E5E7EB] p-8 shadow-sm">

                <h2 className="text-base font-bold text-[#171A1F]">
                  Risk Overview
                </h2>

                <p className="text-sm text-[#667085] mt-1">
                  Your job analysis overview will appear here as the dashboard grows.
                </p>

              </div>
            )}

          </div>

        </main>
      </div>
    </div>
  );
}
