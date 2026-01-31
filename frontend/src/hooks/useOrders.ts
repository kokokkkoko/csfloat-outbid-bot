import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ordersApi } from '@/lib/api'
import { toast } from 'sonner'

export function useOrders(activeOnly = true) {
  return useQuery({
    queryKey: ['orders', activeOnly],
    queryFn: () => ordersApi.getAll(activeOnly),
  })
}

export function useDeleteOrder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (orderId: string) => ordersApi.delete(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      toast.success('Order cancelled')
    },
    onError: (error: Error) => {
      toast.error(`Failed to cancel order: ${error.message}`)
    },
  })
}
