import React, { useState, useRef } from 'react';
import { Send, Paperclip, File, X, Loader2 } from 'lucide-react';

interface MessageInputProps {
  onSendMessage: (text: string) => void;
  onUploadFile: (file: File) => Promise<void>;
  disabled?: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  onUploadFile,
  disabled = false,
}) => {
  const [content, setContent] = useState('');
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (disabled || isUploading) return;

    if (attachedFile) {
      setIsUploading(true);
      try {
        await onUploadFile(attachedFile);
        setAttachedFile(null);
      } catch (err) {
        console.error('File upload error:', err);
      } finally {
        setIsUploading(false);
      }
    }

    if (content.trim()) {
      onSendMessage(content.trim());
      setContent('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setAttachedFile(e.target.files[0]);
    }
  };

  const adjustTextareaHeight = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-4">
      {/* Attached file chip preview */}
      {attachedFile && (
        <div className="mb-2 flex items-center gap-2 bg-slate-800/80 border border-slate-700/60 px-3 py-1.5 rounded-lg w-fit text-xs text-slate-200">
          <File className="w-3.5 h-3.5 text-sky-400" />
          <span className="truncate max-w-xs">{attachedFile.name}</span>
          <span className="text-slate-400 font-mono text-[10px]">({(attachedFile.size / 1024).toFixed(1)} KB)</span>
          <button
            onClick={() => setAttachedFile(null)}
            className="text-slate-400 hover:text-rose-400 ml-1"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main input container */}
      <form
        onSubmit={handleSubmit}
        className="glass-panel rounded-2xl p-2 flex items-end gap-2 border border-slate-700/60 focus-within:border-sky-500/50 shadow-2xl transition-all"
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          accept=".txt,.pdf,.docx,.json,.csv,.eml"
        />

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || isUploading}
          className="p-2.5 text-slate-400 hover:text-sky-400 hover:bg-slate-800/60 rounded-xl transition-colors disabled:opacity-50"
          title="Upload specification, transcript, or policy document"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <textarea
          ref={textareaRef}
          value={content}
          onChange={adjustTextareaHeight}
          onKeyDown={handleKeyDown}
          placeholder="Describe your financial requirement, answering questions, or paste specifications..."
          rows={1}
          disabled={disabled}
          className="flex-1 bg-transparent border-0 text-slate-100 placeholder:text-slate-500 text-sm focus:outline-none resize-none py-2 px-1 max-h-44 leading-relaxed"
        />

        <button
          type="submit"
          disabled={disabled || (!content.trim() && !attachedFile) || isUploading}
          className="p-2.5 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 disabled:opacity-30 disabled:hover:from-sky-500 disabled:hover:to-indigo-600 text-white rounded-xl shadow-md transition-all active:scale-95"
          title="Send message"
        >
          {isUploading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </form>

      <div className="text-center mt-2">
        <span className="text-[11px] text-slate-500 font-mono">
          Strict Offline Guardrails • PII Masked • Verified Regulatory Citations Only
        </span>
      </div>
    </div>
  );
};
