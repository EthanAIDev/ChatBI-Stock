import { create } from 'zustand';

interface AuthState {
  username: string | null;
  role: string | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  login: (username: string, role: string, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  username: localStorage.getItem('username'),
  role: localStorage.getItem('role'),
  accessToken: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  login: (username, role, token) => {
    localStorage.setItem('username', username);
    localStorage.setItem('role', role);
    localStorage.setItem('access_token', token);
    set({ username, role, accessToken: token, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    localStorage.removeItem('access_token');
    set({ username: null, role: null, accessToken: null, isAuthenticated: false });
  },
}));
