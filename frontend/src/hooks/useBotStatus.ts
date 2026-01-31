import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { botApi } from '@/lib/api'
import { toast } from 'sonner'

export function useBotStatus() {
  return useQuery({
    queryKey: ['botStatus'],
    queryFn: botApi.getStatus,
    refetchInterval: 5000, // Poll every 5 seconds
  })
}

export function useStartBot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: botApi.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['botStatus'] })
      toast.success('Bot started successfully!')
    },
    onError: (error: Error) => {
      toast.error(`Failed to start bot: ${error.message}`)
    },
  })
}

export function useStopBot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: botApi.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['botStatus'] })
      toast.success('Bot stopped')
    },
    onError: (error: Error) => {
      toast.error(`Failed to stop bot: ${error.message}`)
    },
  })
}
