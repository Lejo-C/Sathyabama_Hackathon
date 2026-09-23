import React from 'react';
import ExecutiveSummary from './ExecutiveSummary';
import FinancialSnapshot from './FinancialSnapshot';
import CompanyOverview from './CompanyOverview';
import ProductsServices from './ProductsServices';
import CompanyDesk from './CompanyDesk';
import Projects from './Projects';
import People from './People';

const demoResearch = {
  company: {
    name: 'TechNova Solutions',
    website: 'technova.example.com',
    industry: 'Software & SaaS',
    founded: '2018',
    headquarters: 'Chennai, India',
    type: 'Private',
    employees: '200–500',
  },

  executiveSummary:
    'TechNova Solutions is a software and SaaS company focused on cloud infrastructure, enterprise automation, and data-driven business solutions. The company has expanded its product portfolio across multiple enterprise technology areas.',

  financials: {
    revenue: '₹120 Cr',
    funding: '₹35 Cr',
    valuation: 'Not disclosed',
    growth: '+18%',
  },

  history: [
    {
      year: '2018',
      event: 'Company founded',
    },
    {
      year: '2020',
      event: 'Expanded into enterprise cloud solutions',
    },
    {
      year: '2023',
      event: 'Launched automation platform',
    },
  ],

  products: [
    {
      name: 'Cloud Infrastructure',
      description: 'Cloud management and infrastructure solutions for businesses.',
    },
    {
      name: 'Workflow Automation',
      description: 'Tools designed to automate repetitive enterprise workflows.',
    },
    {
      name: 'Data Analytics',
      description: 'Business analytics and reporting solutions.',
    },
  ],

  projects: [
    'Enterprise Cloud Migration',
    'Automation Platform',
    'Business Intelligence Suite',
  ],

  people: [
    {
      name: 'Arun Kumar',
      role: 'Chief Executive Officer',
    },
    {
      name: 'Rahul Menon',
      role: 'Chief Technology Officer',
    },
    {
      name: 'Priya Nair',
      role: 'Head of Product',
    },
  ],
};

export default function Research({ data = demoResearch }) {
  return (
    <section className="space-y-4">

      {/* Page heading */}
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#171A1F]">
          Company Research
        </h2>

        <p className="text-[11px] text-[#667085] mt-1">
          Research gathered from available company information and public sources.
        </p>
      </div>

      {/* Executive Summary */}
      <ExecutiveSummary
        company={data.company}
        summary={data.executiveSummary}
      />

      {/* Financial Snapshot */}
      <FinancialSnapshot financials={data.financials} />

      {/* Research details */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <CompanyOverview
          company={data.company}
          history={data.history}
        />

        <ProductsServices products={data.products} />

        <CompanyDesk company={data.company} />

        <Projects projects={data.projects} />

        <People people={data.people} />
      </div>

    </section>
  );
}