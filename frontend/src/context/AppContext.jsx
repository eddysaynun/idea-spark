import { useCallback, useEffect, useRef, useState } from 'react';

import { configAPI, ideasAPI, sessionAPI } from '../api';
import { logger } from '../utils/logger';
import { consumeSseStream } from '../utils/sse';
import { AppContext } from './app-context';

const emptyProgress = {
  percent: 0,
  step: '',
  message: '',
  thinking_preview: '',
  content_preview: '',
};

export const AppProvider = ({ children }) => {
  const [config, setConfig] = useState({
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    temperature: 0.7,
  });
  const [availableModels, setAvailableModels] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(emptyProgress);
  const [generationError, setGenerationError] = useState('');
  const [currentSession, setCurrentSession] = useState(null);
  const [currentIdeaIndex, setCurrentIdeaIndex] = useState(null);
  const [ideas, setIdeas] = useState([]);
  const [sessions, setSessions] = useState([]);
  const abortRef = useRef(null);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('idea_spark_session'));
      if (saved?.id && Array.isArray(saved.ideas)) {
        setCurrentSession(saved);
        setIdeas(saved.ideas);
      }
    } catch (error) {
      logger.warn('Ignoring invalid local session', error);
    }
  }, []);

  const persistSession = useCallback((session) => {
    try {
      localStorage.setItem('idea_spark_session', JSON.stringify(session));
    } catch (error) {
      logger.warn('Unable to persist session', error);
    }
  }, []);

  const loadConfig = useCallback(async (adminToken = '') => {
    try {
      const data = await configAPI.getConfig(adminToken);
      if (data.success) {
        setConfig(data.config);
        setAvailableModels(data.config.available_models || []);
      }
      return data.success;
    } catch (error) {
      logger.error('Failed to load config', error.message);
      return false;
    }
  }, []);

  const saveConfig = useCallback(async (nextConfig, adminToken = '') => {
    try {
      const data = await configAPI.updateConfig(nextConfig, adminToken);
      if (data.success) {
        setConfig(data.config);
        setAvailableModels(data.config.available_models || []);
      }
      return data.success;
    } catch (error) {
      logger.error('Failed to save config', error.message);
      return false;
    }
  }, []);

  const loadModels = useCallback(async () => {
    try {
      const data = await configAPI.listModels();
      if (data.success) setAvailableModels(data.models);
    } catch (error) {
      logger.error('Failed to load models', error.message);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const data = await sessionAPI.listSessions();
      if (data.success) setSessions(data.sessions);
    } catch (error) {
      logger.error('Failed to load sessions', error);
    }
  }, []);

  const generateIdeas = useCallback(async (direction, count, category, model) => {
    setIsGenerating(true);
    setGenerationError('');
    setCurrentIdeaIndex(null);
    setProgress({ ...emptyProgress, message: '正在连接模型…' });
    const controller = new AbortController();
    abortRef.current = controller;
    const collectedIdeas = [];
    let sessionId = '';
    let reasoning = '';
    let content = '';
    let completed = false;

    try {
      const query = new URLSearchParams({ direction, count: String(count), category, model });
      const response = await fetch(`/api/generate-stream?${query}`, { signal: controller.signal });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `请求失败 (${response.status})`);
      }

      await consumeSseStream(response.body, (event) => {
        switch (event.type) {
          case 'start':
            sessionId = event.data.session_id;
            break;
          case 'progress':
            setProgress((previous) => ({
              ...previous,
              percent: event.data.progress,
              step: event.data.step,
              message: event.data.message,
            }));
            break;
          case 'reasoning':
            reasoning = (reasoning + event.data).slice(-4000);
            setProgress((previous) => ({ ...previous, thinking_preview: reasoning }));
            break;
          case 'text':
            content = (content + event.data).slice(-4000);
            setProgress((previous) => ({ ...previous, content_preview: content }));
            break;
          case 'idea':
            collectedIdeas.push(event.data);
            setIdeas([...collectedIdeas]);
            break;
          case 'complete': {
            completed = true;
            const session = { id: sessionId, direction, count, category, model, ideas: [...collectedIdeas], detailed_plans: {} };
            setIdeas(session.ideas);
            setCurrentSession(session);
            persistSession(session);
            setProgress({ ...emptyProgress, percent: 100, step: '完成', message: `已生成 ${session.ideas.length} 个机会` });
            break;
          }
          case 'error':
            throw new Error(event.data.message);
          default:
            break;
        }
      });

      if (!completed) throw new Error('数据流提前结束，请重试');
      await loadSessions();
      return collectedIdeas;
    } catch (error) {
      const message = error.name === 'AbortError' ? '已停止本次生成' : error.message;
      setGenerationError(message);
      setProgress({ ...emptyProgress, step: '失败', message });
      return null;
    } finally {
      abortRef.current = null;
      setIsGenerating(false);
    }
  }, [loadSessions, persistSession]);

  const cancelGeneration = useCallback(() => abortRef.current?.abort(), []);

  const selectIdea = useCallback((index) => {
    if (!currentSession || !currentSession.ideas[index]) return false;
    setCurrentIdeaIndex(index);
    return true;
  }, [currentSession]);

  const generateDetail = useCallback(async () => {
    if (!currentSession || currentIdeaIndex === null) return null;
    const data = await ideasAPI.getDetail(currentSession.id, currentIdeaIndex, currentSession.model);
    if (!data.success) return null;

    const session = {
      ...currentSession,
      detailed_plans: {
        ...currentSession.detailed_plans,
        [currentIdeaIndex]: data.detailed_plan,
      },
    };
    setCurrentSession(session);
    persistSession(session);
    return data.detailed_plan;
  }, [currentIdeaIndex, currentSession, persistSession]);

  const loadSession = useCallback(async (sessionId) => {
    const data = await sessionAPI.getSession(sessionId);
    if (!data.success) return false;
    const session = { ...data, id: sessionId };
    setCurrentSession(session);
    setIdeas(session.ideas);
    setCurrentIdeaIndex(null);
    persistSession(session);
    return true;
  }, [persistSession]);

  const deleteSession = useCallback(async (sessionId) => {
    const data = await sessionAPI.deleteSession(sessionId);
    if (!data.success) return false;
    if (currentSession?.id === sessionId) {
      setCurrentSession(null);
      setIdeas([]);
      setCurrentIdeaIndex(null);
      localStorage.removeItem('idea_spark_session');
    }
    await loadSessions();
    return true;
  }, [currentSession, loadSessions]);

  const value = {
    config, loadConfig, saveConfig, availableModels, loadModels,
    isGenerating, progress, generationError, generateIdeas, cancelGeneration,
    currentSession, currentIdeaIndex, ideas, sessions,
    selectIdea, generateDetail, loadSessions, loadSession, deleteSession,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export default AppContext;
