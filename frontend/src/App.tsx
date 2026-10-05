import React, { useState, useEffect } from 'react';
import {
  ChatSession,
  MessageData,
  ActionCardData,
  fetchChats,
  createChat,
  renameChat,
  deleteChat,
  fetchMessages,
  uploadFile,
  sendMessageStream,
} from './api';
import { Sidebar } from './components/Sidebar';
import { ChatView } from './components/ChatView';
import { MessageInput } from './components/MessageInput';
import { ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageData[]>([]);

  // Streaming State
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [streamingCards, setStreamingCards] = useState<ActionCardData[]>([]);
  const [statusLine, setStatusLine] = useState<string | undefined>(undefined);

  // Load chats on initial mount
  useEffect(() => {
    loadChats();
  }, []);

  // Load messages when active chat changes
  useEffect(() => {
    if (activeChatId) {
      loadMessages(activeChatId);
    } else {
      setMessages([]);
    }
  }, [activeChatId]);

  const loadChats = async () => {
    try {
      const data = await fetchChats();
      setChats(data);
      if (data.length > 0 && !activeChatId) {
        setActiveChatId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load chats:', err);
    }
  };

  const loadMessages = async (chatId: string) => {
    try {
      const msgs = await fetchMessages(chatId);
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to load messages for chat:', chatId, err);
    }
  };

  const handleNewChat = async () => {
    try {
      const newChat = await createChat('New Financial Requirement');
      setChats((prev) => [newChat, ...prev]);
      setActiveChatId(newChat.id);
    } catch (err) {
      console.error('Failed to create new chat:', err);
    }
  };

  const handleRenameChat = async (id: string, newTitle: string) => {
    try {
      const updated = await renameChat(id, newTitle);
      setChats((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err) {
      console.error('Failed to rename chat:', err);
    }
  };

  const handleDeleteChat = async (id: string) => {
    try {
      await deleteChat(id);
      setChats((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (activeChatId === id) {
          setActiveChatId(next.length > 0 ? next[0].id : null);
        }
        return next;
      });
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
  };

  const handleSendMessage = async (text: string) => {
    let currentId = activeChatId;
    if (!currentId) {
      try {
        const newChat = await createChat(text.slice(0, 30));
        currentId = newChat.id;
        setChats((prev) => [newChat, ...prev]);
        setActiveChatId(newChat.id);
      } catch (err) {
        console.error('Error auto-creating chat:', err);
        return;
      }
    }

    if (!currentId) return;
    const finalChatId: string = currentId;

    // Optimistically append user message
    const tempUserMsg: MessageData = {
      id: `temp-${Date.now()}`,
      chat_id: finalChatId,
      role: 'user',
      sender_agent: 'stakeholder',
      content_masked: text,
      action_cards: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    // Start SSE stream
    setIsStreaming(true);
    setStreamingText('');
    setStreamingCards([]);
    setStatusLine('Coordinating requirement agents...');

    await sendMessageStream(finalChatId, text, {
      onToken: (token) => {
        setStreamingText((prev) => prev + token);
      },
      onActionCards: (cards) => {
        setStreamingCards(cards);
      },
      onDone: async () => {
        setIsStreaming(false);
        setStreamingText('');
        setStreamingCards([]);
        setStatusLine(undefined);
        await loadMessages(finalChatId);
        await loadChats();
      },
      onError: (err) => {
        console.error('Stream error:', err);
        setIsStreaming(false);
        setStatusLine('Error connecting to assistant stream.');
      },
    });
  };

  const handleUploadFile = async (file: File) => {
    if (!activeChatId) return;
    try {
      setStatusLine(`Uploading ${file.name}...`);
      await uploadFile(activeChatId, file);
      setStatusLine(undefined);
    } catch (err) {
      console.error('File upload failed:', err);
      setStatusLine('Failed to upload file.');
    }
  };

  const handleActionClick = (action: string, payload?: any) => {
    handleSendMessage(`[Action Selected: ${action}]`);
  };

  return (
    <div className="flex h-screen bg-[#090d16] text-slate-100 overflow-hidden font-sans">
      {/* Sidebar with Chat History */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={handleNewChat}
        onRenameChat={handleRenameChat}
        onDeleteChat={handleDeleteChat}
      />

      {/* Main Chat Interface */}
      <main className="flex-1 flex flex-col h-screen relative bg-gradient-to-b from-slate-950/80 via-slate-950 to-slate-900">
        {/* Top Header Bar */}
        <header className="h-14 border-b border-slate-800/80 px-6 flex items-center justify-between glass-panel z-10">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-200">
              {chats.find((c) => c.id === activeChatId)?.title || 'Financial Requirement System'}
            </h2>
            <span className="text-[10px] bg-slate-800/80 text-sky-400 font-mono px-2 py-0.5 rounded border border-slate-700/60">
              {chats.find((c) => c.id === activeChatId)?.state || 'INTAKE'}
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Phase 2 Verified</span>
          </div>
        </header>

        {/* Message Feed */}
        <ChatView
          messages={messages}
          streamingText={streamingText}
          streamingCards={streamingCards}
          isStreaming={isStreaming}
          statusLine={statusLine}
          onActionClick={handleActionClick}
        />

        {/* Bottom Message Input */}
        <MessageInput
          onSendMessage={handleSendMessage}
          onUploadFile={handleUploadFile}
          disabled={isStreaming}
        />
      </main>
    </div>
  );
};
