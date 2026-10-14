import React, { useState } from 'react';
import { ChatSession } from '../api';
import { Plus, MessageSquare, Search, Trash2, Edit2, Check, X, Shield, ChevronLeft, ChevronRight } from 'lucide-react';

interface SidebarProps {
  chats: ChatSession[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onRenameChat: (id: string, newTitle: string) => void;
  onDeleteChat: (id: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onRenameChat,
  onDeleteChat,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [collapsed, setCollapsed] = useState(false);

  const filteredChats = chats.filter((c) =>
    c.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const categorizeChatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 3600 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return 'Previous 30 Days';
  };

  const groupedChats: { [group: string]: ChatSession[] } = {
    Today: [],
    Yesterday: [],
    'Previous 30 Days': [],
  };

  filteredChats.forEach((c) => {
    const group = categorizeChatDate(c.updated_at || c.created_at);
    if (!groupedChats[group]) groupedChats[group] = [];
    groupedChats[group].push(c);
  });

  const startEditing = (c: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingChatId(c.id);
    setEditTitle(c.title);
  };

  const saveEditing = (id: string, e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameChat(id, editTitle.trim());
    }
    setEditingChatId(null);
  };

  const cancelEditing = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingChatId(null);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this requirement project?')) {
      onDeleteChat(id);
    }
  };

  if (collapsed) {
    return (
      <div className="w-16 h-screen bg-[#0a0a0a] border-r border-neutral-800 flex flex-col items-center py-4 justify-between transition-all duration-200 z-20">
        <div className="flex flex-col items-center gap-4">
          <button
            onClick={() => setCollapsed(false)}
            className="p-2 hover:bg-neutral-800 rounded-lg text-neutral-400 hover:text-white"
            title="Expand Sidebar"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          <button
            onClick={onNewChat}
            className="p-2.5 bg-white text-black hover:bg-neutral-200 rounded-xl shadow-lg transition-transform active:scale-95"
            title="New Financial Project"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
        <div className="text-neutral-500">
          <Shield className="w-5 h-5" />
        </div>
      </div>
    );
  }

  return (
    <aside className="w-72 h-screen bg-[#0a0a0a] border-r border-neutral-800 flex flex-col transition-all duration-200 z-20 select-none">
      {/* Brand & New Chat */}
      <div className="p-4 border-b border-neutral-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center shadow-md">
              <Shield className="w-4 h-4 text-black" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-white">FinReq AI</h1>
              <span className="text-[10px] text-neutral-400 font-mono tracking-wider uppercase font-semibold">Requirement Engineer</span>
            </div>
          </div>
          <button
            onClick={() => setCollapsed(true)}
            className="p-1.5 hover:bg-neutral-800 rounded-lg text-neutral-400 hover:text-white"
            title="Collapse Sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>

        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-white hover:bg-neutral-200 text-black rounded-xl text-xs font-semibold shadow-md transition-all active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          New Requirement Chat
        </button>

        {/* Search */}
        <div className="mt-3 relative">
          <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search projects..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#121212] border border-neutral-800 text-neutral-200 text-xs rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:border-white transition-colors"
          />
        </div>
      </div>

      {/* Chat History Groupings */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        {Object.entries(groupedChats).map(([groupTitle, chatItems]) => {
          if (chatItems.length === 0) return null;
          return (
            <div key={groupTitle}>
              <div className="px-2 mb-1.5 text-[10px] font-semibold text-neutral-500 tracking-wider uppercase">
                {groupTitle}
              </div>
              <div className="space-y-1">
                {chatItems.map((c) => {
                  const isActive = c.id === activeChatId;
                  const isEditing = c.id === editingChatId;

                  if (isEditing) {
                    return (
                      <div key={c.id} className="p-1.5 bg-neutral-900 rounded-lg flex items-center gap-1.5 border border-white">
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="flex-1 bg-black text-xs px-2 py-1 rounded text-white focus:outline-none"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveEditing(c.id, e);
                            if (e.key === 'Escape') setEditingChatId(null);
                          }}
                        />
                        <button onClick={(e) => saveEditing(c.id, e)} className="text-white hover:text-neutral-300 p-1">
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={cancelEditing} className="text-neutral-400 hover:text-white p-1">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={c.id}
                      onClick={() => onSelectChat(c.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-xs transition-all ${
                        isActive
                          ? 'bg-neutral-900 text-white font-medium border border-neutral-700 shadow-sm'
                          : 'text-neutral-400 hover:bg-neutral-900/60 hover:text-white'
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate pr-6">
                        <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-white' : 'text-neutral-500'}`} />
                        <span className="truncate">{c.title}</span>
                      </div>

                      {/* Hover action icons: Rename & Delete */}
                      <div className="hidden group-hover:flex items-center gap-1 absolute right-2 bg-neutral-900 px-1 py-0.5 rounded shadow border border-neutral-800">
                        <button
                          onClick={(e) => startEditing(c, e)}
                          className="p-1 text-neutral-400 hover:text-white rounded"
                          title="Rename"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                        <button
                          onClick={(e) => handleDelete(c.id, e)}
                          className="p-1 text-neutral-400 hover:text-white rounded"
                          title="Delete"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {filteredChats.length === 0 && (
          <div className="text-center py-8 text-xs text-neutral-600">
            No projects found
          </div>
        )}
      </div>

      {/* Footer Info (Offline Guardrail Notice) */}
      <div className="p-3 border-t border-neutral-800 bg-black">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
          <span className="text-[11px] text-neutral-400 font-mono">Offline Local Inference</span>
        </div>
      </div>
    </aside>
  );
};
