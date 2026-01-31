import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type Theme = 'light' | 'dark' | 'sunset' | 'ocean' | 'forest' | 'purple' | 'rose'

export const themes: { id: Theme; name: string; color: string }[] = [
  { id: 'light', name: 'Light', color: '#f8fafc' },
  { id: 'dark', name: 'Dark', color: '#0a0a0f' },
  { id: 'sunset', name: 'Sunset', color: '#f97316' },
  { id: 'ocean', name: 'Ocean', color: '#06b6d4' },
  { id: 'forest', name: 'Forest', color: '#10b981' },
  { id: 'purple', name: 'Purple', color: '#a855f7' },
  { id: 'rose', name: 'Rose', color: '#f43f5e' },
]

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const stored = localStorage.getItem('theme') as Theme | null
    if (stored && themes.some(t => t.id === stored)) return stored
    return 'dark' // Default to dark theme
  })

  useEffect(() => {
    const root = window.document.documentElement
    // Remove all theme classes
    themes.forEach(t => root.classList.remove(t.id))
    // Add current theme class
    root.classList.add(theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
