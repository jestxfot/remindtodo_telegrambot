import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import './UnlockScreen.css'

const SESSION_DURATION_OPTIONS = [
  { value: '30min', label: '30 минут' },
  { value: '2hours', label: '2 часа' },
  { value: '1day', label: '1 день' },
  { value: '1week', label: '1 неделя' },
  { value: '1month', label: '1 месяц' },
]

function UnlockScreen({ onUnlock, user }) {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isNewUser, setIsNewUser] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [rememberMe, setRememberMe] = useState(true)
  const [sessionDuration, setSessionDuration] = useState('1day')

  // Check if user has password on mount
  useEffect(() => {
    checkUserStatus()
  }, [])

  const checkUserStatus = async () => {
    try {
      const response = await fetch('/api/auth/status', {
        headers: {
          'X-Telegram-Init-Data': WebApp.initData || ''
        }
      })
      const data = await response.json()
      setIsNewUser(!data.has_password)
    } catch (err) {
      console.error('Failed to check status:', err)
      setIsNewUser(true) // Assume new user on error
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    if (isNewUser && password !== confirmPassword) {
      setError('Пароли не совпадают')
      WebApp.HapticFeedback.notificationOccurred('error')
      return
    }
    
    if (password.length < 4) {
      setError('Минимум 4 символа')
      WebApp.HapticFeedback.notificationOccurred('error')
      return
    }
    
    setLoading(true)
    
    try {
      const endpoint = isNewUser ? '/api/auth/create' : '/api/auth/unlock'
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify({ 
          password,
          duration: rememberMe ? sessionDuration : '30min'
        })
      })
      
      const data = await response.json()
      
      if (response.ok && data.success) {
        onUnlock(true)
      } else {
        setError(data.message || 'Неверный пароль')
        WebApp.HapticFeedback.notificationOccurred('error')
      }
    } catch (err) {
      setError('Ошибка подключения')
      WebApp.HapticFeedback.notificationOccurred('error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="unlock-screen">
      <div className="unlock-container">
        <div className="unlock-icon">🔐</div>
        
        <h1 className="unlock-title">
          {isNewUser ? 'Создайте мастер-пароль' : 'Введите пароль'}
        </h1>
        
        {user && (
          <p className="unlock-greeting">
            Привет, {user.first_name || 'друг'}!
          </p>
        )}
        
        <p className="unlock-description">
          {isNewUser 
            ? 'Этот пароль защитит все ваши данные. Запомните его — восстановить невозможно!'
            : 'Разблокируйте хранилище для доступа к данным'
          }
        </p>
        
        <form onSubmit={handleSubmit} className="unlock-form">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Пароль"
            className="unlock-input"
            autoFocus
            disabled={loading}
          />
          
          {isNewUser && (
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Повторите пароль"
              className="unlock-input"
              disabled={loading}
            />
          )}
          
          {/* Remember me section */}
          <div className="remember-section">
            <label className="remember-checkbox">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              <span>Запомнить меня</span>
            </label>
            
            {rememberMe && (
              <select 
                value={sessionDuration}
                onChange={(e) => setSessionDuration(e.target.value)}
                className="duration-select"
              >
                {SESSION_DURATION_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            )}
          </div>
          
          {error && <p className="unlock-error">{error}</p>}
          
          <button 
            type="submit" 
            className="unlock-button"
            disabled={loading || !password}
          >
            {loading ? 'Загрузка...' : (isNewUser ? 'Создать' : 'Разблокировать')}
          </button>
        </form>
        
        <p className="unlock-hint">
          🔒 AES-256-GCM шифрование
        </p>
      </div>
    </div>
  )
}

export default UnlockScreen

