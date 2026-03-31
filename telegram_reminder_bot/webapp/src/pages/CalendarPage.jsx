import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import Calendar from '../components/Calendar'
import './PageStyles.css'

function CalendarPage() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadEvents()
  }, [])

  const loadEvents = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/events', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      if (data.events) {
        setEvents(data.events)
      }
    } catch (err) {
      console.error('Failed to load events:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleEventClick = (event) => {
    WebApp.HapticFeedback.selectionChanged()
    
    const typeLabel = event.type === 'reminder' ? '🔔 Напоминание' : '📋 Задача'
    const time = event.time || ''
    const recurring = event.isRecurring ? '\n🔄 Повторяющееся' : ''
    
    WebApp.showPopup({
      title: typeLabel,
      message: `${event.title}\n${time}${recurring}`,
      buttons: [
        { id: 'close', type: 'cancel', text: 'Закрыть' }
      ]
    })
  }

  if (loading) {
    return (
      <div className="page-loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  return (
    <div className="page calendar-page">
      <header className="page-header">
        <h1>📅 Календарь</h1>
      </header>
      
      <Calendar 
        events={events} 
        onEventClick={handleEventClick}
      />
    </div>
  )
}

export default CalendarPage

