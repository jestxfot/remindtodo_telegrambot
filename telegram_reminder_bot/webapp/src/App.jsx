import { useState, useEffect, useCallback } from 'react'
import WebApp from '@twa-dev/sdk'
import './App.css'

// Pages
import TasksPage from './pages/TasksPage'
import RemindersPage from './pages/RemindersPage'
import NotesPage from './pages/NotesPage'
import PasswordsPage from './pages/PasswordsPage'
import CalendarPage from './pages/CalendarPage'
import ArchivePage from './pages/ArchivePage'
import SettingsPage from './pages/SettingsPage'

// Components
import Navigation from './components/Navigation'
import UnlockScreen from './components/UnlockScreen'

function App() {
  const [currentPage, setCurrentPage] = useState('tasks')
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Initialize Telegram Web App
    WebApp.ready()
    WebApp.expand()
    
    // Set theme colors
    const root = document.documentElement
    root.style.setProperty('--tg-bg', WebApp.themeParams.bg_color || '#1a1a2e')
    root.style.setProperty('--tg-text', WebApp.themeParams.text_color || '#ffffff')
    root.style.setProperty('--tg-hint', WebApp.themeParams.hint_color || '#8b8b8b')
    root.style.setProperty('--tg-button', WebApp.themeParams.button_color || '#6366f1')
    root.style.setProperty('--tg-button-text', WebApp.themeParams.button_text_color || '#ffffff')
    root.style.setProperty('--tg-secondary-bg', WebApp.themeParams.secondary_bg_color || '#16213e')
    root.style.setProperty('--tg-section-bg', WebApp.themeParams.section_bg_color || '#1f1f3a')
    root.style.setProperty('--tg-accent', WebApp.themeParams.accent_text_color || '#6366f1')
    root.style.setProperty('--tg-destructive', WebApp.themeParams.destructive_text_color || '#ff4444')
    
    // Get user info
    if (WebApp.initDataUnsafe?.user) {
      setUser(WebApp.initDataUnsafe.user)
    }

    // Check auth status
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      setIsLoading(true)
      const response = await fetch('/api/auth/status', {
        headers: {
          'X-Telegram-Init-Data': WebApp.initData || ''
        }
      })
      
      const data = await response.json()
      setIsAuthenticated(data.authenticated)
      
      if (!data.authenticated && data.has_password) {
        // Need to unlock
        setIsAuthenticated(false)
      } else if (!data.has_password) {
        // New user, need to create password
        setIsAuthenticated(false)
      }
    } catch (err) {
      console.error('Auth check failed:', err)
      setError('Ошибка подключения к серверу')
    } finally {
      setIsLoading(false)
    }
  }

  const handleUnlock = useCallback((success) => {
    if (success) {
      setIsAuthenticated(true)
      WebApp.HapticFeedback.notificationOccurred('success')
    }
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await fetch('/api/auth/lock', {
        method: 'POST',
        headers: {
          'X-Telegram-Init-Data': WebApp.initData || ''
        }
      })
      setIsAuthenticated(false)
      WebApp.HapticFeedback.notificationOccurred('warning')
    } catch (err) {
      console.error('Logout failed:', err)
    }
  }, [])

  const renderPage = () => {
    const pageProps = { user, onLogout: handleLogout }
    
    switch (currentPage) {
      case 'tasks':
        return <TasksPage {...pageProps} />
      case 'reminders':
        return <RemindersPage {...pageProps} />
      case 'notes':
        return <NotesPage {...pageProps} />
      case 'passwords':
        return <PasswordsPage {...pageProps} />
      case 'calendar':
        return <CalendarPage {...pageProps} />
      case 'archive':
        return <ArchivePage {...pageProps} />
      case 'settings':
        return <SettingsPage {...pageProps} />
      default:
        return <TasksPage {...pageProps} />
    }
  }

  if (isLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner"></div>
        <p>Загрузка...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="error-screen">
        <div className="error-icon">⚠️</div>
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>Повторить</button>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <UnlockScreen onUnlock={handleUnlock} user={user} />
  }

  return (
    <div className="app">
      <main className="main-content">
        {renderPage()}
      </main>
      <Navigation 
        currentPage={currentPage} 
        onPageChange={setCurrentPage} 
      />
    </div>
  )
}

export default App
