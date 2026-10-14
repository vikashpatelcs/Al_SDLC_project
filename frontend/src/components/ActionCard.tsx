import React, { useState } from 'react';
import { ActionCardData } from '../api';
import {
  HelpCircle,
  AlertTriangle,
  CheckCircle,
  FileText,
  Check,
  ShieldAlert,
  GitBranch,
  Layers,
  ArrowRight,
  Sparkles
} from 'lucide-react';

interface ActionCardProps {
  card: ActionCardData;
  onActionClick?: (action: string, payload?: any) => void;
}

export const ActionCard: React.FC<ActionCardProps> = ({ card, onActionClick }) => {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [selectedChips, setSelectedChips] = useState<Record<string, string[]>>({});

  const handleAction = (actionName: string, extraPayload?: any) => {
    setSelectedAction(actionName);
    if (onActionClick) {
      const mergedPayload = { ...card.payload, selected_options: selectedChips, ...(extraPayload || {}) };
      onActionClick(actionName, mergedPayload);
    }
  };

  const toggleChip = (groupKey: string, opt: string) => {
    setSelectedChips((prev) => {
      const current = prev[groupKey] || [];
      const updated = current.includes(opt)
        ? current.filter((x) => x !== opt)
        : [...current, opt];
      return { ...prev, [groupKey]: updated };
    });
  };

  const submitOptionsAsMessage = () => {
    const allSelected = Object.entries(selectedChips)
      .flatMap(([_, opts]) => opts)
      .join(', ');
    if (allSelected) {
      handleAction(`[Selected Options: ${allSelected}]`);
    } else {
      handleAction('Assume Standard Defaults');
    }
  };

  const getCardIcon = () => {
    switch (card.card_type) {
      case 'question_group':
        return <HelpCircle className="w-5 h-5 text-white" />;
      case 'issue_summary':
        return <AlertTriangle className="w-5 h-5 text-neutral-300" />;
      case 'approval_request':
        return <ShieldAlert className="w-5 h-5 text-white" />;
      case 'requirement_card':
        return <CheckCircle className="w-5 h-5 text-neutral-200" />;
      case 'sdlc_ranking':
        return <GitBranch className="w-5 h-5 text-white" />;
      default:
        return <FileText className="w-5 h-5 text-neutral-400" />;
    }
  };

  return (
    <div className="my-3.5 p-4 rounded-xl bg-[#0e0e0e] border border-neutral-800 shadow-2xl transition-all duration-200 hover:border-neutral-700">
      <div className="flex items-center gap-2.5 mb-3 border-b border-neutral-800 pb-2.5">
        <div className="p-1 rounded bg-neutral-900 border border-neutral-800">
          {getCardIcon()}
        </div>
        <h4 className="font-semibold text-white text-sm tracking-wide">{card.title}</h4>
      </div>

      {/* Instruction text */}
      {card.payload.instruction && (
        <p className="text-xs text-neutral-300 mb-3 leading-relaxed">
          {card.payload.instruction}
        </p>
      )}

      {/* QUESTION GROUP RENDERING (Slots + Examples + Option Chips) */}
      {card.card_type === 'question_group' && card.payload.groups && Array.isArray(card.payload.groups) && (
        <div className="space-y-3.5 my-2">
          {card.payload.groups.map((grp: any, gIdx: number) => {
            const groupKey = grp.slot_key || `group-${gIdx}`;
            const activeOptions = selectedChips[groupKey] || [];
            return (
              <div key={gIdx} className="p-3 rounded-lg bg-black border border-neutral-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-white">
                    {grp.topic}
                  </span>
                  {grp.example && (
                    <span className="text-[11px] text-neutral-500 font-mono hidden sm:inline">
                      {grp.example}
                    </span>
                  )}
                </div>

                {grp.questions && Array.isArray(grp.questions) && (
                  <ul className="space-y-1">
                    {grp.questions.map((q: string, qIdx: number) => (
                      <li key={qIdx} className="text-xs text-neutral-300 flex items-start gap-1.5">
                        <span className="text-neutral-500 font-mono text-[11px] mt-0.5">•</span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                )}

                {/* Option Chips for Quick One-Click Selection */}
                {grp.options && Array.isArray(grp.options) && (
                  <div className="pt-1.5 flex flex-wrap gap-1.5">
                    {grp.options.map((opt: string, oIdx: number) => {
                      const isChecked = activeOptions.includes(opt);
                      return (
                        <button
                          key={oIdx}
                          type="button"
                          onClick={() => toggleChip(groupKey, opt)}
                          className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-all flex items-center gap-1.5 border ${
                            isChecked
                              ? 'bg-white text-black border-white shadow-sm'
                              : 'bg-neutral-900 text-neutral-300 border-neutral-700 hover:border-neutral-500 hover:text-white'
                          }`}
                        >
                          {isChecked && <Check className="w-3 h-3 text-black" />}
                          {opt}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {/* Quick Submit with Selected Options */}
          <div className="pt-1 flex items-center justify-between">
            <button
              onClick={submitOptionsAsMessage}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-white text-black hover:bg-neutral-200 transition-all flex items-center gap-1.5 shadow-md"
            >
              <Sparkles className="w-3.5 h-3.5 text-black" />
              Submit Answers & Selections
            </button>
            <span className="text-[11px] text-neutral-500">
              Or click "Assume Standard Defaults" below
            </span>
          </div>
        </div>
      )}

      {/* SDLC RANKING CARD RENDERING */}
      {card.card_type === 'sdlc_ranking' && card.payload && (
        <div className="my-2 p-3 rounded-lg bg-black border border-neutral-800 space-y-3">
          <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
            <div>
              <span className="text-xs text-neutral-400 block uppercase tracking-wider font-semibold">
                Chosen Lifecycle
              </span>
              <span className="text-sm font-bold text-white">
                {card.payload.selected_model}
              </span>
            </div>
            {card.payload.confidence_score !== undefined && (
              <span className="px-2.5 py-1 rounded bg-neutral-900 border border-neutral-700 text-xs font-mono font-bold text-white">
                {Math.round(card.payload.confidence_score * 100)}% Match
              </span>
            )}
          </div>

          {/* Rankings bar chart */}
          {card.payload.rankings && Array.isArray(card.payload.rankings) && (
            <div className="space-y-1.5">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-neutral-400 block">
                Ranked Methodologies (MCDA Evaluation)
              </span>
              {card.payload.rankings.slice(0, 4).map((r: any, idx: number) => (
                <div key={idx} className="space-y-0.5">
                  <div className="flex justify-between text-xs text-neutral-300">
                    <span className="font-medium text-white">{r.rank}. {r.model_type}</span>
                    <span className="font-mono text-neutral-400">{r.score_percentage}%</span>
                  </div>
                  <div className="w-full bg-neutral-900 rounded-full h-1.5 border border-neutral-800 overflow-hidden">
                    <div
                      className="bg-white h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(r.score_percentage, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Key Drivers */}
          {card.payload.factors && (
            <div className="pt-2 border-t border-neutral-800 space-y-1">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-neutral-400 block">
                Key Decision Drivers from Requirements
              </span>
              {['regulatory_criticality', 'security_risk', 'requirement_stability'].map((fKey) => {
                const factor = card.payload.factors[fKey];
                if (!factor) return null;
                return (
                  <div key={fKey} className="text-xs text-neutral-300 flex items-start gap-1.5">
                    <span className="text-white font-mono text-[11px]">•</span>
                    <span className="font-medium capitalize text-white">
                      {fKey.replace(/_/g, ' ')} ({factor.score}/5):
                    </span>
                    <span className="text-neutral-400 italic text-[11px] truncate max-w-sm">
                      {factor.evidence_quote}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* DOWNLOAD PDF PAYLOAD RENDERING */}
      {card.card_type === 'download_pdf' && card.payload && (
        <div className="my-2.5 p-3 rounded-lg bg-black border border-neutral-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-white bg-neutral-900 border border-neutral-700 px-2 py-0.5 rounded">
              ISO/IEC/IEEE 29148 Standard
            </span>
            {card.payload.version && (
              <span className="text-xs text-neutral-400 font-mono">v{card.payload.version}.0</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-neutral-300 pt-1">
            {card.payload.total_requirements !== undefined && (
              <div>
                <span className="text-neutral-500 block">Requirements:</span>
                <span className="font-semibold text-white">{card.payload.total_requirements} Active</span>
              </div>
            )}
            {card.payload.traceability_coverage !== undefined && (
              <div>
                <span className="text-neutral-500 block">Traceability:</span>
                <span className="font-semibold text-white">
                  {Math.round(card.payload.traceability_coverage * 100)}% RTM
                </span>
              </div>
            )}
          </div>
          {card.payload.sha256 && (
            <div className="text-[11px] font-mono text-neutral-400 break-all bg-neutral-950 p-1.5 rounded border border-neutral-800">
              <span className="text-neutral-500 select-none">SHA256: </span>
              {card.payload.sha256}
            </div>
          )}
          {card.payload.download_url && (
            <div className="pt-1.5">
              <a
                href={card.payload.download_url}
                target="_blank"
                rel="noreferrer"
                download
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg bg-white text-black hover:bg-neutral-200 transition-all shadow-md"
              >
                <FileText className="w-4 h-4 text-black" />
                Download Complete SRS PDF
              </a>
            </div>
          )}
        </div>
      )}

      {/* REQUIREMENT CARD BREAKDOWN */}
      {card.card_type === 'requirement_card' && card.payload && (
        <div className="my-2 p-2.5 rounded-lg bg-black border border-neutral-800 text-xs">
          <div className="flex justify-between text-neutral-300 font-medium mb-1.5">
            <span>Total Extracted: {card.payload.total_requirements || 0}</span>
            <span>Assumptions: {card.payload.assumptions_recorded || 0}</span>
          </div>
          {card.payload.category_breakdown && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {Object.entries(card.payload.category_breakdown).map(([cat, count]: [string, any]) => (
                <span key={cat} className="px-2 py-0.5 rounded bg-neutral-900 border border-neutral-800 text-neutral-300 text-[11px] font-mono">
                  {cat}: {count}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ACTION BUTTONS */}
      {card.actions && card.actions.length > 0 && (
        <div className="mt-3.5 pt-2.5 border-t border-neutral-800 flex flex-wrap gap-2">
          {card.actions.map((act) => {
            const isSelected = selectedAction === act;
            return (
              <button
                key={act}
                onClick={() => handleAction(act)}
                className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-white text-black border border-white'
                    : 'bg-neutral-900 hover:bg-neutral-800 text-neutral-200 border border-neutral-700 hover:border-neutral-500'
                }`}
              >
                {isSelected && <Check className="w-3.5 h-3.5 text-black" />}
                {act}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
