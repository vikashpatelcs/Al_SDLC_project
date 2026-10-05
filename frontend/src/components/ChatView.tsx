import React, { useRef, useEffect } from 'react';
import { MessageData } from '../api';
import { ActionCard } from './ActionCard';
import { Bot, User, Copy, Check, Sparkles } from 'lucide-react';

interface ChatViewProps {
  messages: MessageData[];
  streamingText: string;
  streamingCards: any[];
  isStreaming: boolean;
  statusLine?: string;
  onActionClick?: (action: string, payload?: any) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  streamingText,
  streamingCards,
  isStreaming,
  statusLine,
  onActionClick,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, streamingCards]);

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {messages.map((m) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={m.id}
              className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-700 flex items-center justify-center shrink-0 shadow-md shadow-sky-950 mt-1">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}

              <div
                className={`group relative max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  isUser
                    ? 'bg-sky-600 text-white rounded-br-sm shadow-md shadow-sky-950'
                    : 'glass-panel text-slate-100 rounded-bl-sm border border-slate-800'
                }`}
              >
                {/* Header for assistant message indicating specialized agent */}
                {!isUser && m.sender_agent && (
                  <div className="mb-1 text-[11px] font-mono text-sky-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-sky-400" />
                    {m.sender_agent}
                  </div>
                )}

                <div className="whitespace-pre-wrap">{m.content_masked}</div>

                {/* Inline Action Cards */}
                {m.action_cards && m.action_cards.length > 0 && (
                  <div className="mt-3">
                    {m.action_cards.map((card) => (
                      <ActionCard key={card.id} card={card} onActionClick={onActionClick} />
                    ))}
                  </div>
                )}

                {/* Copy button */}
                <button
                  onClick={() => copyToClipboard(m.id, m.content_masked)}
                  className={`absolute -bottom-5 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 text-slate-400 hover:text-slate-200 rounded text-xs flex items-center gap-1`}
                  title="Copy message"
                >
                  {copiedId === m.id ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>

              {isUser && (
                <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 shadow-md mt-1">
                  <User className="w-4 h-4 text-slate-300" />
                </div>
              )}
            </div>
          );
        })}

        {/* Live SSE Streaming Assistant Message */}
        {isStreaming && (
          <div className="flex gap-3.5 justify-start">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-700 flex items-center justify-center shrink-0 shadow-md shadow-sky-950 mt-1">
              <Bot className="w-4 h-4 text-white" />
            </div>

            <div className="max-w-2xl px-4 py-3 rounded-2xl rounded-bl-sm glass-panel text-slate-100 border border-slate-800 text-sm leading-relaxed">
              <div className="mb-1 text-[11px] font-mono text-sky-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-sky-400 animate-spin" />
                Coordinator
              </div>
              <div className="whitespace-pre-wrap">
                {streamingText}
                <span className="cursor-blink" />
              </div>

              {streamingCards.length > 0 && (
                <div className="mt-3">
                  {streamingCards.map((card) => (
                    <ActionCard key={card.id} card={card} onActionClick={onActionClick} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Subtle status line indicator */}
        {statusLine && (
          <div className="flex items-center justify-center gap-2 py-2 text-xs font-mono text-slate-400 animate-pulse">
            <div className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            {statusLine}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
};
