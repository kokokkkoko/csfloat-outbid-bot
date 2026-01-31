import { motion, useSpring, useTransform } from 'framer-motion'
import { useEffect } from 'react'

interface AnimatedCounterProps {
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
}

export function AnimatedCounter({
  value,
  prefix = '',
  suffix = '',
  decimals = 0,
}: AnimatedCounterProps) {
  const spring = useSpring(0, {
    stiffness: 100,
    damping: 30,
    mass: 1,
  })

  const display = useTransform(spring, (v) =>
    decimals > 0 ? v.toFixed(decimals) : Math.round(v).toString()
  )

  useEffect(() => {
    spring.set(value)
  }, [value, spring])

  return (
    <span>
      {prefix}
      <motion.span>{display}</motion.span>
      {suffix}
    </span>
  )
}
