import React from 'react';
import { Sparkles, Home, Zap, History, Settings } from 'lucide-react';
import './Header.css';

const Header = ({ currentPage, onPageChange }) => {
  const navItems = [
    { id: 'welcome', label: '首页', icon: Home },
    { id: 'generate', label: '生成', icon: Zap },
    { id: 'history', label: '历史', icon: History },
    { id: 'settings', label: '设置', icon: Settings },
  ];

  return (
    <header className="header">
      <a href="#" className="header-logo" onClick={(e) => { e.preventDefault(); onPageChange('welcome'); }}>
        <div className="header-logo-icon">
          <Sparkles size={20} />
        </div>
        <span>Idea Spark</span>
      </a>

      <nav className="header-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`header-nav-item ${currentPage === item.id ? 'active' : ''}`}
              onClick={() => onPageChange(item.id)}
            >
              <Icon size={16} className="nav-icon" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
};

export default Header;
