import { useState, useMemo } from 'react'
import { format, startOfWeek, startOfMonth, addDays, addWeeks, addMonths, subWeeks, subMonths, isSameDay } from 'date-fns'
import { ru } from 'date-fns/locale'
import DayView from './DayView'
import WeekView from './WeekView'
import MonthView from './MonthView'
import './Calendar.css'

const VIEW_MODES = {
  DAY: 'day',
  WEEK: 'week',
  MONTH: 'month'
}

function Calendar({ events, onEventClick, user }) {
  const [viewMode, setViewMode] = useState(VIEW_MODES.WEEK)
  const [currentDate, setCurrentDate] = useState(new Date())

  const navigate = (direction) => {
    switch (viewMode) {
      case VIEW_MODES.DAY:
        setCurrentDate(prev => addDays(prev, direction))
        break
      case VIEW_MODES.WEEK:
        setCurrentDate(prev => direction > 0 ? addWeeks(prev, 1) : subWeeks(prev, 1))
        break
      case VIEW_MODES.MONTH:
        setCurrentDate(prev => direction > 0 ? addMonths(prev, 1) : subMonths(prev, 1))
        break
    }
  }

  const goToToday = () => {
    setCurrentDate(new Date())
  }

  const getTitle = () => {
    switch (viewMode) {
      case VIEW_MODES.DAY:
        return format(currentDate, 'd MMMM yyyy', { locale: ru })
      case VIEW_MODES.WEEK:
        const weekStart = startOfWeek(currentDate, { weekStartsOn: 1 })
        const weekEnd = addDays(weekStart, 6)
        return `${format(weekStart, 'd', { locale: ru })} - ${format(weekEnd, 'd MMMM', { locale: ru })}`
      case VIEW_MODES.MONTH:
        return format(currentDate, 'LLLL yyyy', { locale: ru })
    }
  }

  const filteredEvents = useMemo(() => {
    return events.map(event => ({
      ...event,
      dateObj: new Date(event.date)
    }))
  }, [events])

  const isToday = isSameDay(currentDate, new Date())

  return (
    <div className="calendar">
      {/* Header */}
      <header className="calendar-header">
        <div className="calendar-nav">
          <button className="nav-btn" onClick={() => navigate(-1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15,18 9,12 15,6"></polyline>
            </svg>
          </button>
          
          <h1 className="calendar-title">{getTitle()}</h1>
          
          <button className="nav-btn" onClick={() => navigate(1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9,6 15,12 9,18"></polyline>
            </svg>
          </button>
        </div>

        <div className="calendar-actions">
          {!isToday && (
            <button className="today-btn" onClick={goToToday}>
              Сегодня
            </button>
          )}
        </div>
      </header>

      {/* View Mode Tabs */}
      <div className="view-tabs">
        <button 
          className={`view-tab ${viewMode === VIEW_MODES.DAY ? 'active' : ''}`}
          onClick={() => setViewMode(VIEW_MODES.DAY)}
        >
          День
        </button>
        <button 
          className={`view-tab ${viewMode === VIEW_MODES.WEEK ? 'active' : ''}`}
          onClick={() => setViewMode(VIEW_MODES.WEEK)}
        >
          Неделя
        </button>
        <button 
          className={`view-tab ${viewMode === VIEW_MODES.MONTH ? 'active' : ''}`}
          onClick={() => setViewMode(VIEW_MODES.MONTH)}
        >
          Месяц
        </button>
      </div>

      {/* Calendar Content */}
      <div className="calendar-content">
        {viewMode === VIEW_MODES.DAY && (
          <DayView 
            date={currentDate} 
            events={filteredEvents} 
            onEventClick={onEventClick}
          />
        )}
        {viewMode === VIEW_MODES.WEEK && (
          <WeekView 
            date={currentDate} 
            events={filteredEvents} 
            onEventClick={onEventClick}
            onDayClick={(date) => {
              setCurrentDate(date)
              setViewMode(VIEW_MODES.DAY)
            }}
          />
        )}
        {viewMode === VIEW_MODES.MONTH && (
          <MonthView 
            date={currentDate} 
            events={filteredEvents} 
            onEventClick={onEventClick}
            onDayClick={(date) => {
              setCurrentDate(date)
              setViewMode(VIEW_MODES.DAY)
            }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="calendar-legend">
        <span className="legend-item">
          <span className="legend-dot reminder"></span>
          Напоминания
        </span>
        <span className="legend-item">
          <span className="legend-dot todo"></span>
          Задачи
        </span>
      </div>
    </div>
  )
}

export default Calendar

