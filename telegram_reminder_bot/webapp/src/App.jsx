import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import Calendar from './components/Calendar'
import './App.css'

function App() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [user, setUser] = useState(null)

  useEffect(() => {
    // Initialize Telegram Web App
    WebApp.ready()
    WebApp.expand()
    
    // Set theme
    document.documentElement.style.setProperty('--tg-theme-bg-color', WebApp.themeParams.bg_color || '#1a1a2e')
    document.documentElement.style.setProperty('--tg-theme-text-color', WebApp.themeParams.text_color || '#ffffff')
    document.documentElement.style.setProperty('--tg-theme-hint-color', WebApp.themeParams.hint_color || '#8b8b8b')
    document.documentElement.style.setProperty('--tg-theme-button-color', WebApp.themeParams.button_color || '#6366f1')
    document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', WebApp.themeParams.secondary_bg_color || '#16213e')
    
    // Get user info
    if (WebApp.initDataUnsafe?.user) {
      setUser(WebApp.initDataUnsafe.user)
    }

    // Load events
    loadEvents()
  }, [])

  const loadEvents = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const initData = WebApp.initData
      
      // Try to fetch from API (same origin)
      try {
        const response = await fetch('/api/events', {
          headers: {
            'X-Telegram-Init-Data': initData || ''
          }
        })
        
        const data = await response.json()
        
        if (response.ok && data.events && data.events.length > 0) {
          setEvents(data.events)
          return
        }
        
        // If storage is locked, show message
        if (response.status === 403 && data.message) {
          setError(data.message)
          setEvents([])
          return
        }
      } catch (fetchErr) {
        console.error('API fetch error:', fetchErr)
      }
      
      // If no events from API and not in Telegram, use mock data for demo
      if (!initData) {
        console.log('No Telegram init data, using mock events for demo')
        setEvents(getMockEvents())
      } else {
        // In Telegram but no events - show empty
        setEvents([])
      }
      
    } catch (err) {
      console.error('Error loading events:', err)
      setError(err.message)
      setEvents([])
    } finally {
      setLoading(false)
    }
  }

  const getMockEvents = () => {
    const today = new Date()
    const events = []
    
    // Generate some sample events
    for (let i = -5; i < 15; i++) {
      const date = new Date(today)
      date.setDate(date.getDate() + i)
      
      if (Math.random() > 0.5) {
        events.push({
          id: `reminder-${i}`,
          type: 'reminder',
          title: ['Встреча', 'Звонок', 'Совещание', 'Врач', 'Оплата'][Math.floor(Math.random() * 5)],
          date: date.toISOString(),
          time: `${9 + Math.floor(Math.random() * 10)}:00`,
          isRecurring: Math.random() > 0.7
        })
      }
      
      if (Math.random() > 0.6) {
        events.push({
          id: `todo-${i}`,
          type: 'todo',
          title: ['Купить продукты', 'Отправить отчёт', 'Проект', 'Задача'][Math.floor(Math.random() * 4)],
          date: date.toISOString(),
          priority: ['low', 'medium', 'high', 'urgent'][Math.floor(Math.random() * 4)],
          completed: Math.random() > 0.8
        })
      }
    }
    
    return events
  }

  const handleEventClick = (event) => {
    // Show event details
    WebApp.showPopup({
      title: event.type === 'reminder' ? '🔔 Напоминание' : '📋 Задача',
      message: `${event.title}\n${event.time || ''}\n${event.isRecurring ? '🔄 Повторяющееся' : ''}`,
      buttons: [
        { id: 'view', type: 'default', text: 'Открыть в боте' },
        { id: 'close', type: 'cancel', text: 'Закрыть' }
      ]
    }, (buttonId) => {
      if (buttonId === 'view') {
        // Send data back to bot
        WebApp.sendData(JSON.stringify({ action: 'view', event }))
      }
    })
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Загрузка календаря...</p>
      </div>
    )
  }

  return (
    <div className="app">
      <Calendar 
        events={events} 
        onEventClick={handleEventClick}
        user={user}
      />
    </div>
  )
}

export default App

