import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, RefreshCw, Trash2, CheckCircle, Wifi } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useTestAccount,
  useSyncOrders,
} from '@/hooks'
import type { CreateAccountData } from '@/types'

export function AccountsTab() {
  const { data: accounts, isLoading } = useAccounts()
  const [isAddOpen, setIsAddOpen] = useState(false)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">CSFloat Accounts</h2>
        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Add Account
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add CSFloat Account</DialogTitle>
            </DialogHeader>
            <AddAccountForm onSuccess={() => setIsAddOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-xl border bg-card">
        {isLoading ? (
          <div className="p-4 space-y-4">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : accounts?.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No accounts yet. Add your first CSFloat account to get started.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Proxy</TableHead>
                <TableHead>Last Check</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <AnimatePresence>
                {accounts?.map((account) => (
                  <AccountRow key={account.id} account={account} />
                ))}
              </AnimatePresence>
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}

function AccountRow({ account }: { account: import('@/types').Account }) {
  const deleteAccount = useDeleteAccount()
  const testAccount = useTestAccount()
  const syncOrders = useSyncOrders()

  const statusColors = {
    online: 'bg-green-500',
    error: 'bg-red-500',
    idle: 'bg-gray-400',
  }

  return (
    <motion.tr
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="group"
    >
      <TableCell>
        <div className="flex items-center gap-2">
          <span className="font-medium">{account.name}</span>
          {!account.is_active && (
            <Badge variant="secondary" className="text-xs">
              Inactive
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${statusColors[account.status]}`}
          />
          <span className="capitalize">{account.status}</span>
        </div>
        {account.error_message && (
          <p className="text-xs text-destructive mt-1 truncate max-w-[200px]">
            {account.error_message}
          </p>
        )}
      </TableCell>
      <TableCell>
        {account.proxy ? (
          <Badge variant="outline" className="gap-1">
            <Wifi className="h-3 w-3" />
            Configured
          </Badge>
        ) : (
          <span className="text-muted-foreground">None</span>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {account.last_check
          ? new Date(account.last_check).toLocaleString()
          : 'Never'}
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => testAccount.mutate(account.id)}
            disabled={testAccount.isPending}
            title="Test connection"
          >
            <CheckCircle className="h-4 w-4 text-blue-500" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => syncOrders.mutate(account.id)}
            disabled={syncOrders.isPending}
            title="Sync orders"
          >
            <RefreshCw className="h-4 w-4 text-purple-500" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => deleteAccount.mutate(account.id)}
            disabled={deleteAccount.isPending}
            title="Delete"
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </TableCell>
    </motion.tr>
  )
}

function AddAccountForm({ onSuccess }: { onSuccess: () => void }) {
  const createAccount = useCreateAccount()
  const [formData, setFormData] = useState<CreateAccountData>({
    name: '',
    api_key: '',
    proxy: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await createAccount.mutateAsync(formData)
    onSuccess()
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Account Name</Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="My CSFloat Account"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="api_key">API Key</Label>
        <Input
          id="api_key"
          type="password"
          value={formData.api_key}
          onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
          placeholder="Your CSFloat API key"
          required
        />
        <p className="text-xs text-muted-foreground">
          Get your API key from CSFloat settings
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="proxy">Proxy (optional)</Label>
        <Input
          id="proxy"
          value={formData.proxy}
          onChange={(e) => setFormData({ ...formData, proxy: e.target.value })}
          placeholder="socks5://user:pass@host:port"
        />
      </div>

      <Button
        type="submit"
        className="w-full"
        disabled={createAccount.isPending}
      >
        {createAccount.isPending ? 'Creating...' : 'Add Account'}
      </Button>
    </form>
  )
}
