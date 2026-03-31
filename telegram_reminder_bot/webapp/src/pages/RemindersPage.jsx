import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import './PageStyles.css'
import FileViewer, { AttachmentList, AttachmentUpload } from '../components/FileViewer'
import '../components/FileViewer.css'
import { 
  TagsDisplay, TagsInput, parseTags,
  LinksDisplay, LinksInput,
  MetadataDisplay, AttachmentsBadges,
  ItemIndicators
} from '../components/ItemFields'
import '../components/ItemFields.css'

function RemindersPage() {
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingReminder, setEditingReminder] = useState(null)
  const [viewingAttachment, setViewingAttachment] = useState(null)

  useEffect(() => {
    loadReminders()
  }, [])

  const loadReminders = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/reminders', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      if (data.reminders) {
        setReminders(data.reminders)
      }
    } catch (err) {
      console.error('Failed to load reminders:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = async (reminderId) => {
    WebApp.HapticFeedback.impactOccurred('medium')
    try {
      const response = await fetch(`/api/reminders/${reminderId}/complete`, {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      if (response.ok) {
        loadReminders()
      }
    } catch (err) {
      console.error('Failed to complete reminder:', err)
    }
  }

  const handleDelete = async (reminderId) => {
    WebApp.showConfirm('Удалить напоминание?', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.notificationOccurred('warning')
        try {
          const response = await fetch(`/api/reminders/${reminderId}`, {
            method: 'DELETE',
            headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
          })
          if (response.ok) {
            loadReminders()
          }
        } catch (err) {
          console.error('Failed to delete reminder:', err)
        }
      }
    })
  }

  const handleSave = async (reminderData) => {
    try {
      const url = editingReminder 
        ? `/api/reminders/${editingReminder.id}` 
        : '/api/reminders'
      const method = editingReminder ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify(reminderData)
      })
      
      if (response.ok) {
        WebApp.HapticFeedback.notificationOccurred('success')
        setShowForm(false)
        setEditingReminder(null)
        loadReminders()
      }
    } catch (err) {
      console.error('Failed to save reminder:', err)
    }
  }

  if (loading) {
    return (
      <div className="page-loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>🔔 Напоминания</h1>
        <button 
          className="add-button"
          onClick={() => { setEditingReminder(null); setShowForm(true) }}
        >
          ＋
        </button>
      </header>

      <div className="items-list">
        {reminders.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">🔔</span>
            <p>Нет активных напоминаний</p>
            <button 
              className="empty-button"
              onClick={() => setShowForm(true)}
            >
              Создать первое
            </button>
          </div>
        ) : (
          reminders.map(reminder => (
            <ReminderItem 
              key={reminder.id}
              reminder={reminder}
              onComplete={() => handleComplete(reminder.id)}
              onEdit={() => { setEditingReminder(reminder); setShowForm(true) }}
              onDelete={() => handleDelete(reminder.id)}
              onViewAttachment={setViewingAttachment}
            />
          ))
        )}
      </div>

      {showForm && (
        <ReminderForm 
          reminder={editingReminder}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditingReminder(null) }}
          onReload={loadReminders}
        />
      )}
      
      {viewingAttachment && (
        <FileViewer 
          attachment={viewingAttachment}
          onClose={() => setViewingAttachment(null)}
        />
      )}
    </div>
  )
}

function ReminderItem({ reminder, onComplete, onEdit, onDelete, onViewAttachment }) {
  const isPersistent = reminder.is_persistent
  const isRecurring = reminder.recurrence_type && reminder.recurrence_type !== 'none'

  const getRecurrenceText = () => {
    if (!isRecurring) return null
    switch (reminder.recurrence_type) {
      case 'daily': return 'Ежедневно'
      case 'weekly': return 'Еженедельно'
      case 'monthly': return 'Ежемесячно'
      case 'yearly': return 'Ежегодно'
      case 'custom': 
        const days = reminder.recurrence_interval || 7
        if (days === 1) return 'Ежедневно'
        if (days === 7) return 'Еженедельно'
        if (days === 14) return 'Каждые 2 недели'
        return `Каждые ${days} дн.`
      default: return 'Повторяется'
    }
  }

  return (
    <div className={`item-card reminder-card ${isPersistent ? 'persistent' : ''}`}>
      <button 
        className="check-button"
        onClick={onComplete}
      >
        ✓
      </button>
      
      <div className="item-content" onClick={onEdit}>
        <div className="item-title">
          <ItemIndicators 
            isPersistent={isPersistent}
            isRecurring={isRecurring}
            hasAttachments={reminder.attachments?.length > 0}
            hasLinks={reminder.links?.length > 0}
            hasTags={reminder.tags?.length > 0}
          />
          {reminder.title}
        </div>
        
        <div className="item-meta">
          <span className="item-time">
            ⏰ {formatDateTime(reminder.remind_at)}
          </span>
          {isRecurring && (
            <span className="recurrence-text">
              🔄 {getRecurrenceText()}
            </span>
          )}
        </div>
        
        <TagsDisplay tags={reminder.tags} maxShow={3} />
        <LinksDisplay links={reminder.links} maxShow={2} />
        <AttachmentsBadges attachments={reminder.attachments} onView={onViewAttachment} />
      </div>
      
      <button className="delete-button" onClick={onDelete}>
        🗑️
      </button>
    </div>
  )
}

const RECURRENCE_OPTIONS = [
  { value: 'none', label: 'Без повторения' },
  { value: 'daily', label: '🔄 Ежедневно' },
  { value: 'weekly', label: '🔄 Еженедельно' },
  { value: 'monthly', label: '🔄 Ежемесячно' },
  { value: 'yearly', label: '🔄 Ежегодно' },
  { value: 'custom', label: '⚙️ Своё...' },
]

const CUSTOM_INTERVAL_PRESETS = [
  { days: 2, label: 'Каждые 2 дня' },
  { days: 3, label: 'Каждые 3 дня' },
  { days: 14, label: 'Каждые 2 недели' },
  { days: 21, label: 'Каждые 3 недели' },
  { days: 0, label: 'Свой интервал...' },
]

function ReminderForm({ reminder, onSave, onClose, onReload }) {
  const [title, setTitle] = useState(reminder?.title || '')
  const [remindAt, setRemindAt] = useState(
    reminder?.remind_at?.slice(0, 16) || getDefaultDateTime()
  )
  const [isPersistent, setIsPersistent] = useState(reminder?.is_persistent ?? true)
  const [recurrenceType, setRecurrenceType] = useState(reminder?.recurrence_type || 'none')
  const [recurrenceInterval, setRecurrenceInterval] = useState(reminder?.recurrence_interval || 7)
  const [recurrenceEndDate, setRecurrenceEndDate] = useState(reminder?.recurrence_end_date?.slice(0, 10) || '')
  const [customPreset, setCustomPreset] = useState(0)
  const [description, setDescription] = useState(reminder?.description || '')
  const [tags, setTags] = useState(reminder?.tags?.join(', ') || '')
  const [links, setLinks] = useState(reminder?.links || [])
  const [attachments, setAttachments] = useState(reminder?.attachments || [])
  const [viewingAttachment, setViewingAttachment] = useState(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!title.trim() || !remindAt) return
    
    const data = {
      title: title.trim(),
      remind_at: remindAt,
      is_persistent: isPersistent,
      recurrence_type: recurrenceType,
      description: description.trim() || null,
      tags: parseTags(tags),
      links
    }
    
    // Добавить интервал для custom
    if (recurrenceType === 'custom') {
      data.recurrence_interval = parseInt(recurrenceInterval) || 7
    }
    
    // Добавить дату окончания если выбрана
    if (recurrenceType !== 'none' && recurrenceEndDate) {
      data.recurrence_end_date = recurrenceEndDate
    }
    
    onSave(data)
  }
  
  const handleCustomPreset = (days) => {
    setCustomPreset(days)
    if (days > 0) {
      setRecurrenceInterval(days)
    }
  }
  
  const handleUploadAttachment = async (fileData) => {
    if (!reminder?.id) {
      WebApp.showAlert('Сначала сохраните напоминание, потом добавляйте файлы')
      return
    }
    
    try {
      const response = await fetch(`/api/reminders/${reminder.id}/attachments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify(fileData)
      })
      
      const result = await response.json()
      if (result.success && result.attachment) {
        setAttachments([...attachments, result.attachment])
        onReload?.()
      } else {
        WebApp.showAlert(result.error || 'Ошибка загрузки')
      }
    } catch (err) {
      console.error('Upload failed:', err)
      WebApp.showAlert('Ошибка загрузки файла')
    }
  }
  
  const handleDeleteAttachment = async (attachmentId) => {
    if (!reminder?.id) return
    
    WebApp.showConfirm('Удалить вложение?', async (confirmed) => {
      if (confirmed) {
        try {
          const response = await fetch(`/api/reminders/${reminder.id}/attachments/${attachmentId}`, {
            method: 'DELETE',
            headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
          })
          
          if (response.ok) {
            setAttachments(attachments.filter(a => a.id !== attachmentId))
            onReload?.()
          }
        } catch (err) {
          console.error('Delete failed:', err)
        }
      }
    })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{reminder ? 'Редактировать' : 'Новое напоминание'}</h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>
        
        <form onSubmit={handleSubmit} className="form">
          <div className="form-group">
            <label>Текст напоминания</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="О чём напомнить?"
              autoFocus
            />
          </div>
          
          <div className="form-group">
            <label>Дата и время</label>
            <input
              type="datetime-local"
              value={remindAt}
              onChange={e => setRemindAt(e.target.value)}
            />
          </div>
          
          <div className="form-group">
            <label>Повторение</label>
            <select
              value={recurrenceType}
              onChange={e => setRecurrenceType(e.target.value)}
            >
              {RECURRENCE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          
          {/* Custom interval options */}
          {recurrenceType === 'custom' && (
            <div className="form-group">
              <label>Интервал повторения</label>
              <div className="preset-buttons">
                {CUSTOM_INTERVAL_PRESETS.map(preset => (
                  <button
                    key={preset.days}
                    type="button"
                    className={`preset-button ${customPreset === preset.days ? 'active' : ''}`}
                    onClick={() => handleCustomPreset(preset.days)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              
              {customPreset === 0 && (
                <div className="interval-input">
                  <span>Каждые</span>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={recurrenceInterval}
                    onChange={e => setRecurrenceInterval(e.target.value)}
                    className="interval-number"
                  />
                  <span>дней</span>
                </div>
              )}
            </div>
          )}
          
          {/* End date for recurring */}
          {recurrenceType !== 'none' && (
            <div className="form-group">
              <label>Повторять до (необязательно)</label>
              <input
                type="date"
                value={recurrenceEndDate}
                onChange={e => setRecurrenceEndDate(e.target.value)}
                min={new Date().toISOString().slice(0, 10)}
              />
              {recurrenceEndDate && (
                <button 
                  type="button" 
                  className="clear-date-button"
                  onClick={() => setRecurrenceEndDate('')}
                >
                  ✕ Без ограничения
                </button>
              )}
            </div>
          )}
          
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isPersistent}
                onChange={e => setIsPersistent(e.target.checked)}
              />
              <span>🔊 Постоянное уведомление (каждые 60 сек)</span>
            </label>
          </div>
          
          <div className="form-group">
            <label>Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Дополнительная информация..."
              rows={3}
            />
          </div>
          
          {/* Common fields: Tags, Links */}
          <div className="form-group">
            <label>🏷️ Теги</label>
            <TagsInput value={tags} onChange={setTags} placeholder="работа, важное, встреча" />
          </div>
          
          <div className="form-group">
            <label>🔗 Ссылки</label>
            <LinksInput links={links} onChange={setLinks} />
          </div>
          
          {/* Attachments */}
          <div className="form-group">
            <label>📎 Вложения (до 50 МБ)</label>
            {reminder?.id ? (
              <>
                <AttachmentUpload onUpload={handleUploadAttachment} />
                <AttachmentList 
                  attachments={attachments}
                  onView={setViewingAttachment}
                  onDelete={handleDeleteAttachment}
                />
              </>
            ) : (
              <p className="form-hint">💡 Сохраните, чтобы добавить файлы</p>
            )}
          </div>
          
          {/* Metadata */}
          {reminder?.id && (
            <MetadataDisplay 
              createdAt={reminder.created_at}
              updatedAt={reminder.updated_at}
              extraInfo={
                reminder.recurrence_count > 0 
                  ? [`🔄 Выполнено: ${reminder.recurrence_count} раз`] 
                  : undefined
              }
            />
          )}
          
          <button type="submit" className="submit-button">
            {reminder ? 'Сохранить' : 'Создать'}
          </button>
        </form>
      </div>
      
      {viewingAttachment && (
        <FileViewer 
          attachment={viewingAttachment}
          onClose={() => setViewingAttachment(null)}
        />
      )}
    </div>
  )
}

function getDefaultDateTime() {
  const now = new Date()
  now.setHours(now.getHours() + 1)
  now.setMinutes(0)
  // Use local time, not UTC
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

function formatDateTime(dateStr) {
  if (!dateStr) return ''
  // Parse as local time (dateStr format: "2025-12-09T00:20")
  const [datePart, timePart] = dateStr.split('T')
  const [year, month, day] = datePart.split('-').map(Number)
  const [hours, minutes] = (timePart || '00:00').split(':').map(Number)
  const date = new Date(year, month - 1, day, hours, minutes)
  
  const now = new Date()
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  
  const time = date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
  
  if (date.toDateString() === now.toDateString()) {
    return `Сегодня в ${time}`
  }
  if (date.toDateString() === tomorrow.toDateString()) {
    return `Завтра в ${time}`
  }
  return date.toLocaleDateString('ru', { 
    day: 'numeric', 
    month: 'short',
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

export default RemindersPage

