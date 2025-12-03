import { useMemo } from 'react'
import { format, isSameDay } from 'date-fns'
import { ru } from 'date-fns/locale'
import './DayView.css'

function DayView({ date, events, onEventClick }) {
  const dayEvents = useMemo(() => {
    return events
      .filter(event => isSameDay(event.dateObj, date))
      .sort((a, b) => {
        // Sort by time, events without time go to the end
        if (!a.time && !b.time) return 0
        if (!a.time) return 1
        if (!b.time) return -1
        return a.time.localeCompare(b.time)
      })
  }, [events, date])

  const timedEvents = dayEvents.filter(e => e.time)
  const allDayEvents = dayEvents.filter(e => !e.time)
  const isToday = isSameDay(date, new Date())

  // Generate time slots for the timeline
  const timeSlots = Array.from({ length: 24 }, (_, i) => i)

  return (
    <div className="day-view fade-in">
      <div className="day-header">
        <div className={`day-number ${isToday ? 'today' : ''}`}>
          {format(date, 'd')}
        </div>
        <div className="day-info">
          <span className="day-name">{format(date, 'EEEE', { locale: ru })}</span>
          <span className="day-date">{format(date, 'd MMMM yyyy', { locale: ru })}</span>
        </div>
      </div>

      {/* All-day events */}
      {allDayEvents.length > 0 && (
        <div className="all-day-section">
          <div className="section-label">Весь день</div>
          <div className="all-day-events">
            {allDayEvents.map(event => (
              <div 
                key={event.id}
                className={`event-card ${event.type} ${event.completed ? 'completed' : ''}`}
                onClick={() => onEventClick(event)}
              >
                <span className="event-icon">
                  {event.type === 'reminder' ? '🔔' : '📋'}
                </span>
                <span className="event-title">{event.title}</span>
                {event.isRecurring && <span className="event-recurring">🔄</span>}
                {event.priority && (
                  <span className={`event-priority ${event.priority}`}>
                    {event.priority === 'urgent' && '🔴'}
                    {event.priority === 'high' && '🟠'}
                    {event.priority === 'medium' && '🟡'}
                    {event.priority === 'low' && '🟢'}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="timeline">
        {timeSlots.map(hour => {
          const hourEvents = timedEvents.filter(e => {
            const eventHour = parseInt(e.time.split(':')[0])
            return eventHour === hour
          })

          return (
            <div key={hour} className="time-slot">
              <div className="time-label">
                {hour.toString().padStart(2, '0')}:00
              </div>
              <div className="time-content">
                {hourEvents.map(event => (
                  <div 
                    key={event.id}
                    className={`event-card ${event.type} ${event.completed ? 'completed' : ''}`}
                    onClick={() => onEventClick(event)}
                  >
                    <span className="event-time">{event.time}</span>
                    <span className="event-icon">
                      {event.type === 'reminder' ? '🔔' : '📋'}
                    </span>
                    <span className="event-title">{event.title}</span>
                    {event.isRecurring && <span className="event-recurring">🔄</span>}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {dayEvents.length === 0 && (
        <div className="no-events">
          <span className="no-events-icon">📭</span>
          <p>Нет событий на этот день</p>
        </div>
      )}
    </div>
  )
}

export default DayView

