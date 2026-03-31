import { useState, useEffect } from 'react'
import WebApp from '@twa-dev/sdk'
import './PageStyles.css'

function SettingsPage({ user, onLogout }) {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState(null)
  const [session, setSession] = useState(null)
  const [showDurationPicker, setShowDurationPicker] = useState(false)
  const [reminderIntervalMinutes, setReminderIntervalMinutes] = useState('5')
  const [savingInterval, setSavingInterval] = useState(false)

  useEffect(() => {
    loadSettings()
    loadStats()
    loadSession()
  }, [])

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/settings', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      setSettings(data)
      setReminderIntervalMinutes(String(data.reminder_interval_minutes ?? 5))
    } catch (err) {
      console.error('Failed to load settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await fetch('/api/stats', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      setStats(data)
    } catch (err) {
      console.error('Failed to load stats:', err)
    }
  }

  const loadSession = async () => {
    try {
      const response = await fetch('/api/session', {
        headers: { 'X-Telegram-Init-Data': WebApp.initData || '' }
      })
      const data = await response.json()
      setSession(data)
    } catch (err) {
      console.error('Failed to load session:', err)
    }
  }

  const handleChangeDuration = async (durationKey) => {
    try {
      WebApp.HapticFeedback.impactOccurred('medium')
      const response = await fetch('/api/session/duration', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify({ duration: durationKey })
      })
      const data = await response.json()
      if (data.success) {
        setSession(data.session)
        WebApp.HapticFeedback.notificationOccurred('success')
      }
    } catch (err) {
      console.error('Failed to update session:', err)
    }
    setShowDurationPicker(false)
  }

  const handleLock = () => {
    WebApp.showConfirm('Заблокировать хранилище?', (confirmed) => {
      if (confirmed) {
        onLogout()
      }
    })
  }

  const handleChangePassword = () => {
    WebApp.showAlert('Для смены пароля используйте команду /changepassword в боте')
  }

  const handleReminderIntervalSave = async () => {
    const interval = parseInt(reminderIntervalMinutes, 10)
    if (!Number.isFinite(interval) || interval < 1) {
      WebApp.showAlert('Укажите интервал в минутах, минимум 1')
      return
    }

    setSavingInterval(true)
    try {
      WebApp.HapticFeedback.impactOccurred('medium')
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': WebApp.initData || ''
        },
        body: JSON.stringify({ reminder_interval_minutes: interval })
      })
      const data = await response.json()
      if (response.ok) {
        setSettings(data)
        setReminderIntervalMinutes(String(data.reminder_interval_minutes ?? interval))
        WebApp.HapticFeedback.notificationOccurred('success')
      } else {
        WebApp.showAlert(data.error || 'Не удалось сохранить настройку')
      }
    } catch (err) {
      console.error('Failed to update reminder interval:', err)
      WebApp.showAlert('Ошибка сохранения настройки')
    } finally {
      setSavingInterval(false)
    }
  }

  const formatRemainingTime = (minutes) => {
    if (minutes < 60) return `${minutes} мин`
    if (minutes < 1440) return `${Math.floor(minutes / 60)} ч`
    return `${Math.floor(minutes / 1440)} дн`
  }

  if (loading) {
    return (
      <div className="page-loading">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  return (
    <div className="page settings-page">
      <header className="page-header">
        <h1>⚙️ Настройки</h1>
      </header>

      {/* User Info */}
      <section className="settings-section">
        <h2 className="section-title">👤 Профиль</h2>
        <div className="settings-card">
          <div className="user-info">
            {user?.photo_url ? (
              <img src={user.photo_url} alt="" className="user-avatar" />
            ) : (
              <div className="user-avatar-placeholder">
                {(user?.first_name || 'U')[0]}
              </div>
            )}
            <div className="user-details">
              <span className="user-name">
                {user?.first_name} {user?.last_name || ''}
              </span>
              {user?.username && (
                <span className="user-username">@{user.username}</span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Statistics */}
      {stats && (
        <section className="settings-section">
          <h2 className="section-title">📊 Статистика</h2>
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-value">{stats.todos?.total || 0}</span>
              <span className="stat-label">Задач</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.todos?.completed || 0}</span>
              <span className="stat-label">Выполнено</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.reminders?.pending || 0}</span>
              <span className="stat-label">Напоминаний</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.notes || 0}</span>
              <span className="stat-label">Заметок</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.passwords || 0}</span>
              <span className="stat-label">Паролей</span>
            </div>
          </div>
        </section>
      )}

      {/* Session */}
      {session?.active && (
        <section className="settings-section">
          <h2 className="section-title">⏱️ Сессия</h2>
          <div className="settings-list">
            <div className="settings-item info">
              <span className="settings-item-icon">⏳</span>
              <span className="settings-item-text">Осталось</span>
              <span className="settings-item-value">{formatRemainingTime(session.remaining_minutes)}</span>
            </div>
            
            <button className="settings-item" onClick={() => setShowDurationPicker(true)}>
              <span className="settings-item-icon">🕐</span>
              <span className="settings-item-text">Длительность</span>
              <span className="settings-item-value">{session.duration_label}</span>
              <span className="settings-item-arrow">›</span>
            </button>
          </div>
        </section>
      )}

      {/* Security */}
      <section className="settings-section">
        <h2 className="section-title">🔐 Безопасность</h2>
        <div className="settings-list">
          <button className="settings-item" onClick={handleLock}>
            <span className="settings-item-icon">🔒</span>
            <span className="settings-item-text">Заблокировать</span>
            <span className="settings-item-arrow">›</span>
          </button>
          
          <button className="settings-item" onClick={handleChangePassword}>
            <span className="settings-item-icon">🔑</span>
            <span className="settings-item-text">Сменить пароль</span>
            <span className="settings-item-arrow">›</span>
          </button>
        </div>
      </section>

      <section className="settings-section">
        <h2 className="section-title">🔔 Напоминания</h2>
        <div className="settings-card">
          <div className="form-group">
            <label>Интервал повторных уведомлений</label>
            <div className="interval-input">
              <span>Каждые</span>
              <input
                type="number"
                min="1"
                step="1"
                value={reminderIntervalMinutes}
                onChange={e => setReminderIntervalMinutes(e.target.value)}
                className="interval-number"
              />
              <span>минут</span>
            </div>
            <p className="duration-hint">
              Значение по умолчанию для новых напоминаний и сразу для всех текущих постоянных напоминаний.
            </p>
            <button
              type="button"
              className="submit-button"
              onClick={handleReminderIntervalSave}
              disabled={savingInterval}
            >
              {savingInterval ? 'Сохранение...' : 'Сохранить интервал'}
            </button>
          </div>
        </div>
      </section>

      {/* Info */}
      <section className="settings-section">
        <h2 className="section-title">ℹ️ Информация</h2>
        <div className="settings-list">
          <div className="settings-item info">
            <span className="settings-item-icon">🛡️</span>
            <span className="settings-item-text">Шифрование</span>
            <span className="settings-item-value">AES-256-GCM</span>
          </div>
          
          <div className="settings-item info">
            <span className="settings-item-icon">🌍</span>
            <span className="settings-item-text">Часовой пояс</span>
            <span className="settings-item-value">{settings?.timezone || 'Europe/Moscow'}</span>
          </div>

          <div className="settings-item info">
            <span className="settings-item-icon">🔁</span>
            <span className="settings-item-text">Повтор уведомлений</span>
            <span className="settings-item-value">{settings?.reminder_interval_minutes || 5} мин</span>
          </div>
        </div>
      </section>

      {/* Version */}
      <div className="app-version">
        <p>Reminder Bot v2.0</p>
        <p className="version-hint">Telegram Mini App</p>
      </div>

      {/* Duration Picker Modal */}
      {showDurationPicker && session?.available_durations && (
        <div className="modal-overlay" onClick={() => setShowDurationPicker(false)}>
          <div className="modal duration-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Длительность сессии</h2>
              <button className="close-button" onClick={() => setShowDurationPicker(false)}>✕</button>
            </div>
            <div className="duration-options">
              {session.available_durations.map(opt => (
                <button
                  key={opt.key}
                  className={`duration-option ${session.duration_key === opt.key ? 'active' : ''}`}
                  onClick={() => handleChangeDuration(opt.key)}
                >
                  <span className="duration-label">{opt.label}</span>
                  {session.duration_key === opt.key && <span className="duration-check">✓</span>}
                </button>
              ))}
            </div>
            <p className="duration-hint">
              Выберите, как долго сессия остаётся активной без повторного ввода пароля
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default SettingsPage
