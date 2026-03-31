/**
 * Общие компоненты для заметок и напоминаний
 * - Теги
 * - Ссылки  
 * - Статус
 * - Метаданные
 * - Вложения
 */

import { useState } from 'react'
import WebApp from '@twa-dev/sdk'
import './ItemFields.css'

// ============ STATUS ============

export const STATUS_OPTIONS = [
  { value: 'active', label: '✓ Активно', color: '#22c55e' },
  { value: 'draft', label: '📝 Черновик', color: '#eab308' },
  { value: 'archived', label: '🗃️ В архиве', color: '#6b7280' },
]

export function StatusBadge({ status }) {
  const opt = STATUS_OPTIONS.find(s => s.value === status) || STATUS_OPTIONS[0]
  return (
    <span className="status-badge" style={{ backgroundColor: `${opt.color}20`, color: opt.color }}>
      {opt.label}
    </span>
  )
}

export function StatusSelector({ value, onChange }) {
  return (
    <div className="status-selector">
      {STATUS_OPTIONS.map(opt => (
        <button
          key={opt.value}
          type="button"
          className={`status-option ${value === opt.value ? 'selected' : ''}`}
          style={{ '--status-color': opt.color }}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ============ TAGS ============

export function TagsDisplay({ tags, maxShow = 4 }) {
  if (!tags || tags.length === 0) return null
  
  return (
    <div className="tags-display">
      {tags.slice(0, maxShow).map((tag, i) => (
        <span key={i} className="tag-chip">#{tag}</span>
      ))}
      {tags.length > maxShow && (
        <span className="tag-more">+{tags.length - maxShow}</span>
      )}
    </div>
  )
}

export function TagsInput({ value, onChange, placeholder = "работа, идеи, важное" }) {
  return (
    <div className="tags-input-wrapper">
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="tags-input"
      />
      <span className="tags-hint">Через запятую</span>
    </div>
  )
}

export function parseTags(tagsString) {
  return tagsString
    .split(',')
    .map(t => t.trim().replace(/^#/, ''))
    .filter(t => t.length > 0)
}

// ============ LINKS ============

// Check if URL is a Telegram link
const isTelegramLink = (url) => {
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    return hostname === 't.me' || hostname === 'telegram.me' || hostname === 'telegram.dog'
  } catch {
    return false
  }
}

// Open link with appropriate method
const openLink = (url) => {
  if (isTelegramLink(url)) {
    WebApp.openTelegramLink(url)
  } else {
    WebApp.openLink(url)
  }
}

export function LinksDisplay({ links, maxShow = 2, onLinkClick }) {
  if (!links || links.length === 0) return null
  
  const handleClick = (e, url) => {
    e.preventDefault()
    e.stopPropagation()
    if (onLinkClick) {
      onLinkClick(url)
    } else {
      openLink(url)
    }
  }
  
  const getHostname = (url) => {
    try {
      return new URL(url).hostname
    } catch {
      return url
    }
  }
  
  const getLinkIcon = (url) => {
    if (isTelegramLink(url)) return '✈️'
    return '🔗'
  }
  
  return (
    <div className="links-display">
      {links.slice(0, maxShow).map((link, i) => (
        <a 
          key={i}
          href={link}
          className={`link-chip ${isTelegramLink(link) ? 'telegram-link' : ''}`}
          onClick={(e) => handleClick(e, link)}
        >
          {getLinkIcon(link)} {getHostname(link)}
        </a>
      ))}
      {links.length > maxShow && (
        <span className="link-more">+{links.length - maxShow}</span>
      )}
    </div>
  )
}

export function LinksInput({ links, onChange }) {
  const [newLink, setNewLink] = useState('')
  
  const handleAdd = () => {
    if (!newLink.trim()) return
    let url = newLink.trim()
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'https://' + url
    }
    try {
      new URL(url) // Validate
      onChange([...links, url])
      setNewLink('')
    } catch {
      WebApp.showAlert('Неверный формат ссылки')
    }
  }
  
  const handleRemove = (index) => {
    onChange(links.filter((_, i) => i !== index))
  }
  
  const getHostname = (url) => {
    try {
      return new URL(url).hostname
    } catch {
      return url
    }
  }
  
  return (
    <div className="links-input-wrapper">
      <div className="link-add-row">
        <input
          type="text"
          value={newLink}
          onChange={e => setNewLink(e.target.value)}
          placeholder="https://example.com или t.me/..."
          onKeyPress={e => e.key === 'Enter' && (e.preventDefault(), handleAdd())}
        />
        <button type="button" className="link-add-btn" onClick={handleAdd}>+</button>
      </div>
      
      {links.length > 0 && (
        <div className="links-list">
          {links.map((link, i) => (
            <div key={i} className={`link-item ${isTelegramLink(link) ? 'telegram' : ''}`}>
              <a 
                href={link} 
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); openLink(link) }}
              >
                {isTelegramLink(link) ? '✈️' : '🔗'} {getHostname(link)}
              </a>
              <button type="button" onClick={(e) => { e.stopPropagation(); handleRemove(i) }}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ============ METADATA ============

export function MetadataDisplay({ createdAt, updatedAt, extraInfo }) {
  const formatDateTime = (dateStr) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    return date.toLocaleDateString('ru', { 
      day: 'numeric', 
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    })
  }
  
  const isEdited = createdAt !== updatedAt
  
  return (
    <div className="metadata-display">
      <span>📅 Создано: {formatDateTime(createdAt)}</span>
      {isEdited && <span>✏️ Изменено: {formatDateTime(updatedAt)}</span>}
      {extraInfo && extraInfo.map((info, i) => (
        <span key={i}>{info}</span>
      ))}
    </div>
  )
}

// ============ ATTACHMENTS BADGES ============

export function AttachmentsBadges({ attachments, onView, maxShow = 3 }) {
  if (!attachments || attachments.length === 0) return null
  
  const getIcon = (fileType) => {
    if (fileType?.startsWith('image/')) return '🖼️'
    if (fileType?.startsWith('video/')) return '🎬'
    if (fileType === 'application/pdf') return '📕'
    return '📎'
  }
  
  return (
    <div className="attachments-badges">
      {attachments.slice(0, maxShow).map(att => (
        <span 
          key={att.id} 
          className="attachment-badge"
          onClick={(e) => { e.stopPropagation(); onView?.(att) }}
          title={att.filename}
        >
          {getIcon(att.file_type)}
        </span>
      ))}
      {attachments.length > maxShow && (
        <span className="attachment-badge more">+{attachments.length - maxShow}</span>
      )}
    </div>
  )
}

// ============ ITEM INDICATORS ============

export function ItemIndicators({ 
  hasAttachments, 
  hasLinks, 
  hasTags,
  isPinned,
  isRecurring,
  isPersistent,
  status 
}) {
  return (
    <div className="item-indicators">
      {isPinned && <span title="Закреплено">📌</span>}
      {isRecurring && <span title="Повторяется">🔄</span>}
      {isPersistent && <span title="Постоянное">🔊</span>}
      {hasAttachments && <span title="Вложения">📎</span>}
      {hasLinks && <span title="Ссылки">🔗</span>}
      {status === 'draft' && <span className="draft-indicator">черновик</span>}
    </div>
  )
}

// ============ COMMON FORM SECTION ============

export function CommonFieldsSection({ 
  tags, 
  setTags, 
  links, 
  setLinks, 
  status, 
  setStatus,
  showStatus = true 
}) {
  return (
    <div className="common-fields-section">
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
      
      {/* Status */}
      {showStatus && (
        <div className="form-group">
          <label>📋 Статус</label>
          <StatusSelector value={status} onChange={setStatus} />
        </div>
      )}
    </div>
  )
}

export default {
  STATUS_OPTIONS,
  StatusBadge,
  StatusSelector,
  TagsDisplay,
  TagsInput,
  parseTags,
  LinksDisplay,
  LinksInput,
  MetadataDisplay,
  AttachmentsBadges,
  ItemIndicators,
  CommonFieldsSection,
  isTelegramLink,
  openLink
}

