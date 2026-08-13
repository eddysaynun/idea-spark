import { useEffect, useState } from 'react';

import Header from './components/Header';
import DetailPage from './components/DetailPage';
import GeneratePage from './components/GeneratePage';
import HistoryPage from './components/HistoryPage';
import LoginPage from './components/LoginPage';
import AdminPage from './components/AdminPage';
import AccountPage from './components/AccountPage';
import { useApp } from './context/app-context';
import './App.css';

function App() {
  const { loadModels, loadSessions, loadSession, selectIdea } = useApp();
  const [currentPage, setCurrentPage] = useState('generate');

  useEffect(() => {
    if (window.location.pathname === '/admin') {
      setCurrentPage('admin');
    } else if (window.location.pathname === '/account') {
      setCurrentPage('account');
    } else if (window.location.pathname === '/login' || window.location.pathname === '/auth/callback') {
      setCurrentPage('login');
    }
  }, []);

  useEffect(() => {
    loadSessions();
    loadModels();
  }, [loadModels, loadSessions]);

  const openIdea = (index) => {
    if (selectIdea(index)) setCurrentPage('detail');
  };

  const openSession = async (sessionId) => {
    if (await loadSession(sessionId)) setCurrentPage('generate');
  };

  return (
    <div className="app-shell">
      <Header currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className="main-content">
        {currentPage === 'login' && <LoginPage onComplete={() => setCurrentPage('generate')} />}
        {currentPage === 'admin' && <AdminPage />}
        {currentPage === 'account' && <AccountPage />}
        {currentPage === 'generate' && <GeneratePage onOpenIdea={openIdea} />}
        {currentPage === 'detail' && <DetailPage onBack={() => setCurrentPage('generate')} />}
        {currentPage === 'history' && <HistoryPage onOpenSession={openSession} />}
      </main>
    </div>
  );
}

export default App;
