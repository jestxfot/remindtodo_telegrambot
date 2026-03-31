import { useState } from 'react'
import WebApp from '@twa-dev/sdk'
import './FileViewer.css'

function FileViewer({ attachment, onClose }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  const fileUrl = `/api/attachments/${attachment.id}`
  const isImage = attachment.file_type?.startsWith('image/')
  const isVideo = attachment.file_type?.startsWith('video/')
  const isPdf = attachment.file_type === 'application/pdf'
  
  const handleLoad = () => setLoading(false)
  const handleError = () => {
    setLoading(false)
    setError('Не удалось загрузить файл')
  }
  
  const handleDownload = async () => {
    try {
      WebApp.HapticFeedback.impactOccurred('medium')
      const response = await fetch(fileUrl, {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = attachment.filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
    }
  }
  
  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="file-viewer-overlay" onClick={onClose}>
      <div className="file-viewer" onClick={e => e.stopPropagation()}>
        <div className="file-viewer-header">
          <div className="file-info">
            <span className="file-name">{attachment.filename}</span>
            <span className="file-size">{formatSize(attachment.file_size)}</span>
          </div>
          <div className="file-actions">
            <button className="download-btn" onClick={handleDownload}>⬇️</button>
            <button className="close-btn" onClick={onClose}>✕</button>
          </div>
        </div>
        
        <div className="file-viewer-content">
          {loading && (
            <div className="file-loading">
              <div className="loading-spinner"></div>
            </div>
          )}
          
          {error && (
            <div className="file-error">
              <span>⚠️</span>
              <p>{error}</p>
            </div>
          )}
          
          {isImage && (
            <img 
              src={`${fileUrl}?init_data=${encodeURIComponent(WebApp.initData || '')}`}
              alt={attachment.filename}
              onLoad={handleLoad}
              onError={handleError}
              style={{ display: loading ? 'none' : 'block' }}
            />
          )}
          
          {isVideo && (
            <video 
              controls 
              autoPlay
              onLoadedData={handleLoad}
              onError={handleError}
              style={{ display: loading ? 'none' : 'block' }}
            >
              <source src={`${fileUrl}?init_data=${encodeURIComponent(WebApp.initData || '')}`} type={attachment.file_type} />
            </video>
          )}
          
          {isPdf && (
            <iframe
              src={`${fileUrl}?init_data=${encodeURIComponent(WebApp.initData || '')}`}
              title={attachment.filename}
              onLoad={handleLoad}
              onError={handleError}
              style={{ display: loading ? 'none' : 'block' }}
            />
          )}
          
          {!isImage && !isVideo && !isPdf && (
            <div className="file-unsupported">
              <span className="file-icon">📄</span>
              <p>Предпросмотр недоступен</p>
              <button onClick={handleDownload}>Скачать файл</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function AttachmentList({ attachments, onView, onDelete, canDelete = true }) {
  if (!attachments || attachments.length === 0) return null
  
  const getIcon = (fileType) => {
    if (fileType?.startsWith('image/')) return '🖼️'
    if (fileType?.startsWith('video/')) return '🎬'
    if (fileType === 'application/pdf') return '📕'
    return '📎'
  }
  
  const formatSize = (bytes) => {
    if (!bytes) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="attachment-list">
      {attachments.map(att => (
        <div key={att.id} className="attachment-item">
          <div className="attachment-preview" onClick={() => onView?.(att)}>
            <span className="attachment-icon">{getIcon(att.file_type)}</span>
          </div>
          <div className="attachment-info" onClick={() => onView?.(att)}>
            <span className="attachment-name">{att.filename}</span>
            <span className="attachment-size">{formatSize(att.file_size)}</span>
          </div>
          {canDelete && (
            <button 
              className="attachment-delete"
              onClick={(e) => { e.stopPropagation(); onDelete?.(att.id) }}
            >
              ✕
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

export function AttachmentUpload({ onUpload, maxSize = 50 * 1024 * 1024 }) {
  const [uploading, setUploading] = useState(false)
  
  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    if (file.size > maxSize) {
      WebApp.showAlert(`Файл слишком большой. Максимум ${maxSize / (1024 * 1024)}MB`)
      return
    }
    
    setUploading(true)
    WebApp.HapticFeedback.impactOccurred('light')
    
    try {
      // Read file as base64
      const reader = new FileReader()
      reader.onload = async () => {
        const base64 = reader.result.split(',')[1]
        await onUpload({
          file_data: base64,
          filename: file.name,
          file_type: file.type || 'application/octet-stream'
        })
        setUploading(false)
        WebApp.HapticFeedback.notificationOccurred('success')
      }
      reader.onerror = () => {
        setUploading(false)
        WebApp.showAlert('Ошибка чтения файла')
      }
      reader.readAsDataURL(file)
    } catch (err) {
      setUploading(false)
      console.error('Upload failed:', err)
    }
    
    e.target.value = '' // Reset input
  }

  return (
    <label className={`attachment-upload ${uploading ? 'uploading' : ''}`}>
      <input 
        type="file" 
        onChange={handleFileSelect}
        accept="image/*,video/*,application/pdf,.doc,.docx,.xls,.xlsx,.txt"
        disabled={uploading}
      />
      {uploading ? (
        <span className="upload-loading">⏳</span>
      ) : (
        <span className="upload-icon">📎</span>
      )}
      <span className="upload-text">{uploading ? 'Загрузка...' : 'Прикрепить файл'}</span>
    </label>
  )
}

export default FileViewer

