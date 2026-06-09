// frontend/src/lib/stores/auth.ts
import { create } from "zustand";
import { api } from "@/lib/api";

interface AuthState {
  user: { sub: string; scope: string[] } | null;
  tokenInput: string;
  loading: boolean;
  error: string | null;
  setToken: (token: string) => void;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  tokenInput: "",
  loading: false,
  error: null,
  setToken: (token) => set({ tokenInput: token, error: null }),
  login: async () => {
    set({ loading: true, error: null });
    try {
      const { tokenInput } = useAuthStore.getState();
      await api.login(tokenInput);
      await useAuthStore.getState().fetchMe();
      set({ tokenInput: "" });
    } catch (e: any) {
      set({ error: e?.message || "Login failed" });
    } finally {
      set({ loading: false });
    }
  },
  logout: async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    set({ user: null });
  },
  fetchMe: async () => {
    try {
      const user = await api.me();
      set({ user });
    } catch {
      set({ user: null });
    }
  },
}));
