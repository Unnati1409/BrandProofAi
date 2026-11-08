import React from 'react';
import { BookOpen, FileText } from 'lucide-react';

export interface EvidenceBlockProps {
  quotedContent: string;
  quotedApprovedSource: string;
  sourceReference: string;
  sourceDocumentName?: string;
  ruleOrFactId?: string;
  owner?: string;
  expiryDate?: string;
  className?: string;
}

export const EvidenceBlock: React.FC<EvidenceBlockProps> = ({
  quotedContent,
  quotedApprovedSource,
  sourceReference,
  sourceDocumentName,
  ruleOrFactId,
  owner,
  expiryDate,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col gap-3 p-3 bg-surface-50 border border-surface-200 rounded text-xs ${className}`}
    >
      {/* Submitted Content Excerpt */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-wider text-surface-500">
          <FileText className="h-3 w-3" aria-hidden="true" />
          <span>Flagged Submission Text</span>
        </div>
        <blockquote className="p-2 bg-white border border-surface-200 rounded font-mono text-xs text-surface-900 whitespace-pre-wrap">
          &ldquo;{quotedContent}&rdquo;
        </blockquote>
      </div>

      {/* Approved Knowledge Base Reference */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-2xs text-surface-500">
          <div className="flex items-center gap-1.5 font-semibold uppercase tracking-wider text-surface-700">
            <BookOpen className="h-3 w-3 text-brand-600" aria-hidden="true" />
            <span>Approved Source Citation</span>
          </div>
          {ruleOrFactId && (
            <span className="font-mono text-surface-500">
              ID: {ruleOrFactId}
            </span>
          )}
        </div>
        <blockquote className="p-2 bg-emerald-50/50 border border-emerald-200/80 rounded font-mono text-xs text-emerald-950 whitespace-pre-wrap">
          &ldquo;{quotedApprovedSource}&rdquo;
        </blockquote>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-surface-500 mt-0.5">
          <span>
            <strong>Ref:</strong> {sourceReference}
          </span>
          {sourceDocumentName && (
            <span>
              <strong>Doc:</strong> {sourceDocumentName}
            </span>
          )}
          {owner && (
            <span>
              <strong>Owner:</strong> {owner}
            </span>
          )}
          {expiryDate && (
            <span className="text-amber-800 font-medium">
              <strong>Expires:</strong> {expiryDate}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
