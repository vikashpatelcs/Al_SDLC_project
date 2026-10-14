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
    <div className="flex-1 overflow-y-auto px-4 py-6 bg-black">
      <div className="max-w-4xl mx-auto space-y-6">
        {messages.map((m) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={m.id}
              className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser && (
                <div className="w-8 h-8 rounded-xl bg-[#141414] border border-neutral-800 flex items-center justify-center shrink-0 shadow-md mt-1">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}

              <div
                className={`group relative max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  isUser
                    ? 'bg-white text-black font-medium rounded-br-sm shadow-md'
                    : 'bg-[#0c0c0c] text-neutral-100 rounded-bl-sm border border-neutral-800 shadow-md'
                }`}
              >
                {/* Header for assistant message indicating specialized agent */}
                {!isUser && m.sender_agent && (
                  <div className="mb-1 text-[11px] font-mono text-neutral-400 font-semibold uppercase tracking-wider flex items-center gap-1.5 border-b border-neutral-800/80 pb-1">
                    <Sparkles className="w-3 h-3 text-white" />
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
                  className="absolute -bottom-5 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 text-neutral-500 hover:text-white rounded text-xs flex items-center gap-1"
                  title="Copy message"
                >
                  {copiedId === m.id ? (
                    <Check className="w-3 h-3 text-white" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>

              {isUser && (
                <div className="w-8 h-8 rounded-xl bg-white text-black flex items-center justify-center shrink-0 shadow-md mt-1">
                  <User className="w-4 h-4 text-black" />
                </div>
              )}
            </div>
          );
        })}

        {/* Live SSE Streaming Assistant Message */}
        {isStreaming && (
          <div className="flex gap-3.5 justify-start">
            <div className="w-8 h-8 rounded-xl bg-[#141414] border border-neutral-800 flex items-center justify-center shrink-0 shadow-md mt-1">
              <Bot className="w-4 h-4 text-white" />
            </div>

            <div className="max-w-2xl px-4 py-3 rounded-2xl rounded-bl-sm bg-[#0c0c0c] text-neutral-100 border border-neutral-800 text-sm leading-relaxed shadow-md">
              <div className="mb-1 text-[11px] font-mono text-neutral-400 font-semibold uppercase tracking-wider flex items-center gap-1.5 border-b border-neutral-800 pb-1">
                <Sparkles className="w-3 h-3 text-white animate-spin" />
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
          <div className="flex items-center justify-center gap-2 py-2 text-xs font-mono text-neutral-400 animate-pulse">
            <div className="w-1.5 h-1.5 rounded-full bg-white" />
            {statusLine}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
};
