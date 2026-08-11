import React, { useState, useEffect, useRef } from 'react';
import { useApp } from '../context/AppContext';
import { Sparkles, ArrowRight, Terminal } from 'lucide-react';
import './StreamPage.css';

const StreamPage = () => {
  const { config } = useApp();
  const [direction, setDirection] = useState('');
  const [count, setCount] = useState(5);
  const [category, setCategory] = useState('ai-agent');
  const [isStreaming, setIsStreaming] = useState(false);
  const [output, setOutput] = useState([]);
  const [progress, setProgress] = useState(0);
  const outputRef = useRef(null);

  // 自动滚动到底部
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const addOutput = (type, message, data = null) => {
    setOutput(prev => [...prev, { type, message, data, timestamp: new Date().toLocaleTimeString() }]);
  };

  const startStream = async () => {
    if (!direction.trim()) {
      addOutput('error', '请输入项目方向');
      return;
    }

    setIsStreaming(true);
    setOutput([]);
    setProgress(0);

    addOutput('info', `开始生成 Ideas: ${direction}`);
    addOutput('info', `数量：${count}, 分类：${category}`);

    try {
      const controller = new AbortController();
      const url = `/api/generate-stream?direction=${encodeURIComponent(direction)}&count=${count}&category=${category}`;

      const response = await fetch(url, {
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');

      addOutput('info', '正在接收流式数据...');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'start':
                  addOutput('progress', '开始生成', data.data);
                  setProgress(10);
                  break;
                case 'progress':
                  addOutput('progress', data.data.step, data.data);
                  setProgress(data.data.progress);
                  break;
                case 'idea':
                  addOutput('idea', `Idea #${data.index}: ${data.data.name}`, data.data);
                  setProgress(60 + (data.index / count) * 30);
                  break;
                case 'complete':
                  addOutput('success', `生成完成！共 ${data.data.total} 个 Ideas`);
                  setProgress(100);
                  break;
                case 'error':
                  addOutput('error', data.data.message);
                  break;
                default:
                  addOutput('info', JSON.stringify(data));
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }

    } catch (error) {
      if (error.name !== 'AbortError') {
        addOutput('error', `生成失败：${error.message}`);
      }
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="stream-page">
      <div className="page-header">
        <h1 className="page-title">流式生成 Ideas</h1>
        <p className="page-subtitle">
          实时查看 AI 生成过程，无需等待
        </p>
      </div>

      <div className="stream-container">
        <div className="stream-form">
          <div className="form-group">
            <label className="form-label">项目方向</label>
            <textarea
              className="form-textarea"
              placeholder="例如：AI Agent 辅助工具、开发者效率工具..."
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              rows={2}
              disabled={isStreaming}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">生成数量</label>
              <select
                className="form-select"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                disabled={isStreaming}
              >
                <option value={3}>3 个</option>
                <option value={5}>5 个</option>
                <option value={10}>10 个</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">分类</label>
              <select
                className="form-select"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={isStreaming}
              >
                <option value="general">通用</option>
                <option value="ai-agent">AI Agent</option>
                <option value="dev-tools">开发者工具</option>
                <option value="privacy">隐私安全</option>
              </select>
            </div>
          </div>

          <button
            className={`btn btn-primary btn-large ${isStreaming ? 'streaming' : ''}`}
            onClick={startStream}
            disabled={isStreaming}
          >
            <Terminal size={20} className={isStreaming ? 'spinning' : ''} />
            {isStreaming ? '生成中...' : '开始流式生成'}
          </button>
        </div>

        <div className="stream-output">
          <div className="output-header">
            <h3>
              <Terminal size={18} />
              实时输出
            </h3>
            {progress > 0 && (
              <div className="output-progress">
                <div className="progress-bar-small">
                  <div className="progress-fill-small" style={{ width: `${progress}%` }} />
                </div>
                <span>{progress}%</span>
              </div>
            )}
          </div>

          <div className="output-content" ref={outputRef}>
            {output.length === 0 ? (
              <div className="output-empty">
                <Terminal size={48} className="empty-icon" />
                <p>等待生成...</p>
              </div>
            ) : (
              output.map((item, index) => (
                <div key={index} className={`output-line ${item.type}`}>
                  <span className="output-time">[{item.timestamp}]</span>
                  {item.type === 'idea' && <Sparkles size={14} className="idea-icon" />}
                  {item.type === 'error' && <span className="error-icon">⚠️</span>}
                  {item.type === 'success' && <span className="success-icon">✅</span>}
                  {item.type === 'progress' && <span className="progress-icon">🔄</span>}
                  <span className="output-message">{item.message}</span>
                  {item.data && item.type === 'idea' && (
                    <div className="idea-preview">
                      <strong>{item.data.name}</strong>: {item.data.tagline}
                      <div className="idea-tags">
                        {item.data.tags?.map((tag, i) => (
                          <span key={i} className="tag-small">{tag}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StreamPage;
