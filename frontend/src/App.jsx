import { useCallback, useEffect, useState } from 'react';

import Header from './components/Header';
import DetailPage from './components/DetailPage';
import GeneratePage from './components/GeneratePage';
import HistoryPage from './components/HistoryPage';
import LoginPage from './components/LoginPage';
import AdminPage from './components/AdminPage';
import AccountPage from './components/AccountPage';
import { useApp } from './context/app-context';
import { pageFromPath, pathForPage } from './utils/routes';
import './App.css';

function App() {
  const { loadModels, loadSessions, loadSession, selectIdea } = useApp();
  const [currentPage, setCurrentPage] = useState(() => pageFromPath(window.location.pathname));

  useEffect(() => {
    const handlePopState = () => setCurrentPage(pageFromPath(window.location.pathname));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = useCallback((page, { replace = false } = {}) => {
    const path = pathForPage(page);
    window.history[replace ? 'replaceState' : 'pushState']({}, '', path);
    setCurrentPage(page);
  }, []);

  useEffect(() => {
    loadSessions();
    loadModels();
  }, [loadModels, loadSessions]);

  const openIdea = (index) => {
    if (selectIdea(index)) navigate('detail');
  };

  const openSession = async (sessionId) => {
    if (await loadSession(sessionId)) navigate('generate');
  };

  return (
    <div className="app-shell">
      <Header currentPage={currentPage} onPageChange={navigate} />
      <main className="main-content">
        {currentPage === 'login' && <LoginPage onComplete={() => navigate('generate', { replace: true })} />}
        {currentPage === 'admin' && <AdminPage />}
        {currentPage === 'account' && <AccountPage />}
        {currentPage === 'generate' && <GeneratePage onOpenIdea={openIdea} />}
        {currentPage === 'detail' && <DetailPage onBack={() => navigate('generate')} />}
        {currentPage === 'history' && <HistoryPage onOpenSession={openSession} />}
      </main>
    </div>
  );
}

export default App;
