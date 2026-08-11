import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { logger } from '../utils/logger';

const AppContext = createContext();

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};

export const AppProvider = ({ children }) => {
  const [config, setConfig] = useState({
    provider: 'hermes',
    hermes_url: 'http://localhost:8080/api/chat',
    temperature: 0.7,
  });

  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState({
    percent: 0,
    step: '',
    message: '',
    thinking_preview: null,
    content_preview: null,
  });

  const [currentSession, setCurrentSession] = useState(null);
  const [ideas, setIdeas] = useState([]);
  const [sessions, setSessions] = useState([]);

  // 从 localStorage 恢复数据
  useEffect(() => {
    try {
      const savedIdeas = localStorage.getItem('idea_generator_ideas');
      const savedSession = localStorage.getItem('idea_generator_session');
      const savedProgress = localStorage.getItem('idea_generator_progress');
      
      if (savedIdeas) setIdeas(JSON.parse(savedIdeas));
      if (savedSession) setCurrentSession(JSON.parse(savedSession));
      if (savedProgress) setProgress(JSON.parse(savedProgress));
      
      logger.info('Data restored from localStorage');
    } catch (error) {
      logger.error('Failed to restore data from localStorage:', error);
    }
  }, []);

  // 保存到 localStorage
  const saveToLocalStorage = useCallback((data) => {
    try {
      if (data.ideas) localStorage.setItem('idea_generator_ideas', JSON.stringify(data.ideas));
      if (data.session) localStorage.setItem('idea_generator_session', JSON.stringify(data.session));
      if (data.progress) localStorage.setItem('idea_generator_progress', JSON.stringify(data.progress));
    } catch (error) {
      logger.error('Failed to save to localStorage:', error);
    }
  }, []);

  // 加载配置
  const loadConfig = useCallback(async () => {
    try {
      logger.info('Loading configuration...');
      const { configAPI } = await import('../api');
      const data = await configAPI.getConfig();
      if (data.success) {
        setConfig(data.config);
        logger.info('Configuration loaded successfully', data.config);
      }
    } catch (error) {
      logger.error('Failed to load config:', error);
    }
  }, []);

  // 保存配置
  const saveConfig = useCallback(async (newConfig) => {
    try {
      const { configAPI } = await import('../api');
      const data = await configAPI.updateConfig(newConfig);
      if (data.success) {
        setConfig(data.config);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to save config:', error);
      return false;
    }
  }, []);

  // 加载会话列表
  const loadSessions = useCallback(async () => {
    try {
      const { sessionAPI } = await import('../api');
      const data = await sessionAPI.listSessions();
      if (data.success) {
        setSessions(data.sessions);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }, []);

  // 生成 Ideas (流式)
  const generateIdeas = useCallback(async (direction, count, category) => {
    setIsGenerating(true);
    setProgress({ percent: 0, step: '', message: '', thinking_preview: null, content_preview: null });
    
    try {
      logger.info(`Starting idea generation: ${direction}, count=${count}, category=${category}`);
      
      // 使用流式 API
      const url = `http://localhost:3001/api/generate-stream?direction=${encodeURIComponent(direction)}&count=${count}&category=${category}`;
      const response = await fetch(url);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      let collectedIdeas = [];
      let sessionId = '';
      let fullReasoning = '';
      let fullText = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'start':
                  logger.info('Stream started');
                  break;
                  
                case 'progress':
                  const { step, progress, message } = data.data;
                  setProgress({
                    percent: progress,
                    step: step,
                    message: message,
                    thinking_preview: fullReasoning, // 保留全量 thinking
                    content_preview: fullText // 保留全量 content
                  });
                  logger.info(`Progress: ${step} (${progress}%)`);
                  break;
                  
                case 'reasoning':
                  fullReasoning += data.data;
                  // 保留全量 thinking 内容
                  setProgress(prev => ({
                    ...prev,
                    thinking_preview: fullReasoning
                  }));
                  break;
                  
                case 'text':
                  fullText += data.data;
                  // 保留全量 content 内容
                  setProgress(prev => ({
                    ...prev,
                    content_preview: fullText
                  }));
                  break;
                  
                case 'idea':
                  collectedIdeas.push(data.data);
                  logger.info(`Received idea ${data.index}: ${data.data.name}`);
                  break;
                  
                case 'complete':
                  sessionId = data.data.session_id || `session-${Date.now()}`;
                  setIdeas(collectedIdeas);
                  setCurrentSession(sessionId);
                  setProgress({ percent: 100, step: '完成', message: '生成完成!', thinking_preview: null, content_preview: null });
                  
                  // 保存到 localStorage
                  saveToLocalStorage({
                    ideas: collectedIdeas,
                    session: sessionId,
                    progress: { percent: 100, step: '完成', message: '生成完成!' }
                  });
                  
                  logger.info(`Stream completed: ${collectedIdeas.length} ideas`);
                  break;
                  
                case 'error':
                  logger.error(`Stream error: ${data.data.message}`);
                  // 保存错误状态到 localStorage
                  saveToLocalStorage({
                    ideas: collectedIdeas,
                    session: sessionId || `session-${Date.now()}`,
                    progress: { percent: 0, step: '失败', message: data.data.message }
                  });
                  throw new Error(data.data.message);
              }
            } catch (e) {
              logger.error('Failed to parse SSE chunk:', e);
            }
          }
        }
      }
      
      // 加载历史
      await loadSessions();
      
      return collectedIdeas;
      
    } catch (error) {
      logger.error('Failed to generate ideas:', error);
      setProgress({ percent: 0, step: '失败', message: error.message, thinking_preview: null, content_preview: null });
      
      // 保存错误状态到 localStorage
      saveToLocalStorage({
        ideas: [],
        session: `session-${Date.now()}`,
        progress: { percent: 0, step: '失败', message: error.message }
      });
      
      return null;
    } finally {
      setTimeout(() => setIsGenerating(false), 1000);
    }
  }, [loadSessions, saveToLocalStorage]);

  // 获取详细方案
  const getDetail = useCallback(async (sessionId, ideaIndex) => {
    try {
      const { ideasAPI } = await import('../api');
      const data = await ideasAPI.getDetail(sessionId, ideaIndex);
      return data;
    } catch (error) {
      console.error('Failed to get detail:', error);
      return null;
    }
  }, []);

  // 加载单个会话
  const loadSession = useCallback(async (sessionId) => {
    try {
      const { sessionAPI } = await import('../api');
      const data = await sessionAPI.getSession(sessionId);
      if (data.success) {
        setCurrentSession(sessionId);
        setIdeas(data.ideas);
        return data.ideas;
      }
      return null;
    } catch (error) {
      console.error('Failed to load session:', error);
      return null;
    }
  }, []);

  // 删除会话
  const deleteSession = useCallback(async (sessionId) => {
    try {
      const { sessionAPI } = await import('../api');
      await sessionAPI.deleteSession(sessionId);
      await loadSessions();
      return true;
    } catch (error) {
      console.error('Failed to delete session:', error);
      return false;
    }
  }, [loadSessions]);

  // 更新进度
  const updateProgress = useCallback((percent, step, message) => {
    setProgress({ percent, step, message });
  }, []);

  const value = {
    // Config
    config,
    loadConfig,
    saveConfig,
    
    // Generation
    isGenerating,
    progress,
    updateProgress,
    generateIdeas,
    getDetail,
    saveToLocalStorage,
    
    // Sessions
    currentSession,
    ideas,
    sessions,
    loadSessions,
    loadSession,
    deleteSession,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export default AppContext;
