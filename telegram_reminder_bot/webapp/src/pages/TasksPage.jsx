import { useState, useEffect, useCallback } from 'react'
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

const PRIORITIES = {
  low: { label: 'Низкий', color: '#22c55e', icon: '🟢' },
  medium: { label: 'Средний', color: '#eab308', icon: '🟡' },
  high: { label: 'Высокий', color: '#f97316', icon: '🟠' },
  urgent: { label: 'Срочный', color: '#ef4444', icon: '🔴' }
}

const STATUSES = {
  pending: { label: 'Ожидает', icon: '⏳' },
  in_progress: { label: 'В работе', icon: '🔄' },
  completed: { label: 'Выполнено', icon: '✅' }
}

const PROGRESS_PRESETS = [0, 25, 50, 75, 100]

function TasksPage() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingTask, setEditingTask] = useState(null)
  const [filter, setFilter] = useState('active') // active, completed, all
  const [viewingAttachment, setViewingAttachment] = useState(null)

  useEffect(() => {
    loadTasks()
  }, [])

  const loadTasks = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/todos', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      if (data.todos) {
        setTasks(data.todos)
      }
    } catch (err) {
      console.error('Failed to load tasks:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = async (taskId) => {
    WebApp.HapticFeedback.impactOccurred('medium')
    try {
      const response = await fetch(`/api/todos/${taskId}/complete`, {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      if (response.ok) {
        loadTasks()
      }
    } catch (err) {
      console.error('Failed to complete task:', err)
    }
  }

  const handleDelete = async (taskId) => {
    WebApp.showConfirm('Удалить задачу?', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.notificationOccurred('warning')
        try {
          const response = await fetch(`/api/todos/${taskId}`, {
            method: 'DELETE',
            headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
          })
          if (response.ok) {
            loadTasks()
          }
        } catch (err) {
          console.error('Failed to delete task:', err)
        }
      }
    })
  }

  const handleSave = async (taskData) => {
    try {
      const url = editingTask ? `/api/todos/${editingTask.id}` : '/api/todos'
      const method = editingTask ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify(taskData)
      })
      
      if (response.ok) {
        WebApp.HapticFeedback.notificationOccurred('success')
        setShowForm(false)
        setEditingTask(null)
        loadTasks()
      }
    } catch (err) {
      console.error('Failed to save task:', err)
    }
  }

  const handleUpdateProgress = async (taskId, progress) => {
    WebApp.HapticFeedback.impactOccurred('light')
    try {
      // Auto-complete if 100%
      const status = progress === 100 ? 'completed' : 'in_progress'
      
      const response = await fetch(`/api/todos/${taskId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify({ progress, status })
      })
      
      if (response.ok) {
        loadTasks()
      }
    } catch (err) {
      console.error('Failed to update progress:', err)
    }
  }

  const filteredTasks = tasks.filter(task => {
    if (filter === 'active') return task.status !== 'completed'
    if (filter === 'completed') return task.status === 'completed'
    return true
  })

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
        <h1>📋 Задачи</h1>
        <button 
          className="add-button"
          onClick={() => { setEditingTask(null); setShowForm(true) }}
        >
          ＋
        </button>
      </header>

      <div className="filter-tabs">
        <button 
          className={`filter-tab ${filter === 'active' ? 'active' : ''}`}
          onClick={() => setFilter('active')}
        >
          Активные
        </button>
        <button 
          className={`filter-tab ${filter === 'completed' ? 'active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          Выполненные
        </button>
        <button 
          className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          Все
        </button>
      </div>

      <div className="items-list">
        {filteredTasks.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">📋</span>
            <p>Нет задач</p>
            <button 
              className="empty-button"
              onClick={() => setShowForm(true)}
            >
              Создать первую
            </button>
          </div>
        ) : (
          filteredTasks.map(task => (
            <TaskItem 
              key={task.id}
              task={task}
              onComplete={() => handleComplete(task.id)}
              onEdit={() => { setEditingTask(task); setShowForm(true) }}
              onDelete={() => handleDelete(task.id)}
              onUpdateProgress={handleUpdateProgress}
              onViewAttachment={setViewingAttachment}
            />
          ))
        )}
      </div>

      {showForm && (
        <TaskForm 
          task={editingTask}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditingTask(null) }}
          onReload={loadTasks}
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

function TaskItem({ task, onComplete, onEdit, onDelete, onUpdateProgress, onViewAttachment }) {
  const priority = PRIORITIES[task.priority] || PRIORITIES.medium
  const isCompleted = task.status === 'completed'
  const progress = task.progress || 0
  const subtasksCount = task.subtasks?.length || 0
  const completedSubtasks = task.subtasks?.filter(s => s.completed).length || 0

  const getProgressColor = (p) => {
    if (p === 100) return '#22c55e'
    if (p >= 75) return '#84cc16'
    if (p >= 50) return '#eab308'
    if (p >= 25) return '#f97316'
    return '#6b7280'
  }

  const handleProgressClick = (e) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percent = Math.round((x / rect.width) * 100 / 25) * 25
    onUpdateProgress?.(task.id, Math.min(100, Math.max(0, percent)))
  }

  return (
    <div className={`item-card ${isCompleted ? 'completed' : ''}`}>
      <button 
        className={`check-button ${isCompleted ? 'checked' : ''}`}
        onClick={onComplete}
        style={{ borderColor: priority.color }}
      >
        {isCompleted ? '✓' : progress > 0 ? `${progress}` : ''}
      </button>
      
      <div className="item-content" onClick={onEdit}>
        <div className="item-title">
          <ItemIndicators 
            isRecurring={task.recurrence_type && task.recurrence_type !== 'none'}
            hasAttachments={task.attachments?.length > 0}
            hasLinks={task.links?.length > 0}
            hasTags={task.tags?.length > 0}
          />
          {task.title}
        </div>
        
        {/* Description preview */}
        {task.description && (
          <p className="task-description-preview">{task.description}</p>
        )}
        
        {/* Subtasks indicator */}
        {subtasksCount > 0 && (
          <div className="subtasks-indicator">
            ☑️ {completedSubtasks}/{subtasksCount} подзадач
          </div>
        )}
        
        {/* Progress bar */}
        {!isCompleted && (
          <div 
            className="progress-bar-container" 
            onClick={handleProgressClick}
            title={`${progress}% выполнено`}
          >
            <div 
              className="progress-bar-fill" 
              style={{ 
                width: `${progress}%`,
                backgroundColor: getProgressColor(progress)
              }}
            />
            <span className="progress-label">{progress}%</span>
          </div>
        )}
        
        <TagsDisplay tags={task.tags} maxShow={3} />
        <AttachmentsBadges attachments={task.attachments} onView={onViewAttachment} />
        
        <div className="item-meta">
          <span className="priority-badge" style={{ color: priority.color }}>
            {priority.icon} {priority.label}
          </span>
          
          {task.deadline && (
            <span className="deadline">
              📅 {formatDate(task.deadline)}
            </span>
          )}
        </div>
      </div>
      
      <button className="delete-button" onClick={onDelete}>
        🗑️
      </button>
    </div>
  )
}

const RECURRENCE_OPTIONS = [
  { value: 'none', label: 'Без повторения' },
  { value: 'daily', label: '🔁 Ежедневно' },
  { value: 'weekly', label: '🔁 Еженедельно' },
  { value: 'monthly', label: '🔁 Ежемесячно' },
  { value: 'yearly', label: '🔁 Ежегодно' },
]

function TaskForm({ task, onSave, onClose, onReload }) {
  const [title, setTitle] = useState(task?.title || '')
  const [priority, setPriority] = useState(task?.priority || 'medium')
  const [deadline, setDeadline] = useState(task?.deadline?.slice(0, 16) || '')
  const [recurrenceType, setRecurrenceType] = useState(task?.recurrence_type || 'none')
  const [description, setDescription] = useState(task?.description || '')
  const [progress, setProgress] = useState(task?.progress || 0)
  const [tags, setTags] = useState(task?.tags?.join(', ') || '')
  const [links, setLinks] = useState(task?.links || [])
  const [subtasks, setSubtasks] = useState(task?.subtasks || [])
  const [newSubtask, setNewSubtask] = useState('')
  const [attachments, setAttachments] = useState(task?.attachments || [])
  const [viewingAttachment, setViewingAttachment] = useState(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!title.trim()) return
    
    // Auto-set status based on progress
    let status = task?.status || 'pending'
    if (progress === 100) {
      status = 'completed'
    } else if (progress > 0) {
      status = 'in_progress'
    }
    
    onSave({
      title: title.trim(),
      priority,
      progress,
      status,
      deadline: deadline || null,
      recurrence_type: recurrenceType,
      description: description.trim() || null,
      tags: parseTags(tags),
      links,
      subtasks
    })
  }
  
  // Subtask handlers
  const handleAddSubtask = () => {
    if (!newSubtask.trim()) return
    const subtask = {
      id: Date.now().toString(),
      title: newSubtask.trim(),
      completed: false
    }
    setSubtasks([...subtasks, subtask])
    setNewSubtask('')
  }
  
  const handleToggleSubtask = (id) => {
    setSubtasks(subtasks.map(s => 
      s.id === id ? { ...s, completed: !s.completed } : s
    ))
  }
  
  const handleDeleteSubtask = (id) => {
    setSubtasks(subtasks.filter(s => s.id !== id))
  }
  
  const handleEditSubtask = (id, newTitle) => {
    setSubtasks(subtasks.map(s => 
      s.id === id ? { ...s, title: newTitle } : s
    ))
  }
  
  // Attachment handlers
  const handleUploadAttachment = async (fileData) => {
    if (!task?.id) {
      WebApp.showAlert('Сначала сохраните задачу, потом добавляйте файлы')
      return
    }
    
    try {
      const response = await fetch(`/api/todos/${task.id}/attachments`, {
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
    if (!task?.id) return
    
    WebApp.showConfirm('Удалить вложение?', async (confirmed) => {
      if (confirmed) {
        try {
          const response = await fetch(`/api/todos/${task.id}/attachments/${attachmentId}`, {
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
          <h2>{task ? 'Редактировать' : 'Новая задача'}</h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>
        
        <form onSubmit={handleSubmit} className="form">
          <div className="form-group">
            <label>Название</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Что нужно сделать?"
              autoFocus
            />
          </div>
          
          <div className="form-group">
            <label>Приоритет</label>
            <div className="priority-selector">
              {Object.entries(PRIORITIES).map(([key, val]) => (
                <button
                  key={key}
                  type="button"
                  className={`priority-option ${priority === key ? 'selected' : ''}`}
                  onClick={() => setPriority(key)}
                  style={{ '--priority-color': val.color }}
                >
                  {val.icon}
                </button>
              ))}
            </div>
          </div>
          
          {/* Progress selector */}
          <div className="form-group">
            <label>Прогресс: {progress}%</label>
            <div className="progress-selector">
              {PROGRESS_PRESETS.map(p => (
                <button
                  key={p}
                  type="button"
                  className={`progress-option ${progress === p ? 'selected' : ''}`}
                  onClick={() => setProgress(p)}
                >
                  {p}%
                </button>
              ))}
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={progress}
              onChange={e => setProgress(parseInt(e.target.value))}
              className="progress-slider"
            />
          </div>
          
          <div className="form-group">
            <label>Дедлайн</label>
            <input
              type="datetime-local"
              value={deadline}
              onChange={e => setDeadline(e.target.value)}
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
          
          <div className="form-group">
            <label>📝 Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Дополнительная информация..."
              rows={3}
            />
          </div>
          
          {/* Subtasks */}
          <div className="form-group">
            <label>☑️ Подзадачи</label>
            <div className="subtask-add-row">
              <input
                type="text"
                value={newSubtask}
                onChange={e => setNewSubtask(e.target.value)}
                placeholder="Добавить подзадачу..."
                onKeyPress={e => e.key === 'Enter' && (e.preventDefault(), handleAddSubtask())}
              />
              <button type="button" className="subtask-add-btn" onClick={handleAddSubtask}>+</button>
            </div>
            {subtasks.length > 0 && (
              <div className="subtasks-list">
                {subtasks.map(subtask => (
                  <SubtaskItem 
                    key={subtask.id}
                    subtask={subtask}
                    onToggle={() => handleToggleSubtask(subtask.id)}
                    onDelete={() => handleDeleteSubtask(subtask.id)}
                    onEdit={(newTitle) => handleEditSubtask(subtask.id, newTitle)}
                  />
                ))}
              </div>
            )}
          </div>
          
          {/* Tags */}
          <div className="form-group">
            <label>🏷️ Теги</label>
            <TagsInput value={tags} onChange={setTags} />
          </div>
          
          {/* Links */}
          <div className="form-group">
            <label>🔗 Ссылки</label>
            <LinksInput links={links} onChange={setLinks} />
          </div>
          
          {/* Attachments */}
          <div className="form-group">
            <label>📎 Вложения (до 50 МБ)</label>
            {task?.id ? (
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
          {task?.id && (
            <MetadataDisplay 
              createdAt={task.created_at}
              updatedAt={task.updated_at}
            />
          )}
          
          <button type="submit" className="submit-button">
            {task ? 'Сохранить' : 'Создать'}
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

// Subtask component
function SubtaskItem({ subtask, onToggle, onDelete, onEdit }) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(subtask.title)
  
  const handleSaveEdit = () => {
    if (editText.trim()) {
      onEdit(editText.trim())
    }
    setEditing(false)
  }
  
  if (editing) {
    return (
      <div className="subtask-item editing">
        <input
          type="text"
          value={editText}
          onChange={e => setEditText(e.target.value)}
          onBlur={handleSaveEdit}
          onKeyPress={e => e.key === 'Enter' && handleSaveEdit()}
          autoFocus
        />
        <button type="button" onClick={handleSaveEdit}>✓</button>
      </div>
    )
  }
  
  return (
    <div className={`subtask-item ${subtask.completed ? 'completed' : ''}`}>
      <button type="button" className="subtask-check" onClick={onToggle}>
        {subtask.completed ? '✅' : '⬜'}
      </button>
      <span className="subtask-title" onClick={() => setEditing(true)}>
        {subtask.title}
      </span>
      <button type="button" className="subtask-delete" onClick={onDelete}>✕</button>
    </div>
  )
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  
  if (date.toDateString() === now.toDateString()) {
    return `Сегодня ${date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })}`
  }
  if (date.toDateString() === tomorrow.toDateString()) {
    return `Завтра ${date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })}`
  }
  return date.toLocaleDateString('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export default TasksPage

