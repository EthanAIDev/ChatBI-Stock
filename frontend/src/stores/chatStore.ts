import { create } from 'zustand';
import type { ChatSession, ChatMessage } from '../types';

interface ChatState {
  sessions: ChatSession[];
  messages: ChatMessage[];
  activeSessionId: string | null;
  loading: boolean;
  completedSessions: Set<string>;
  setSessions: (sessions: ChatSession[]) => void;
  setMessages: (messages: ChatMessage[]) => void;
  setActiveSession: (sessionId: string | null) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: number, updates: Partial<ChatMessage>) => void;
  refreshMessageRender: (id: number) => void;
  setLoading: (loading: boolean) => void;
  markSessionCompleted: (sessionId: string) => void;
  clearSessionCompleted: (sessionId: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  messages: [],
  activeSessionId: null,
  loading: false,
  completedSessions: new Set<string>(),
  setSessions: (sessions) => set({ sessions }),
  setMessages: (messages) => set({ messages }),
  setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map((m) => (m.id === id ? { ...m, ...updates } : m)),
  })),
  refreshMessageRender: (id) => set((state) => ({
    messages: state.messages.map((m) => (m.id === id ? { ...m, render_key: Date.now() } : m)),
  })),
  setLoading: (loading) => set({ loading }),
  markSessionCompleted: (sessionId) => set((state) => {
    const next = new Set(state.completedSessions);
    next.add(sessionId);
    return { completedSessions: next };
  }),
  clearSessionCompleted: (sessionId) => set((state) => {
    const next = new Set(state.completedSessions);
    next.delete(sessionId);
    return { completedSessions: next };
  }),
}));
