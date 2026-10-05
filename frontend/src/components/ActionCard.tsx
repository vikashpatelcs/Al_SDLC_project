import React, { useState } from 'react';
import { ActionCardData } from '../api';
import { HelpCircle, AlertTriangle, CheckCircle, RefreshCw, FileText, ChevronRight, Check, X, ShieldAlert } from 'lucide-react';

interface ActionCardProps {
  card: ActionCardData;
  onActionClick?: (action: string, payload?: any) => void;
}

export const ActionCard: React.FC<ActionCardProps> = ({ card, onActionClick }) => {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);

  const handleAction = (actionName: string) => {
    setSelectedAction(actionName);
    if (onActionClick) {
      onActionClick(actionName, card.payload);
    }
  };

  const getCardIcon = () => {
    switch (card.card_type) {
      case 'question_group':
        return <HelpCircle className="w-5 h-5 text-sky-400" />;
      case 'issue_summary':
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case 'approval_request':
        return <ShieldAlert className="w-5 h-5 text-purple-400" />;
      case 'requirement_card':
        return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      default:
        return <FileText className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="my-3 p-4 rounded-xl glass-panel card-glow transition-all duration-200">
      <div className="flex items-center gap-2.5 mb-2.5 border-b border-slate-800 pb-2">
        {getCardIcon()}
        <h4 className="font-semibold text-slate-100 text-sm tracking-wide">{card.title}</h4>
      </div>

      {/* Payload Content rendering */}
      {card.payload.topic && (
        <div className="mb-2">
          <span className="text-xs uppercase tracking-wider font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
            {card.payload.topic}
          </span>
        </div>
      )}

      {card.payload.questions && Array.isArray(card.payload.questions) && (
        <ul className="space-y-1.5 my-2.5">
          {card.payload.questions.map((q: string, idx: number) => (
            <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
              <span className="text-sky-400 font-mono text-[11px] mt-0.5">{idx + 1}.</span>
              <span>{q}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Action Buttons */}
      {card.actions && card.actions.length > 0 && (
        <div className="mt-3.5 pt-2.5 border-t border-slate-800/80 flex flex-wrap gap-2">
          {card.actions.map((act) => {
            const isSelected = selectedAction === act;
            return (
              <button
                key={act}
                onClick={() => handleAction(act)}
                className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/50'
                    : 'bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 border border-slate-700/60 hover:border-slate-600'
                }`}
              >
                {isSelected && <Check className="w-3.5 h-3.5 text-sky-400" />}
                {act}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
