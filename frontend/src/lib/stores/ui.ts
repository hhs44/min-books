// frontend/src/lib/stores/ui.ts
import { create } from "zustand";

interface UIState {
  sidebarCollapsed: boolean;
  locale: string;
  toggleSidebar: () => void;
  setLocale: (locale: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  locale: process.env.NEXT_PUBLIC_DEFAULT_LOCALE || "zh",
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setLocale: (locale) => set({ locale }),
}));
