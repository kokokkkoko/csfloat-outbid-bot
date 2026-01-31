import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '@/lib/api'
import type { BotSettings } from '@/types'
import { toast } from 'sonner'

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (settings: Partial<BotSettings>) => settingsApi.update(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['botStatus'] })
      toast.success('Settings saved!')
    },
    onError: (error: Error) => {
      toast.error(`Failed to save settings: ${error.message}`)
    },
  })
}
