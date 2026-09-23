import React, { useRef, useState } from 'react';
import {
  Sparkles,
  Trash2,
  ArrowRight,
  Loader2,
  FileText,
  Link2,
  Image as ImageIcon,
  Upload,
  X,
} from 'lucide-react';

const inputModes = [
  {
    id: 'text',
    label: 'Job Text',
    icon: FileText,
  },
  {
    id: 'url',
    label: 'Job URL',
    icon: Link2,
  },
  {
    id: 'image',
    label: 'Screenshot',
    icon: ImageIcon,
  },
];

export default function JobInput({
  jobText,
  setJobText,
  onAnalyze,
  onUseSample,
  onClear,
  isAnalyzing,
}) {
  const [activeMode, setActiveMode] = useState('text');
  const [jobUrl, setJobUrl] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  const fileInputRef = useRef(null);

  const handleModeChange = (mode) => {
    if (isAnalyzing) return;
    setActiveMode(mode);
  };

  const handleImageSelect = (file) => {
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      return;
    }

    setImageFile(file);

    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);
  };

  const handleFileInput = (event) => {
    const file = event.target.files?.[0];

    if (file) {
      handleImageSelect(file);
    }

    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();

    if (isAnalyzing) return;

    const file = event.dataTransfer.files?.[0];

    if (file) {
      handleImageSelect(file);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const removeImage = () => {
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
    }

    setImageFile(null);
    setImagePreview(null);
  };

  const handleClear = () => {
    if (activeMode === 'text') {
      setJobText('');
    }

    if (activeMode === 'url') {
      setJobUrl('');
    }

    if (activeMode === 'image') {
      removeImage();
    }

    onClear?.();
  };

  const getInputValue = () => {
    if (activeMode === 'text') {
      return jobText;
    }

    if (activeMode === 'url') {
      return jobUrl;
    }

    return imageFile;
  };

  const hasInput = Boolean(getInputValue());

  const handleAnalyze = () => {
    if (!hasInput || isAnalyzing) return;

    onAnalyze?.({
      type: activeMode,
      value:
        activeMode === 'image'
          ? imageFile
          : activeMode === 'url'
            ? jobUrl.trim()
            : jobText.trim(),
    });
  };

  const getWordCount = () => {
    if (!jobText.trim()) return 0;
    return jobText.trim().split(/\s+/).length;
  };

  return (
    <div className="bg-white rounded-xl border border-[#E5E7EB] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 sm:px-6 pt-5 sm:pt-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h2 className="text-base sm:text-lg font-semibold text-[#171A1F] flex items-center gap-2">
              <FileText className="w-5 h-5 text-[#F97316]" />
              Analyze Job Posting
            </h2>

            <p className="text-xs sm:text-sm text-[#667085] mt-1 leading-relaxed">
              Paste a job, enter its URL, or upload a screenshot to check for
              suspicious signals.
            </p>
          </div>

          {/* Sample Job */}
          {activeMode === 'text' && (
            <button
              onClick={onUseSample}
              disabled={isAnalyzing}
              className="inline-flex items-center justify-center gap-1.5 text-xs font-semibold text-[#F97316] hover:text-[#EA580C] bg-[#FFF7ED] hover:bg-[#FFEDD5] border border-[#FFEDD5] px-3 py-2 rounded-md transition-colors disabled:opacity-50 cursor-pointer whitespace-nowrap"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Use Sample
            </button>
          )}
        </div>

        {/* Input Tabs */}
        <div className="mt-5 border-b border-[#E5E7EB]">
          <div className="flex items-center gap-1 overflow-x-auto">
            {inputModes.map((mode) => {
              const Icon = mode.icon;
              const isActive = activeMode === mode.id;

              return (
                <button
                  key={mode.id}
                  onClick={() => handleModeChange(mode.id)}
                  disabled={isAnalyzing}
                  className={`
                    relative flex items-center justify-center gap-2
                    px-3 sm:px-4 py-3
                    text-xs sm:text-sm font-medium
                    whitespace-nowrap
                    transition-colors
                    disabled:opacity-50
                    cursor-pointer
                    ${
                      isActive
                        ? 'text-[#F97316]'
                        : 'text-[#667085] hover:text-[#171A1F]'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span>{mode.label}</span>

                  {isActive && (
                    <span className="absolute bottom-[-1px] left-0 right-0 h-0.5 bg-[#F97316]" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="px-5 sm:px-6 py-5">
        {/* TEXT MODE */}
        {activeMode === 'text' && (
          <div className="relative">
            <textarea
              rows={3}
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
              disabled={isAnalyzing}
              placeholder="Paste the complete job or internship posting here..."
              className="
                w-full
                min-h-[140px]
                bg-[#F8FAFC]
                border border-[#E5E7EB]
                rounded-lg
                p-4
                pb-10
                text-sm
                text-[#171A1F]
                placeholder-[#94A3B8]
                focus:outline-none
                focus:ring-1
                focus:ring-[#F97316]
                focus:border-[#F97316]
                transition-colors
                resize-y
                disabled:opacity-60
              "
            />

            <div className="absolute bottom-3 right-3 text-[10px] text-[#94A3B8] bg-white px-2 py-1 rounded border border-[#E5E7EB]">
              {getWordCount()} words
            </div>
          </div>
        )}

        {/* URL MODE */}
        {activeMode === 'url' && (
          <div className="min-h-[190px] flex items-center justify-center">
            <div className="w-full max-w-2xl">
              <div className="text-center mb-5">
                <div className="mx-auto w-11 h-11 rounded-lg bg-[#FFF7ED] flex items-center justify-center mb-3">
                  <Link2 className="w-5 h-5 text-[#F97316]" />
                </div>

                <h3 className="text-sm font-semibold text-[#171A1F]">
                  Analyze a job URL
                </h3>

                <p className="text-xs text-[#667085] mt-1">
                  Paste the public job listing URL below.
                </p>
              </div>

              <div className="relative">
                <Link2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />

                <input
                  type="url"
                  value={jobUrl}
                  onChange={(e) => setJobUrl(e.target.value)}
                  disabled={isAnalyzing}
                  placeholder="https://example.com/jobs/software-engineer-intern"
                  className="
                    w-full
                    bg-[#F8FAFC]
                    border border-[#E5E7EB]
                    rounded-lg
                    pl-10
                    pr-4
                    py-3.5
                    text-sm
                    text-[#171A1F]
                    placeholder-[#94A3B8]
                    focus:outline-none
                    focus:ring-1
                    focus:ring-[#F97316]
                    focus:border-[#F97316]
                    transition-colors
                    disabled:opacity-60
                  "
                />
              </div>

              <p className="text-[11px] text-[#98A2B3] mt-2">
                Example: LinkedIn, Indeed, Internshala, company careers page
              </p>
            </div>
          </div>
        )}

        {/* IMAGE MODE */}
        {activeMode === 'image' && (
          <div className="min-h-[190px]">
            {!imagePreview ? (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                disabled={isAnalyzing}
                className="
                  w-full
                  min-h-[190px]
                  bg-[#F8FAFC]
                  border
                  border-dashed
                  border-[#D0D5DD]
                  hover:border-[#F97316]
                  hover:bg-[#FFFDFC]
                  rounded-lg
                  flex
                  flex-col
                  items-center
                  justify-center
                  transition-colors
                  cursor-pointer
                  disabled:opacity-50
                  disabled:cursor-not-allowed
                "
              >
                <div className="w-11 h-11 rounded-lg bg-[#FFF7ED] flex items-center justify-center mb-3">
                  <Upload className="w-5 h-5 text-[#F97316]" />
                </div>

                <p className="text-sm font-semibold text-[#171A1F]">
                  Upload job screenshot
                </p>

                <p className="text-xs text-[#667085] mt-1">
                  Drag and drop or click to browse
                </p>

                <p className="text-[11px] text-[#98A2B3] mt-2">
                  PNG, JPG or WEBP
                </p>
              </button>
            ) : (
              <div className="relative bg-[#F8FAFC] border border-[#E5E7EB] rounded-lg overflow-hidden">
                <img
                  src={imagePreview}
                  alt="Uploaded job posting"
                  className="w-full max-h-[320px] object-contain bg-[#F8FAFC]"
                />

                <button
                  type="button"
                  onClick={removeImage}
                  disabled={isAnalyzing}
                  className="
                    absolute
                    top-3
                    right-3
                    w-8
                    h-8
                    rounded-md
                    bg-white
                    border
                    border-[#E5E7EB]
                    text-[#667085]
                    hover:text-red-600
                    hover:border-red-200
                    flex
                    items-center
                    justify-center
                    shadow-sm
                    transition-colors
                    cursor-pointer
                  "
                  title="Remove image"
                >
                  <X className="w-4 h-4" />
                </button>

                <div className="px-3 py-2.5 border-t border-[#E5E7EB] bg-white flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <ImageIcon className="w-4 h-4 text-[#F97316] shrink-0" />

                    <span className="text-xs text-[#667085] truncate">
                      {imageFile?.name}
                    </span>
                  </div>

                  <span className="text-[10px] text-[#98A2B3] shrink-0 ml-3">
                    {imageFile
                      ? `${(imageFile.size / 1024 / 1024).toFixed(2)} MB`
                      : ''}
                  </span>
                </div>
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={handleFileInput}
              className="hidden"
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 sm:px-6 py-3.5 border-t border-[#F1F5F9] flex items-center justify-between gap-3">
        <button
          onClick={handleClear}
          disabled={!hasInput || isAnalyzing}
          className="
            flex
            items-center
            gap-1.5
            text-xs
            font-medium
            text-[#667085]
            hover:text-red-600
            disabled:opacity-40
            transition-colors
            cursor-pointer
            disabled:cursor-not-allowed
          "
        >
          <Trash2 className="w-4 h-4" />
          <span>Clear</span>
        </button>

        <button
          onClick={handleAnalyze}
          disabled={!hasInput || isAnalyzing}
          className="
            inline-flex
            items-center
            justify-center
            gap-2
            bg-[#F97316]
            hover:bg-[#EA580C]
            text-white
            text-xs
            sm:text-sm
            font-semibold
            px-5
            py-2.5
            rounded-md
            shadow-sm
            transition-colors
            cursor-pointer
            disabled:opacity-50
            disabled:cursor-not-allowed
            whitespace-nowrap
          "
        >
          {isAnalyzing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <span>Analyze Job</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}