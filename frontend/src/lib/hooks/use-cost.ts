// frontend/src/lib/hooks/use-cost.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCostSummary() {
  return useQuery({
    queryKey: ["cost", "summary"],
    queryFn: () => api.getCostSummary(),
    refetchInterval: 60_000,
  });
}

export function useDailyCosts(days: number = 30) {
  return useQuery({
    queryKey: ["cost", "daily", days],
    queryFn: () => api.getDailyCosts(days),
    refetchInterval: 300_000,
  });
}

export function useCostByBook() {
  return useQuery({
    queryKey: ["cost", "by-book"],
    queryFn: () => api.getCostByBook(),
    refetchInterval: 300_000,
  });
}

export function useRecentCalls(limit: number = 50) {
  return useQuery({
    queryKey: ["cost", "recent", limit],
    queryFn: () => api.getRecentCalls(limit),
    refetchInterval: 30_000,
  });
}

export function useCostThresholds() {
  return useQuery({
    queryKey: ["cost", "thresholds"],
    queryFn: () => api.getCostThresholds(),
  });
}
