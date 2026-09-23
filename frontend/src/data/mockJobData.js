// Sample job posting text for high risk scam demonstration
export const SAMPLE_HIGH_RISK_JOB = `URGENT REQUIREMENT: Junior Data Entry & Back Office Assistant (Work From Home)

Company: Apex Global Innovators Inc.
Location: Remote (Pan India)
Stipend: ₹85,000 per month + Laptop Allowance
Experience Required: 0 - 10 years (No prior technical background needed, freshers welcome!)

About the Role:
We are looking for immediate joiners for our fast-growing international operations team. The selected candidates will perform simple online document data entry, assist executive management with back-office duties, and execute daily web tasks. High earning potential for just 2 hours of daily work!

Requirements:
- Minimum 10 years experience in Quantum AI & Enterprise Blockchain architecture (or 10th pass fresher).
- Must have basic laptop or smartphone with internet connection.
- High accuracy in typing simple words.

Selection & Joining Process:
Due to high candidate volume, candidates selected for the final interview slot must deposit a refundable registration and security processing fee of ₹1,500 via UPI before onboarding documents are processed. This fee is 100% refundable with your first stipend payment!

URGENT: Only 3 positions remaining! Offer closes strictly in 2 hours. Send your resume and payment screenshot immediately to HR manager via WhatsApp at +91-9876543210 or email jobsoffers2026.apex@gmail.com. Do not reply to this job portal listing.`;

export const MOCK_ANALYSIS_RESULT = {
  score: 74,
  level: 'HIGH RISK',
  levelColor: 'bg-red-50 text-red-700 border-red-200',
  summary: {
    keyThreat: 'Mandatory upfront registration fee combined with artificial urgency and personal communication channels.',
    recommendation: 'DO NOT APPLY or pay any money. High confidence of fraudulent stipend/registration scam.',
    flagsCount: {
      critical: 2,
      high: 3,
      medium: 1,
      low: 1
    },
    metadata: {
      companyStatus: 'Unverified Entity',
      domainAge: 'Newly Registered (14 days)',
      contactType: 'Personal Gmail & WhatsApp',
      reportedIncidents: '3 similar listings flagged in last 48h'
    }
  },
  contributors: [
    { id: 'upfront', title: 'Upfront Payment Required', percentage: 35, color: '#EF4444' },
    { id: 'salary', title: 'Unrealistic Salary / Stipend', percentage: 22, color: '#F97316' },
    { id: 'contact', title: 'Suspicious Contact Details', percentage: 18, color: '#F97316' },
    { id: 'urgency', title: 'Artificial Urgency Tactics', percentage: 12, color: '#F59E0B' },
    { id: 'company', title: 'Unverified Corporate Identity', percentage: 8, color: '#F59E0B' },
    { id: 'description', title: 'Vague Role Responsibilities', percentage: 3, color: '#6B7280' },
    { id: 'requirements', title: 'Contradictory Requirements', percentage: 2, color: '#6B7280' }
  ],
  riskFactors: [
    {
      id: 'upfront_payment',
      title: 'Upfront Payment',
      category: 'Financial Fraud',
      severity: 'CRITICAL',
      severityColor: 'bg-red-100 text-red-800 border-red-300',
      badgeColor: 'bg-red-600',
      flagged: true,
      evidence: 'Selected candidates must deposit a refundable registration and security processing fee of ₹1,500 via UPI before onboarding documents are processed.',
      explanation: 'Legitimate employers never demand registration, processing, uniform, or security deposit fees from job candidates before or during hiring.'
    },
    {
      id: 'unrealistic_salary',
      title: 'Unrealistic Salary/Stipend',
      category: 'Compensation Mismatch',
      severity: 'CRITICAL',
      severityColor: 'bg-red-100 text-red-800 border-red-300',
      badgeColor: 'bg-red-600',
      flagged: true,
      evidence: 'Stipend: ₹85,000 per month + Laptop Allowance... High earning potential for just 2 hours of daily work!',
      explanation: 'Offering ₹85,000/month for 2 hours of basic data entry work far exceeds market compensation standard (avg ₹8k-15k) and is a primary bait metric.'
    },
    {
      id: 'urgency_language',
      title: 'Urgency Language',
      category: 'Coercive Tactics',
      severity: 'HIGH',
      severityColor: 'bg-orange-100 text-orange-800 border-orange-300',
      badgeColor: 'bg-orange-500',
      flagged: true,
      evidence: 'URGENT: Only 3 positions remaining! Offer closes strictly in 2 hours.',
      explanation: 'Imposing tight artificial deadlines creates panic and pressure, discouraging candidates from independently verifying company credentials.'
    },
    {
      id: 'suspicious_contact',
      title: 'Suspicious Contact Information',
      category: 'Identity Verification',
      severity: 'HIGH',
      severityColor: 'bg-orange-100 text-orange-800 border-orange-300',
      badgeColor: 'bg-orange-500',
      flagged: true,
      evidence: 'Send your resume and payment screenshot immediately to HR manager via WhatsApp at +91-9876543210 or email jobsoffers2026.apex@gmail.com.',
      explanation: 'Using public @gmail.com domains and personal WhatsApp numbers rather than verifiable corporate emails (@apexglobal.com) indicates unvetted recruiters.'
    },
    {
      id: 'missing_company',
      title: 'Missing/Suspicious Company Information',
      category: 'Corporate Legitimacy',
      severity: 'HIGH',
      severityColor: 'bg-orange-100 text-orange-800 border-orange-300',
      badgeColor: 'bg-orange-500',
      flagged: true,
      evidence: 'Company: Apex Global Innovators Inc. (No registration number, physical address, CIN, or official web domain provided).',
      explanation: 'Missing corporate registration details, physical address, and domain information prevents independent registry checks (MCA / ROC).'
    },
    {
      id: 'unrealistic_requirements',
      title: 'Unrealistic Requirements',
      category: 'Job Specification',
      severity: 'MEDIUM',
      severityColor: 'bg-amber-100 text-amber-800 border-amber-300',
      badgeColor: 'bg-amber-500',
      flagged: true,
      evidence: 'Requires 10 years experience in Quantum AI & Enterprise Blockchain architecture for a 0-10 years fresher entry-level role.',
      explanation: 'Contradictory and absurd technical skill requirements mixed with "no experience needed" indicate a copy-pasted or auto-generated job template.'
    },
    {
      id: 'vague_description',
      title: 'Vague Job Description',
      category: 'Scope Clarity',
      severity: 'LOW',
      severityColor: 'bg-gray-100 text-gray-800 border-gray-300',
      badgeColor: 'bg-gray-500',
      flagged: true,
      evidence: 'Perform simple online document data entry, assist executive management with back-office duties, and execute daily web tasks.',
      explanation: 'Overly generic descriptions without defined deliverables or department alignment are structured to attract maximum applicants without clear scope.'
    }
  ]
};
