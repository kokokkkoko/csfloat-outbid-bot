import { motion, AnimatePresence } from 'framer-motion'
import { X, Package } from 'lucide-react'
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
import { Skeleton } from '@/components/ui/skeleton'
import { useOrders, useDeleteOrder } from '@/hooks'

export function OrdersTab() {
  const { data: orders, isLoading } = useOrders()

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Active Orders</h2>
        <p className="text-muted-foreground">
          {orders?.length ?? 0} orders
        </p>
      </div>

      <div className="rounded-xl border bg-card">
        {isLoading ? (
          <div className="p-4 space-y-4">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : orders?.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <Package className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No active orders</p>
            <p className="text-sm mt-1">Sync your accounts to load orders</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Float Range</TableHead>
                <TableHead>Outbids</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <AnimatePresence>
                {orders?.map((order) => (
                  <OrderRow key={order.id} order={order} />
                ))}
              </AnimatePresence>
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}

function OrderRow({ order }: { order: import('@/types').BuyOrder }) {
  const deleteOrder = useDeleteOrder()

  const floatRange =
    order.order_type === 'advanced'
      ? `${order.float_min?.toFixed(4)} - ${order.float_max?.toFixed(4)}`
      : '-'

  const iconUrl = order.icon_url
    ? `https://community.akamai.steamstatic.com/economy/image/${order.icon_url}`
    : null

  return (
    <motion.tr
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="group"
    >
      <TableCell>
        <div className="flex items-center gap-3">
          {iconUrl ? (
            <img
              src={iconUrl}
              alt=""
              className="w-10 h-10 rounded-lg object-cover"
              loading="lazy"
            />
          ) : (
            <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
              <Package className="h-5 w-5 text-muted-foreground" />
            </div>
          )}
          <span className="font-medium truncate max-w-[200px]">
            {order.market_hash_name}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <span className="font-semibold">
          ${(order.price_cents / 100).toFixed(2)}
        </span>
      </TableCell>
      <TableCell>
        <Badge
          variant={order.order_type === 'advanced' ? 'default' : 'secondary'}
          className={
            order.order_type === 'advanced'
              ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
              : ''
          }
        >
          {order.order_type}
        </Badge>
      </TableCell>
      <TableCell className="text-muted-foreground">{floatRange}</TableCell>
      <TableCell>
        <Badge
          variant={order.outbid_count > 5 ? 'destructive' : 'secondary'}
          className="tabular-nums"
        >
          {order.outbid_count}
        </Badge>
      </TableCell>
      <TableCell>
        <div className="flex justify-end">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => deleteOrder.mutate(order.order_id)}
            disabled={deleteOrder.isPending}
            className="opacity-0 group-hover:opacity-100 transition-opacity"
            title="Cancel order"
          >
            <X className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </TableCell>
    </motion.tr>
  )
}
