import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import './PageStyles.css'

function PasswordsPage() {
  const [passwords, setPasswords] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingPassword, setEditingPassword] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadPasswords()
  }, [])

  const loadPasswords = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/passwords', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      if (data.passwords) {
        setPasswords(data.passwords)
      }
    } catch (err) {
      console.error('Failed to load passwords:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (passwordId) => {
    WebApp.showConfirm('Удалить пароль?', async (confirmed) => {
      if (confirmed) {
        WebApp.HapticFeedback.notificationOccurred('warning')
        try {
          const response = await fetch(`/api/passwords/${passwordId}`, {
            method: 'DELETE',
            headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
          })
          if (response.ok) {
            loadPasswords()
          }
        } catch (err) {
          console.error('Failed to delete password:', err)
        }
      }
    })
  }

  const handleSave = async (passwordData) => {
    try {
      const url = editingPassword 
        ? `/api/passwords/${editingPassword.id}` 
        : '/api/passwords'
      const method = editingPassword ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify(passwordData)
      })
      
      if (response.ok) {
        WebApp.HapticFeedback.notificationOccurred('success')
        setShowForm(false)
        setEditingPassword(null)
        loadPasswords()
      }
    } catch (err) {
      console.error('Failed to save password:', err)
    }
  }

  const filteredPasswords = passwords.filter(pwd => 
    pwd.service_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    pwd.username.toLowerCase().includes(searchQuery.toLowerCase())
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
        <h1>🔐 Пароли</h1>
        <button 
          className="add-button"
          onClick={() => { setEditingPassword(null); setShowForm(true) }}
        >
          ＋
        </button>
      </header>

      {passwords.length > 0 && (
        <div className="search-bar">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="🔍 Поиск паролей..."
          />
        </div>
      )}

      <div className="items-list">
        {filteredPasswords.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">🔐</span>
            <p>{searchQuery ? 'Ничего не найдено' : 'Нет сохранённых паролей'}</p>
            {!searchQuery && (
              <button 
                className="empty-button"
                onClick={() => setShowForm(true)}
              >
                Добавить первый
              </button>
            )}
          </div>
        ) : (
          filteredPasswords.map(pwd => (
            <PasswordItem 
              key={pwd.id}
              password={pwd}
              onEdit={() => { setEditingPassword(pwd); setShowForm(true) }}
              onDelete={() => handleDelete(pwd.id)}
            />
          ))
        )}
      </div>

      {showForm && (
        <PasswordForm 
          password={editingPassword}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditingPassword(null) }}
        />
      )}
    </div>
  )
}

function PasswordItem({ password, onEdit, onDelete }) {
  const [showPassword, setShowPassword] = useState(false)
  const [copied, setCopied] = useState(null)

  const handleCopy = async (text, type) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(type)
      WebApp.HapticFeedback.notificationOccurred('success')
      setTimeout(() => setCopied(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="item-card password-card">
      <div className="item-content" onClick={onEdit}>
        <div className="item-title">
          {password.is_favorite && <span>⭐</span>}
          {password.service_name}
          {password.totp_secret && <span className="badge-2fa">2FA</span>}
        </div>
        
        <div className="password-details">
          <div className="password-field">
            <span className="field-label">👤</span>
            <span className="field-value">{password.username}</span>
            <button 
              className={`copy-button ${copied === 'user' ? 'copied' : ''}`}
              onClick={(e) => { e.stopPropagation(); handleCopy(password.username, 'user') }}
            >
              {copied === 'user' ? '✓' : '📋'}
            </button>
          </div>
          
          <div className="password-field">
            <span className="field-label">🔑</span>
            <span className="field-value password-hidden">
              {showPassword ? password.password : '••••••••'}
            </span>
            <button 
              className="show-button"
              onClick={(e) => { e.stopPropagation(); setShowPassword(!showPassword) }}
            >
              {showPassword ? '🙈' : '👁️'}
            </button>
            <button 
              className={`copy-button ${copied === 'pass' ? 'copied' : ''}`}
              onClick={(e) => { e.stopPropagation(); handleCopy(password.password, 'pass') }}
            >
              {copied === 'pass' ? '✓' : '📋'}
            </button>
          </div>
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

function PasswordForm({ password, onSave, onClose }) {
  const [serviceName, setServiceName] = useState(password?.service_name || '')
  const [username, setUsername] = useState(password?.username || '')
  const [pwd, setPwd] = useState(password?.password || '')
  const [url, setUrl] = useState(password?.url || '')
  const [notes, setNotes] = useState(password?.notes || '')
  const [showPassword, setShowPassword] = useState(false)

  const generatePassword = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    let result = ''
    for (let i = 0; i < 16; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    setPwd(result)
    setShowPassword(true)
    WebApp.HapticFeedback.impactOccurred('light')
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!serviceName.trim() || !username.trim() || !pwd.trim()) return
    
    onSave({
      service_name: serviceName.trim(),
      username: username.trim(),
      password: pwd.trim(),
      url: url.trim() || null,
      notes: notes.trim() || null
    })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{password ? 'Редактировать' : 'Новый пароль'}</h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>
        
        <form onSubmit={handleSubmit} className="form">
          <div className="form-group">
            <label>Сервис</label>
            <input
              type="text"
              value={serviceName}
              onChange={e => setServiceName(e.target.value)}
              placeholder="Название сайта/приложения"
              autoFocus
            />
          </div>
          
          <div className="form-group">
            <label>Логин/Email</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Ваш логин"
            />
          </div>
          
          <div className="form-group">
            <label>Пароль</label>
            <div className="password-input-group">
              <input
                type={showPassword ? 'text' : 'password'}
                value={pwd}
                onChange={e => setPwd(e.target.value)}
                placeholder="Пароль"
              />
              <button 
                type="button"
                className="input-action"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
              <button 
                type="button"
                className="input-action generate"
                onClick={generatePassword}
              >
                🎲
              </button>
            </div>
          </div>
          
          <div className="form-group">
            <label>URL сайта</label>
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://example.com"
            />
          </div>
          
          <div className="form-group">
            <label>Заметки</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Дополнительная информация..."
              rows={2}
            />
          </div>
          
          <button type="submit" className="submit-button">
            {password ? 'Сохранить' : 'Добавить'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default PasswordsPage

