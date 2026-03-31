import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import './PageStyles.css'
import FileViewer, { AttachmentList, AttachmentUpload } from '../components/FileViewer'
import '../components/FileViewer.css'
import { 
  TagsDisplay, TagsInput, parseTags,
  LinksDisplay, LinksInput,
  StatusSelector, StatusBadge,
  MetadataDisplay, AttachmentsBadges,
  ItemIndicators, CommonFieldsSection
} from '../components/ItemFields'
import '../components/ItemFields.css'

function NotesPage() {
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingNote, setEditingNote] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewingAttachment, setViewingAttachment] = useState(null)

  useEffect(() => {
    loadNotes()
  }, [])

  const loadNotes = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/notes', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      if (data.notes) {
        setNotes(data.notes)
      }
    } catch (err) {
      console.error('Failed to load notes:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (noteId) => {
    WebApp.showConfirm('Удалить заметку?', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.notificationOccurred('warning')
        try {
          const response = await fetch(`/api/notes/${noteId}`, {
            method: 'DELETE',
            headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
          })
          if (response.ok) {
            loadNotes()
          }
        } catch (err) {
          console.error('Failed to delete note:', err)
        }
      }
    })
  }

  const handleSave = async (noteData) => {
    try {
      const url = editingNote ? `/api/notes/${editingNote.id}` : '/api/notes'
      const method = editingNote ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify(noteData)
      })
      
      if (response.ok) {
        WebApp.HapticFeedback.notificationOccurred('success')
        setShowForm(false)
        setEditingNote(null)
        loadNotes()
      }
    } catch (err) {
      console.error('Failed to save note:', err)
    }
  }

  const filteredNotes = notes.filter(note => 
    note.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    note.content.toLowerCase().includes(searchQuery.toLowerCase())
  )

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
        <h1>📝 Заметки</h1>
        <button 
          className="add-button"
          onClick={() => { setEditingNote(null); setShowForm(true) }}
        >
          ＋
        </button>
      </header>

      {notes.length > 0 && (
        <div className="search-bar">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="🔍 Поиск заметок..."
          />
        </div>
      )}

      <div className="items-list notes-grid">
        {filteredNotes.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">📝</span>
            <p>{searchQuery ? 'Ничего не найдено' : 'Нет заметок'}</p>
            {!searchQuery && (
              <button 
                className="empty-button"
                onClick={() => setShowForm(true)}
              >
                Создать первую
              </button>
            )}
          </div>
        ) : (
          filteredNotes.map(note => (
            <NoteItem 
              key={note.id}
              note={note}
              onEdit={() => { setEditingNote(note); setShowForm(true) }}
              onDelete={() => handleDelete(note.id)}
              onViewAttachment={setViewingAttachment}
            />
          ))
        )}
      </div>

      {showForm && (
        <NoteForm 
          note={editingNote}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditingNote(null) }}
          onReload={loadNotes}
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

function NoteItem({ note, onEdit, onDelete, onViewAttachment }) {
  return (
    <div className={`item-card note-card ${note.status === 'draft' ? 'draft' : ''}`} onClick={onEdit}>
      <div className="item-content">
        <div className="item-title">
          <ItemIndicators 
            isPinned={note.is_pinned}
            hasAttachments={note.attachments?.length > 0}
            hasLinks={note.links?.length > 0}
            hasTags={note.tags?.length > 0}
            status={note.status}
          />
          {note.title}
        </div>
        
        <p className="note-preview">{note.content}</p>
        
        <TagsDisplay tags={note.tags} />
        <LinksDisplay links={note.links} />
        <AttachmentsBadges attachments={note.attachments} onView={onViewAttachment} />
        
        <div className="item-meta">
          <span className="note-date">
            {formatDate(note.updated_at || note.created_at)}
          </span>
          {note.created_at !== note.updated_at && (
            <span className="note-edited">изм.</span>
          )}
        </div>
      </div>
      
      <button 
        className="delete-button" 
        onClick={(e) => { e.stopPropagation(); onDelete() }}
      >
        🗑️
      </button>
    </div>
  )
}

function NoteForm({ note, onSave, onClose, onReload }) {
  const [title, setTitle] = useState(note?.title || '')
  const [content, setContent] = useState(note?.content || '')
  const [isPinned, setIsPinned] = useState(note?.is_pinned || false)
  const [status, setStatus] = useState(note?.status || 'active')
  const [tags, setTags] = useState(note?.tags?.join(', ') || '')
  const [links, setLinks] = useState(note?.links || [])
  const [attachments, setAttachments] = useState(note?.attachments || [])
  const [viewingAttachment, setViewingAttachment] = useState(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!title.trim()) return
    
    onSave({
      title: title.trim(),
      content: content.trim(),
      is_pinned: isPinned,
      status,
      tags: parseTags(tags),
      links
    })
  }
  
  const handleUploadAttachment = async (fileData) => {
    if (!note?.id) {
      WebApp.showAlert('Сначала сохраните заметку, потом добавляйте файлы')
      return
    }
    
    try {
      const response = await fetch(`/api/notes/${note.id}/attachments`, {
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
    if (!note?.id) return
    
    WebApp.showConfirm('Удалить вложение?', async (confirmed) => {
      if (confirmed) {
        try {
          const response = await fetch(`/api/notes/${note.id}/attachments/${attachmentId}`, {
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
      <div className="modal modal-fullscreen" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{note ? 'Редактировать' : 'Новая заметка'}</h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>
        
        <form onSubmit={handleSubmit} className="form">
          <div className="form-group">
            <label>Заголовок</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Название заметки"
              autoFocus
            />
          </div>
          
          <div className="form-group">
            <label>Содержимое</label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Текст заметки..."
              rows={8}
              className="note-textarea"
            />
          </div>
          
          {/* Common fields: Tags, Links, Status */}
          <div className="form-group">
            <label>🏷️ Теги</label>
            <TagsInput value={tags} onChange={setTags} />
          </div>
          
          <div className="form-group">
            <label>🔗 Ссылки</label>
            <LinksInput links={links} onChange={setLinks} />
          </div>
          
          {/* Attachments */}
          <div className="form-group">
            <label>📎 Вложения (до 50 МБ)</label>
            {note?.id ? (
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
          
          {/* Status & Pin */}
          <div className="form-row">
            <div className="form-group half">
              <label>📋 Статус</label>
              <StatusSelector value={status} onChange={setStatus} />
            </div>
            
            <div className="form-group half checkbox-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={isPinned}
                  onChange={e => setIsPinned(e.target.checked)}
                />
                <span>📌 Закрепить</span>
              </label>
            </div>
          </div>
          
          {/* Metadata */}
          {note?.id && (
            <MetadataDisplay 
              createdAt={note.created_at}
              updatedAt={note.updated_at}
            />
          )}
          
          <button type="submit" className="submit-button">
            {note ? 'Сохранить' : 'Создать'}
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

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru', { 
    day: 'numeric', 
    month: 'short',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
  })
}

export default NotesPage

