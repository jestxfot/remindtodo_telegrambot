import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import './PageStyles.css'

function ArchivePage() {
  const [archive, setArchive] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    loadArchive()
  }, [])

  const loadArchive = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/archive', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      if (data.archive) {
        setArchive(data.archive)
      }
    } catch (err) {
      console.error('Failed to load archive:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRestore = async (archivedAt) => {
    WebApp.showConfirm('Восстановить элемент?', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.impactOccurred('medium')
        try {
          const response = await fetch(`/api/archive/restore`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Telegram-Init-Data': WebApp.initData || ''
            },
            body: JSON.stringify({ archived_at: archivedAt })
          })
          if (response.ok) {
            WebApp.HapticFeedback.notificationOccurred('success')
            loadArchive()
          }
        } catch (err) {
          console.error('Failed to restore:', err)
        }
      }
    })
  }

  const handleDelete = async (archivedAt) => {
    WebApp.showConfirm('Удалить навсегда?', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.notificationOccurred('warning')
        try {
          const response = await fetch(`/api/archive/delete`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Telegram-Init-Data': WebApp.initData || ''
            },
            body: JSON.stringify({ archived_at: archivedAt })
          })
          if (response.ok) {
            loadArchive()
          }
        } catch (err) {
          console.error('Failed to delete:', err)
        }
      }
    })
  }

  const handleClearAll = () => {
    if (archive.length === 0) return
    
    WebApp.showConfirm('Очистить весь архив? Это действие нельзя отменить!', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.notificationOccurred('warning')
        try {
          const response = await fetch('/api/archive/clear', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Telegram-Init-Data': WebApp.initData || ''
            },
            body: JSON.stringify({ item_type: filter === 'all' ? null : filter })
          })
          if (response.ok) {
            loadArchive()
          }
        } catch (err) {
          console.error('Failed to clear archive:', err)
        }
      }
    })
  }

  const filteredArchive = filter === 'all' 
    ? archive 
    : archive.filter(item => item.item_type === filter)

  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    return date.toLocaleDateString('ru', { 
      day: 'numeric', 
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
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
    <div className="page archive-page">
      <header className="page-header">
        <h1>🗃️ Архив</h1>
        {archive.length > 0 && (
          <button className="clear-all-button" onClick={handleClearAll}>
            🗑️
          </button>
        )}
      </header>

      <div className="filter-tabs">
        <button 
          className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          Все ({archive.length})
        </button>
        <button 
          className={`filter-tab ${filter === 'todo' ? 'active' : ''}`}
          onClick={() => setFilter('todo')}
        >
          📋 Задачи ({archive.filter(a => a.item_type === 'todo').length})
        </button>
        <button 
          className={`filter-tab ${filter === 'reminder' ? 'active' : ''}`}
          onClick={() => setFilter('reminder')}
        >
          🔔 Напоминания ({archive.filter(a => a.item_type === 'reminder').length})
        </button>
      </div>

      <div className="items-list">
        {filteredArchive.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">🗃️</span>
            <p>Архив пуст</p>
            <p className="empty-hint">Выполненные задачи и напоминания появятся здесь</p>
          </div>
        ) : (
          filteredArchive.map(item => (
            <ArchiveItem 
              key={item.archived_at}
              item={item}
              onRestore={() => handleRestore(item.archived_at)}
              onDelete={() => handleDelete(item.archived_at)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function ArchiveItem({ item, onRestore, onDelete }) {
  const data = item.data || {}
  const isReminder = item.item_type === 'reminder'
  const icon = isReminder ? '🔔' : '📋'
  
  const getRecurrenceText = () => {
    const type = data.recurrence_type
    if (!type || type === 'none') return null
    switch (type) {
      case 'daily': return 'Ежедневно'
      case 'weekly': return 'Еженедельно'
      case 'monthly': return 'Ежемесячно'
      case 'yearly': return 'Ежегодно'
      case 'custom': return `Каждые ${data.recurrence_interval || 7} дн.`
      default: return null
    }
  }

  const recurrenceText = getRecurrenceText()

  return (
    <div className="item-card archive-card">
      <div className="archive-icon">{icon}</div>
      
      <div className="item-content">
        <div className="item-title">
          {data.title || 'Без названия'}
          {recurrenceText && (
            <span className="recurrence-badge-small">🔄 {recurrenceText}</span>
          )}
        </div>
        
        <div className="item-meta">
          <span className="archive-date">
            Архивировано: {formatArchiveDate(item.archived_at)}
          </span>
          {data.recurrence_count > 0 && (
            <span className="completion-count">
              ✓ {data.recurrence_count} раз
            </span>
          )}
        </div>
      </div>
      
      <div className="archive-actions">
        <button className="restore-button" onClick={onRestore} title="Восстановить">
          ↩️
        </button>
        <button className="delete-button" onClick={onDelete} title="Удалить">
          🗑️
        </button>
      </div>
    </div>
  )
}

function formatArchiveDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return 'только что'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} мин назад`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} ч назад`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} дн назад`
  
  return date.toLocaleDateString('ru', { day: 'numeric', month: 'short' })
}

export default ArchivePage

