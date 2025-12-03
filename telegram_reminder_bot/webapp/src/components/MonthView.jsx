import { useMemo } from 'react'
import { 
  format, 
  startOfMonth, 
  endOfMonth, 
  startOfWeek, 
  endOfWeek, 
  addDays, 
  isSameDay, 
  isSameMonth,
  isWeekend 
} from 'date-fns'
import { ru } from 'date-fns/locale'
import './MonthView.css'

function MonthView({ date, events, onEventClick, onDayClick }) {
  const today = new Date()
  const monthStart = startOfMonth(date)
  const monthEnd = endOfMonth(date)
  
  const calendarDays = useMemo(() => {
    const start = startOfWeek(monthStart, { weekStartsOn: 1 })
    const end = endOfWeek(monthEnd, { weekStartsOn: 1 })
    
    const days = []
    let day = start
    
    while (day <= end) {
      const currentDay = day
      const dayEvents = events.filter(event => isSameDay(event.dateObj, currentDay))
      
      days.push({
        date: currentDay,
        events: dayEvents,
        isCurrentMonth: isSameMonth(currentDay, date),
        isToday: isSameDay(currentDay, today),
        isWeekend: isWeekend(currentDay)
      })
      
      day = addDays(day, 1)
    }
    
    return days
  }, [date, events, monthStart, monthEnd])

  // Split into weeks
  const weeks = useMemo(() => {
    const result = []
    for (let i = 0; i < calendarDays.length; i += 7) {
      result.push(calendarDays.slice(i, i + 7))
    }
    return result
  }, [calendarDays])

  return (
    <div className="month-view fade-in">
      {/* Month Header */}
      <div className="month-header">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day, i) => (
          <div 
            key={day} 
            className={`month-header-cell ${i >= 5 ? 'weekend' : ''}`}
          >
            {day}
          </div>
        ))}
      </div>

      {/* Month Grid */}
      <div className="month-grid">
        {weeks.map((week, weekIndex) => (
          <div key={weekIndex} className="month-week">
            {week.map(({ date: dayDate, events: dayEvents, isCurrentMonth, isToday, isWeekend }) => {
              const reminderCount = dayEvents.filter(e => e.type === 'reminder').length
              const todoCount = dayEvents.filter(e => e.type === 'todo').length
              
              return (
                <div 
                  key={dayDate.toISOString()}
                  className={`month-day ${!isCurrentMonth ? 'other-month' : ''} ${isToday ? 'today' : ''} ${isWeekend ? 'weekend' : ''}`}
                  onClick={() => onDayClick(dayDate)}
                >
                  <span className={`month-day-number ${isToday ? 'today' : ''}`}>
                    {format(dayDate, 'd')}
                  </span>
                  
                  {/* Event dots */}
                  {dayEvents.length > 0 && (
                    <div className="month-day-dots">
                      {reminderCount > 0 && (
                        <span className="dot reminder" title={`${reminderCount} напоминаний`}>
                          {reminderCount > 3 ? '3+' : '●'.repeat(reminderCount)}
                        </span>
                      )}
                      {todoCount > 0 && (
                        <span className="dot todo" title={`${todoCount} задач`}>
                          {todoCount > 3 ? '3+' : '●'.repeat(todoCount)}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Quick event list for selected date */}
      <div className="month-events-preview">
        <h3 className="preview-title">
          {format(date, 'd MMMM', { locale: ru })}
        </h3>
        
        {events.filter(e => isSameDay(e.dateObj, date)).length > 0 ? (
          <div className="preview-events">
            {events
              .filter(e => isSameDay(e.dateObj, date))
              .slice(0, 5)
              .map(event => (
                <div 
                  key={event.id}
                  className={`preview-event ${event.type}`}
                  onClick={() => onEventClick(event)}
                >
                  <span className="preview-icon">
                    {event.type === 'reminder' ? '🔔' : '📋'}
                  </span>
                  <span className="preview-time">{event.time || ''}</span>
                  <span className="preview-title-text">{event.title}</span>
                </div>
              ))}
          </div>
        ) : (
          <p className="preview-empty">Нет событий</p>
        )}
      </div>
    </div>
  )
}

export default MonthView

