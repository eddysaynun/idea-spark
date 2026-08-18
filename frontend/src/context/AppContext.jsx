import { useCallback, useEffect, useRef, useState } from 'react';

import { authAPI, ideasAPI, modelAPI, sessionAPI } from '../api';
import { consumeSseStream } from '../utils/sse';
import { AppContext } from './app-context';

const emptyProgress = {
  percent: 0,
  step: '',
  message: '',
};

export const AppProvider = ({ children }) => {
  const [availableModels, setAvailableModels] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(emptyProgress);
  const [generationError, setGenerationError] = useState('');
  const [currentSession, setCurrentSession] = useState(null);
  const [currentIdeaIndex, setCurrentIdeaIndex] = useState(null);
  const [ideas, setIdeas] = useState([]);
  const [sessions, setSessions] = useState([]);
  const abortRef = useRef(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);

  const refreshUser = useCallback(async () => {
    setAuthLoading(true);
    try {
      const data = await authAPI.me();
      setUser(data.user);
      return data.user;
    } catch {
      setUser(null);
      return null;
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => { refreshUser(); }, [refreshUser]);

  const logout = useCallback(async () => {
    await authAPI.logout();
    setUser(null);
    setSessions([]);
  }, []);

  const loadModels = useCallback(async () => {
    if (!user) return;
    try {
      const data = await modelAPI.listModels();
      if (data.success) setAvailableModels(data.models);
    } catch (error) {
      console.error('Failed to load models', error);
    }
  }, [user]);

  const loadSessions = useCallback(async () => {
    if (!user) {
      setSessions([]);
      return;
    }
    try {
      const data = await sessionAPI.listSessions();
      if (data.success) setSessions(data.sessions);
    } catch (error) {
      console.error('Failed to load sessions', error);
    }
  }, [user]);

  const generateIdeas = useCallback(async (direction, count, category, model) => {
    setIsGenerating(true);
    setGenerationError('');
    setCurrentIdeaIndex(null);
    setProgress({ ...emptyProgress, message: '正在连接模型…' });
    const controller = new AbortController();
    abortRef.current = controller;
    const collectedIdeas = [];
    let sessionId = '';
    let completed = false;

    try {
      if (!user) throw new Error('请先登录后开始探索');
      const idempotencyKey = crypto.randomUUID();
      const response = await fetch('/api/generate-stream', {
        method: 'POST',
        credentials: 'include',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify({ direction, count, category, model }),
      });
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
          case 'idea':
            collectedIdeas.push(event.data);
            setIdeas([...collectedIdeas]);
            break;
          case 'complete': {
            completed = true;
            const session = { id: sessionId, direction, count, category, model, ideas: [...collectedIdeas], detailed_plans: {} };
            setIdeas(session.ideas);
            setCurrentSession(session);
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
      await refreshUser();
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
  }, [loadSessions, refreshUser, user]);

  const cancelGeneration = useCallback(() => abortRef.current?.abort(), []);

  const selectIdea = useCallback((index) => {
    if (!currentSession || !currentSession.ideas[index]) return false;
    setCurrentIdeaIndex(index);
    return true;
  }, [currentSession]);

  const generateDetail = useCallback(async () => {
    if (!currentSession || currentIdeaIndex === null) return null;
    const data = await ideasAPI.getDetail(
      currentSession.id,
      currentIdeaIndex,
      currentSession.model,
      crypto.randomUUID(),
    );
    if (!data.success) return null;

    const session = {
      ...currentSession,
      detailed_plans: {
        ...currentSession.detailed_plans,
        [currentIdeaIndex]: data.detailed_plan,
      },
    };
    setCurrentSession(session);
    await refreshUser();
    return data.detailed_plan;
  }, [currentIdeaIndex, currentSession, refreshUser]);

  const loadSession = useCallback(async (sessionId) => {
    const data = await sessionAPI.getSession(sessionId);
    if (!data.success) return false;
    const session = { ...data, id: sessionId };
    setCurrentSession(session);
    setIdeas(session.ideas);
    setCurrentIdeaIndex(null);
    return true;
  }, []);

  const deleteSession = useCallback(async (sessionId) => {
    const data = await sessionAPI.deleteSession(sessionId);
    if (!data.success) return false;
    if (currentSession?.id === sessionId) {
      setCurrentSession(null);
      setIdeas([]);
      setCurrentIdeaIndex(null);
    }
    await loadSessions();
    return true;
  }, [currentSession, loadSessions]);

  const value = {
    authLoading, user, refreshUser, logout,
    availableModels, loadModels,
    isGenerating, progress, generationError, generateIdeas, cancelGeneration,
    currentSession, currentIdeaIndex, ideas, sessions,
    selectIdea, generateDetail, loadSessions, loadSession, deleteSession,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export default AppContext;
