import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Save, Clock, DollarSign, TrendingUp, Percent } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSettings, useUpdateSettings } from '@/hooks'

export function SettingsTab() {
  const { data: settings, isLoading } = useSettings()
  const updateSettings = useUpdateSettings()

  const [formData, setFormData] = useState({
    check_interval: 600,
    outbid_step: 1,
    max_outbids: 10,
    price_ceiling_percent: 85,
  })

  useEffect(() => {
    if (settings) {
      setFormData({
        check_interval: settings.check_interval,
        outbid_step: settings.outbid_step,
        max_outbids: settings.max_outbids,
        price_ceiling_percent: settings.price_ceiling_percent,
      })
    }
  }, [settings])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateSettings.mutate(formData)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <h2 className="text-xl font-semibold">Bot Settings</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Bot Settings Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-blue-500" />
              Bot Configuration
            </CardTitle>
            <CardDescription>
              Configure how the bot checks and outbids competitors
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="check_interval" className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Check Interval (seconds)
              </Label>
              <Input
                id="check_interval"
                type="number"
                min={60}
                max={3600}
                value={formData.check_interval}
                onChange={(e) =>
                  setFormData({ ...formData, check_interval: parseInt(e.target.value) || 600 })
                }
              />
              <p className="text-xs text-muted-foreground">
                How often to check for competing orders (min: 60s)
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="outbid_step" className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Outbid Step (cents)
              </Label>
              <Input
                id="outbid_step"
                type="number"
                min={1}
                max={100}
                value={formData.outbid_step}
                onChange={(e) =>
                  setFormData({ ...formData, outbid_step: parseInt(e.target.value) || 1 })
                }
              />
              <p className="text-xs text-muted-foreground">
                Amount to outbid competitors by
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max_outbids" className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Max Outbids per Order
              </Label>
              <Input
                id="max_outbids"
                type="number"
                min={1}
                max={100}
                value={formData.max_outbids}
                onChange={(e) =>
                  setFormData({ ...formData, max_outbids: parseInt(e.target.value) || 10 })
                }
              />
              <p className="text-xs text-muted-foreground">
                Stop outbidding after this many times
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="price_ceiling" className="flex items-center gap-2">
                <Percent className="h-4 w-4" />
                Price Ceiling (%)
              </Label>
              <Input
                id="price_ceiling"
                type="number"
                min={50}
                max={99}
                value={formData.price_ceiling_percent}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    price_ceiling_percent: parseInt(e.target.value) || 85,
                  })
                }
              />
              <p className="text-xs text-muted-foreground">
                Max % of lowest listing price to pay
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="bg-blue-500/5 border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-blue-600 dark:text-blue-400">
              Recommended Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>
              <strong>Check Interval:</strong> 600+ seconds (10 min) to avoid rate
              limiting
            </p>
            <p>
              <strong>Outbid Step:</strong> 1 cent for minimal cost increase
            </p>
            <p>
              <strong>Max Outbids:</strong> 10 to prevent overspending on competitive
              items
            </p>
            <p>
              <strong>Price Ceiling:</strong> 85% ensures you never pay more than the
              listing price
            </p>
          </CardContent>
        </Card>

        <Button
          type="submit"
          className="w-full sm:w-auto gap-2"
          disabled={updateSettings.isPending}
        >
          <Save className="h-4 w-4" />
          {updateSettings.isPending ? 'Saving...' : 'Save Settings'}
        </Button>
      </form>
    </motion.div>
  )
}
