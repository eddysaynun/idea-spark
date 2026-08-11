import React, { useEffect, useState } from 'react';
import { useApp } from './context/AppContext';
import { Sparkles, FileText, History, Settings, Zap } from 'lucide-react';
import Header from './components/Header';
import WelcomePage from './components/WelcomePage';
import GeneratePage from './components/GeneratePage';
import DetailPage from './components/DetailPage';
import HistoryPage from './components/HistoryPage';
import SettingsPage from './components/SettingsPage';
import './App.css';

function App() {
  const { loadConfig } = useApp();
  const [currentPage, setCurrentPage] = useState('welcome');

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const renderPage = () => {
    switch (currentPage) {
      case 'welcome':
        return <WelcomePage onGetStarted={() => setCurrentPage('generate')} />;
      case 'generate':
        return <GeneratePage />;
      case 'detail':
        return <DetailPage />;
      case 'history':
        return <HistoryPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <WelcomePage onGetStarted={() => setCurrentPage('generate')} />;
    }
  };

  return (
    <div className="app-container">
      <Header currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className="main-content">
        <div className="page">
          {renderPage()}
        </div>
      </main>
    </div>
  );
}

export default App;
