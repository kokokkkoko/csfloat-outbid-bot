import { motion } from 'framer-motion'
import { History } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { useHistory } from '@/hooks'

export function HistoryTab() {
  const { data: history, isLoading } = useHistory(50)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Outbid History</h2>
        <p className="text-muted-foreground">
          {history?.length ?? 0} entries
        </p>
      </div>

      <div className="rounded-xl border bg-card">
        {isLoading ? (
          <div className="p-4 space-y-4">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : history?.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No outbid history yet</p>
            <p className="text-sm mt-1">
              History will appear when the bot outbids competitors
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Item</TableHead>
                <TableHead>Old Price</TableHead>
                <TableHead>New Price</TableHead>
                <TableHead>Competitor</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history?.map((h, index) => (
                <motion.tr
                  key={h.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <TableCell className="text-muted-foreground">
                    {new Date(h.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell className="font-medium truncate max-w-[200px]">
                    {h.market_hash_name}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    ${(h.old_price_cents / 100).toFixed(2)}
                  </TableCell>
                  <TableCell className="text-green-500 font-medium">
                    ${(h.new_price_cents / 100).toFixed(2)}
                  </TableCell>
                  <TableCell className="text-red-500">
                    ${(h.competitor_price_cents / 100).toFixed(2)}
                  </TableCell>
                </motion.tr>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}
