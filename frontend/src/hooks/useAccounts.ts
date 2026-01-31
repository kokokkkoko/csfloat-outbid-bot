import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { accountsApi } from '@/lib/api'
import type { CreateAccountData } from '@/types'
import { toast } from 'sonner'

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: accountsApi.getAll,
  })
}

export function useCreateAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateAccountData) => accountsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      toast.success('Account created successfully!')
    },
    onError: (error: Error) => {
      toast.error(`Failed to create account: ${error.message}`)
    },
  })
}

export function useDeleteAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => accountsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      toast.success('Account deleted')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete account: ${error.message}`)
    },
  })
}

export function useTestAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => accountsApi.test(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      if (data.success) {
        toast.success('Connection successful!')
      } else {
        toast.error(`Connection failed: ${data.message}`)
      }
    },
    onError: (error: Error) => {
      toast.error(`Test failed: ${error.message}`)
    },
  })
}

export function useSyncOrders() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => accountsApi.syncOrders(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      toast.success('Orders synced successfully!')
    },
    onError: (error: Error) => {
      toast.error(`Sync failed: ${error.message}`)
    },
  })
}
