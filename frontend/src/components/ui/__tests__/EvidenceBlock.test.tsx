import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EvidenceBlock } from '../EvidenceBlock';

describe('EvidenceBlock Component', () => {
  it('renders submitted content and approved source side-by-side with citation metadata', () => {
    render(
      <EvidenceBlock
        quotedContent="Product pricing is $449/month."
        quotedApprovedSource="Standard pricing is $499/month per clinic."
        sourceReference="Pricing Schedule §4.1"
        sourceDocumentName="Brand_Guidelines_2026.pdf"
        ruleOrFactId="fact_001"
        owner="Product Marketing"
        expiryDate="2026-12-31"
      />
    );

    expect(screen.getByText(/Product pricing is \$449\/month\./i)).toBeInTheDocument();
    expect(screen.getByText(/Standard pricing is \$499\/month per clinic\./i)).toBeInTheDocument();
    expect(screen.getByText(/Pricing Schedule §4\.1/i)).toBeInTheDocument();
    expect(screen.getByText(/Brand_Guidelines_2026\.pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/ID: fact_001/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-12-31/i)).toBeInTheDocument();
  });
});
