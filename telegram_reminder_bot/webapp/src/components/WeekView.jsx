import { useMemo } from 'react'
import { format, startOfWeek, addDays, isSameDay, isWeekend } from 'date-fns'
import { ru } from 'date-fns/locale'
import './WeekView.css'

function WeekView({ date, events, onEventClick, onDayClick }) {
  const weekStart = startOfWeek(date, { weekStartsOn: 1 })
  const today = new Date()

  const weekDays = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => {
      const day = addDays(weekStart, i)
      const dayEvents = events.filter(event => isSameDay(event.dateObj, day))
      return {
        date: day,
        events: dayEvents,
        isToday: isSameDay(day, today),
        isWeekend: isWeekend(day)
      }
    })
  }, [weekStart, events])

  const getEventPreview = (dayEvents) => {
    const reminders = dayEvents.filter(e => e.type === 'reminder')
    const todos = dayEvents.filter(e => e.type === 'todo')
    return { reminders, todos }
  }

  return (
    <div className="week-view fade-in">
      {/* Week Header */}
      <div className="week-header">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day, i) => (
          <div 
            key={day} 
            className={`week-header-cell ${i >= 5 ? 'weekend' : ''}`}
          >
            {day}
          </div>
        ))}
      </div>

      {/* Week Grid */}
      <div className="week-grid">
        {weekDays.map(({ date: dayDate, events: dayEvents, isToday, isWeekend }) => {
          const { reminders, todos } = getEventPreview(dayEvents)
          
          return (
            <div 
              key={dayDate.toISOString()}
              className={`week-day ${isToday ? 'today' : ''} ${isWeekend ? 'weekend' : ''}`}
              onClick={() => onDayClick(dayDate)}
            >
              <div className="week-day-header">
                <span className={`week-day-number ${isToday ? 'today' : ''}`}>
                  {format(dayDate, 'd')}
                </span>
                <span className="week-day-name">
                  {format(dayDate, 'EEE', { locale: ru })}
                </span>
              </div>

              <div className="week-day-events">
                {/* Show first 3 events */}
                {dayEvents.slice(0, 3).map(event => (
                  <div 
                    key={event.id}
                    className={`week-event ${event.type} ${event.completed ? 'completed' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onEventClick(event)
                    }}
                  >
                    <span className="week-event-icon">
                      {event.type === 'reminder' ? '🔔' : '📋'}
                    </span>
                    <span className="week-event-time">
                      {event.time || ''}
                    </span>
                    <span className="week-event-title">
                      {event.title}
                    </span>
                  </div>
                ))}

                {/* Show more indicator */}
                {dayEvents.length > 3 && (
                  <div className="week-more">
                    +{dayEvents.length - 3} ещё
                  </div>
                )}
              </div>

              {/* Event indicators at bottom */}
              {dayEvents.length > 0 && (
                <div className="week-day-indicators">
                  {reminders.length > 0 && (
                    <span className="indicator reminder">{reminders.length}</span>
                  )}
                  {todos.length > 0 && (
                    <span className="indicator todo">{todos.length}</span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default WeekView

