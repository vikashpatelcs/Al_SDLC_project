/**
 * Frontend API client with credentials: "include" for anonymous session isolation.
 */

export interface ChatSession {
  id: string;
  title: string;
  state: string;
  created_at: string;
  updated_at: string;
}

export interface ActionCardData {
  id: string;
  card_type: string;
  title: string;
  payload: Record<string, any>;
  actions: string[];
}

export interface MessageData {
  id: string;
  chat_id: string;
  role: 'user' | 'assistant' | 'system';
  sender_agent?: string;
  content_masked: string;
  action_cards: ActionCardData[];
  created_at: string;
}

const BASE_URL = '/api';

export async function fetchChats(): Promise<ChatSession[]> {
  const res = await fetch(`${BASE_URL}/chats`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to fetch chats');
  return res.json();
}

export async function createChat(title?: string): Promise<ChatSession> {
  const res = await fetch(`${BASE_URL}/chats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ title: title || 'New Financial Requirement' }),
  });
  if (!res.ok) throw new Error('Failed to create chat');
  return res.json();
}

export async function renameChat(chatId: string, title: string): Promise<ChatSession> {
  const res = await fetch(`${BASE_URL}/chats/${chatId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to rename chat');
  return res.json();
}

export async function deleteChat(chatId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/chats/${chatId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to delete chat');
}

export async function fetchMessages(chatId: string): Promise<MessageData[]> {
  const res = await fetch(`${BASE_URL}/chats/${chatId}/messages`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to fetch messages');
  return res.json();
}

export async function uploadFile(chatId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE_URL}/chats/${chatId}/upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload file');
  return res.json();
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onActionCards: (cards: ActionCardData[]) => void;
  onDone: (messageId: string) => void;
  onError: (error: Error) => void;
}

export async function sendMessageStream(
  chatId: string,
  content: string,
  callbacks: StreamCallbacks
): Promise<void> {
  try {
    const res = await fetch(`${BASE_URL}/chats/${chatId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ content }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to send message`);
    if (!res.body) throw new Error('No readable stream response');

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        if (!rawEvent.trim()) continue;
        const lines = rawEvent.split('\n');
        let eventType = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.replace('event: ', '').trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.replace('data: ', '').trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (eventType === 'token' && parsed.token) {
            callbacks.onToken(parsed.token);
          } else if (eventType === 'action_cards' && parsed.action_cards) {
            callbacks.onActionCards(parsed.action_cards);
          } else if (eventType === 'done') {
            callbacks.onDone(parsed.message_id);
          }
        } catch (e) {
          console.warn('Failed to parse SSE JSON payload:', dataStr);
        }
      }
    }
  } catch (err: any) {
    callbacks.onError(err);
  }
}
