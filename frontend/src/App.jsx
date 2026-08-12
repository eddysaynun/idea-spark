import { useEffect, useState } from 'react';

import Header from './components/Header';
import DetailPage from './components/DetailPage';
import GeneratePage from './components/GeneratePage';
import HistoryPage from './components/HistoryPage';
import { useApp } from './context/app-context';
import './App.css';

function App() {
  const { loadModels, loadSessions, loadSession, selectIdea } = useApp();
  const [currentPage, setCurrentPage] = useState('generate');

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
        {currentPage === 'generate' && <GeneratePage onOpenIdea={openIdea} />}
        {currentPage === 'detail' && <DetailPage onBack={() => setCurrentPage('generate')} />}
        {currentPage === 'history' && <HistoryPage onOpenSession={openSession} />}
      </main>
    </div>
  );
}

export default App;
