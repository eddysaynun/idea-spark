import { Archive, CircleUserRound, LogIn, LogOut, Sparkles } from 'lucide-react';

import { useApp } from '../context/app-context';

import './Header.css';

const Header = ({ currentPage, onPageChange }) => {
  const { user, logout } = useApp();
  const items = [
    { id: 'generate', label: '工作台', icon: Sparkles },
    { id: 'history', label: '历史', icon: Archive },
    ...(user ? [{ id: 'account', label: '账户', icon: CircleUserRound }] : []),
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
      <div className="account-control">
        {user ? <>
          <button className="quota-shortcut" onClick={() => onPageChange('account')} aria-label="查看剩余额度">
            <span>{Math.max(0, user.quota.idea.limit - user.quota.idea.used - user.quota.idea.reserved)} Idea</span>
            <span>{Math.max(0, user.quota.detail.limit - user.quota.detail.used - user.quota.detail.reserved)} 方案</span>
          </button>
          <span>{user.display_name}</span><button onClick={logout} aria-label="退出登录"><LogOut size={16} /></button>
        </> : <button onClick={() => onPageChange('login')}><LogIn size={16} /> 登录</button>}
      </div>
    </header>
  );
};

export default Header;
