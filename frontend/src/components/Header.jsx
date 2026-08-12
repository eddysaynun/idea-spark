import { Archive, Settings, Sparkles } from 'lucide-react';

import './Header.css';

const Header = ({ currentPage, onPageChange }) => {
  const items = [
    { id: 'generate', label: '工作台', icon: Sparkles },
    { id: 'history', label: '历史', icon: Archive },
    { id: 'settings', label: '模型设置', icon: Settings },
  ];

  return (
    <header className="header">
      <button className="brand" onClick={() => onPageChange('generate')} aria-label="返回 Idea Spark 工作台">
        <img className="brand-mark" src="/favicon.svg" alt="" />
        <span>Idea Spark</span>
        <span className="brand-version">LAB</span>
      </button>
      <nav className="header-nav" aria-label="主导航">
        {items.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={currentPage === id || (id === 'generate' && currentPage === 'detail') ? 'active' : ''}
            onClick={() => onPageChange(id)}
            aria-label={label}
            aria-current={currentPage === id ? 'page' : undefined}
          >
            <Icon size={16} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </header>
  );
};

export default Header;
