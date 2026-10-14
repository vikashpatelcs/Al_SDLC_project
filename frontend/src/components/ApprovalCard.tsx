import React, { useState } from 'react';
import {
  ShieldAlert,
  CheckCircle,
  XCircle,
  Edit3,
  RefreshCw,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Award,
  UserCheck
} from 'lucide-react';

export interface ApprovalCardData {
  id: string;
  gate_type: string;
  subject_id: string;
  title: string;
  description: string;
  required_role: string;
  status: 'pending' | 'approved' | 'rejected' | 'revised';
  confidence_score?: number;
  evidence_quote?: string;
  rationale?: string;
  citations?: string[];
  sdlc_signoffs?: Record<string, { signed_at: string; comment?: string }>;
}

interface ApprovalCardProps {
  approval: ApprovalCardData;
  onDecision: (
    approvalId: string,
    action: 'accept' | 'reject' | 'edit' | 'regenerate' | 'explain',
    actingRole: string,
    comment?: string,
    modifiedPayload?: string
  ) => Promise<any>;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({ approval, onDecision }) => {
  const [actingRole, setActingRole] = useState<string>(approval.required_role || 'product_owner');
  const [comment, setComment] = useState<string>('');
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editedText, setEditedText] = useState<string>(approval.description);
  const [showExplain, setShowExplain] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleAction = async (action: 'accept' | 'reject' | 'edit' | 'regenerate' | 'explain') => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await onDecision(
        approval.id,
        action,
        actingRole,
        comment,
        action === 'edit' ? editedText : undefined
      );
      if (action === 'edit') {
        setIsEditing(false);
        setFeedback('Saved revision v+1.');
      } else if (action === 'explain') {
        // explain handled locally
      } else {
        setFeedback(`Decision recorded: ${action.toUpperCase()} as ${actingRole}.`);
      }
    } catch (err: any) {
      setFeedback(`Error recording decision: ${err?.message || 'Network error'}`);
    } finally {
      setLoading(false);
    }
  };

  const isSDLC = approval.gate_type === 'sdlc_selection';

  const mandatorySDLCRoles = [
    { key: 'project_manager', label: 'Project Manager' },
    { key: 'software_architect', label: 'Software Architect' },
    { key: 'security_architect', label: 'Security Architect' },
    { key: 'compliance_officer', label: 'Compliance Officer' },
  ];

  return (
    <div className="my-4 p-5 rounded-2xl bg-[#0e0e0e] border border-neutral-800 shadow-xl">
      {/* Header Badge */}
      <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
        <div className="flex items-center gap-2.5">
          <ShieldAlert className="w-5 h-5 text-white" />
          <div>
            <span className="text-[11px] font-mono uppercase tracking-wider text-neutral-300 font-semibold bg-neutral-900 px-2 py-0.5 rounded border border-neutral-700">
              GATE: {approval.gate_type.replace('_', ' ')}
            </span>
            <h4 className="font-semibold text-white text-sm mt-1">{approval.title}</h4>
          </div>
        </div>

        <div className="text-right">
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider ${
              approval.status === 'approved'
                ? 'bg-white text-black font-bold'
                : approval.status === 'rejected'
                ? 'bg-neutral-800 text-neutral-400 border border-neutral-700'
                : 'bg-neutral-900 text-neutral-300 border border-neutral-700'
            }`}
          >
            {approval.status}
          </span>
        </div>
      </div>

      {/* Description / Content Body */}
      <div className="my-3 text-xs text-neutral-300 leading-relaxed bg-black p-3 rounded-lg border border-neutral-800">
        {!isEditing ? (
          <p>{approval.description}</p>
        ) : (
          <div className="space-y-2">
            <label className="text-[11px] text-white font-semibold">Edit Statement (Will create v+1 snapshot):</label>
            <textarea
              className="w-full bg-[#121212] border border-neutral-700 rounded p-2 text-xs text-white focus:outline-none focus:border-white"
              rows={3}
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
            />
          </div>
        )}
      </div>

      {/* SDLC Multi-Role Progress Indicator */}
      {isSDLC && (
        <div className="my-3 p-3 bg-black rounded-lg border border-neutral-800">
          <div className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Award className="w-3.5 h-3.5 text-white" />
            Mandatory 4-Role Sign-Off Progress
          </div>
          <div className="grid grid-cols-2 gap-2">
            {mandatorySDLCRoles.map((r) => {
              const isSigned = !!(approval.sdlc_signoffs && approval.sdlc_signoffs[r.key]);
              return (
                <div
                  key={r.key}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs border ${
                    isSigned
                      ? 'bg-neutral-900 text-white border-neutral-600'
                      : 'bg-black text-neutral-500 border-neutral-850'
                  }`}
                >
                  <UserCheck className={`w-3.5 h-3.5 ${isSigned ? 'text-white' : 'text-neutral-600'}`} />
                  <span className="text-[11px] font-medium">{r.label}</span>
                  {isSigned && <span className="ml-auto text-[10px] text-white font-mono">✓ Signed</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Acting Role & Comment Inputs */}
      <div className="my-3 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div>
          <label className="text-[11px] text-neutral-400 font-medium block mb-1">Acting Role:</label>
          <select
            value={actingRole}
            onChange={(e) => setActingRole(e.target.value)}
            className="w-full bg-[#121212] border border-neutral-800 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-white"
          >
            <option value="product_owner">Product Owner / BA</option>
            <option value="compliance_officer">Compliance & Legal Officer</option>
            <option value="security_architect">Security Lead / CISO</option>
            <option value="software_architect">Principal Software Architect</option>
            <option value="project_manager">Project Manager</option>
            <option value="risk_officer">Risk & Audit Officer</option>
          </select>
        </div>

        <div>
          <label className="text-[11px] text-neutral-400 font-medium block mb-1">Reviewer Note / Justification:</label>
          <input
            type="text"
            placeholder="Optional comment..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="w-full bg-[#121212] border border-neutral-800 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-white"
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-neutral-800">
        <button
          onClick={() => handleAction('accept')}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-neutral-200 text-black rounded-lg text-xs font-semibold shadow transition-all duration-150 disabled:opacity-50"
        >
          <CheckCircle className="w-3.5 h-3.5" />
          Accept
        </button>

        <button
          onClick={() => handleAction('reject')}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-neutral-300 hover:text-white rounded-lg text-xs font-semibold border border-neutral-700 transition-all duration-150 disabled:opacity-50"
        >
          <XCircle className="w-3.5 h-3.5" />
          Reject
        </button>

        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-neutral-200 rounded-lg text-xs font-semibold border border-neutral-700 transition-all duration-150 disabled:opacity-50"
          >
            <Edit3 className="w-3.5 h-3.5" />
            Edit
          </button>
        ) : (
          <button
            onClick={() => handleAction('edit')}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-black hover:bg-neutral-200 rounded-lg text-xs font-semibold shadow transition-all duration-150 disabled:opacity-50"
          >
            Save Edit (v+1)
          </button>
        )}

        <button
          onClick={() => handleAction('regenerate')}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-neutral-300 rounded-lg text-xs font-medium border border-neutral-700 transition-all duration-150 disabled:opacity-50"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Regenerate
        </button>

        <button
          onClick={() => {
            setShowExplain(!showExplain);
            if (!showExplain) handleAction('explain');
          }}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-black hover:bg-neutral-900 text-neutral-300 rounded-lg text-xs font-medium border border-neutral-700 transition-all duration-150 ml-auto"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          Explain
          {showExplain ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {/* Feedback Alert */}
      {feedback && (
        <div className="mt-2.5 p-2 rounded bg-neutral-900 border border-neutral-700 text-[11px] text-neutral-200">
          {feedback}
        </div>
      )}

      {/* Expandable Explain Drawer */}
      {showExplain && (
        <div className="mt-3 p-3.5 bg-black rounded-xl border border-neutral-800 space-y-2 text-xs">
          <div className="flex items-center justify-between text-white font-semibold border-b border-neutral-800 pb-1.5">
            <span>Decision Rationale & Regulatory Grounding</span>
            <span className="font-mono text-[11px] text-neutral-400">
              Confidence: {Math.round((approval.confidence_score || 1.0) * 100)}%
            </span>
          </div>

          <p className="text-neutral-300">
            <span className="text-white font-semibold">Engineering Rationale: </span>
            {approval.rationale || 'Derived from verified requirement constraints and statutory compliance rules.'}
          </p>

          {approval.evidence_quote && (
            <blockquote className="border-l-2 border-white pl-2.5 py-1 text-neutral-300 italic bg-neutral-950 rounded-r">
              "{approval.evidence_quote}"
            </blockquote>
          )}

          {approval.citations && approval.citations.length > 0 && (
            <div>
              <span className="text-[11px] font-semibold text-white block mb-1">Statutory Citations:</span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] text-neutral-300">
                {approval.citations.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
