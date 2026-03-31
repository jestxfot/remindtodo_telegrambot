import WebApp from '@twa-dev/sdk'
import './Navigation.css'

const tabs = [
  { id: 'tasks', icon: '📋', label: 'Задачи' },
  { id: 'reminders', icon: '🔔', label: 'Напом.' },
  { id: 'notes', icon: '📝', label: 'Заметки' },
  { id: 'passwords', icon: '🔐', label: 'Пароли' },
  { id: 'calendar', icon: '📅', label: 'Календ.' },
  { id: 'archive', icon: '🗃️', label: 'Архив' },
  { id: 'settings', icon: '⚙️', label: '...' },
]

function Navigation({ currentPage, onPageChange }) {
  const handleTabClick = (tabId) => {
    if (tabId !== currentPage) {
      WebApp.HapticFeedback.selectionChanged()
      onPageChange(tabId)
    }
  }

  return (
    <nav className="navigation">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`nav-tab ${currentPage === tab.id ? 'active' : ''}`}
          onClick={() => handleTabClick(tab.id)}
        >
          <span className="nav-icon">{tab.icon}</span>
          <span className="nav-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}

export default Navigation

