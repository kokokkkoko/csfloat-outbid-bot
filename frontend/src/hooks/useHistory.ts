import { useQuery } from '@tanstack/react-query'
import { historyApi } from '@/lib/api'

export function useHistory(limit = 50) {
  return useQuery({
    queryKey: ['history', limit],
    queryFn: () => historyApi.getAll(limit),
  })
}
