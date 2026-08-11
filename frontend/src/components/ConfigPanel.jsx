import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { Settings, Save, RefreshCw } from 'lucide-react';
import './ConfigPanel.css';

const ConfigPanel = () => {
  const { config, saveConfig, loadConfig } = useApp();
  const [localConfig, setLocalConfig] = useState(config);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [detectionError, setDetectionError] = useState('');

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleProviderChange = (e) => {
    setLocalConfig({ ...localConfig, provider: e.target.value });
  };

  const handleHermesUrlChange = (e) => {
    setLocalConfig({ ...localConfig, hermes_url: e.target.value });
  };

  const handleOpenaiKeyChange = (e) => {
    setLocalConfig({ ...localConfig, openai_api_key: e.target.value });
  };

  const handleCustomUrlChange = (e) => {
    setLocalConfig({ ...localConfig, custom_base_url: e.target.value });
    setAvailableModels([]);
    setDetectionError('');
  };

  const handleCustomModelChange = (e) => {
    setLocalConfig({ ...localConfig, custom_model: e.target.value });
  };

  const handleCustomApiKeyChange = (e) => {
    setLocalConfig({ ...localConfig, custom_api_key: e.target.value });
  };

  const handleTemperatureChange = (e) => {
    setLocalConfig({ ...localConfig, temperature: parseFloat(e.target.value) });
  };

  const handleDetectModels = async () => {
    if (!localConfig.custom_base_url) {
      setDetectionError('请先填写 Custom Base URL');
      return;
    }

    setIsDetecting(true);
    setDetectionError('');

    try {
      const response = await fetch('/api/detect-models', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      const data = await response.json();

      if (data.success && data.models.length > 0) {
        setAvailableModels(data.models);
        setLocalConfig({ ...localConfig, custom_model: data.models[0] });
      } else {
        setDetectionError(data.error || '未找到可用模型');
        setAvailableModels([]);
      }
    } catch (error) {
      setDetectionError('检测失败：' + error.message);
      setAvailableModels([]);
    } finally {
      setIsDetecting(false);
    }
  };

  const handleSave = async () => {
    if (!localConfig.custom_model && localConfig.provider === 'custom') {
      alert('请选择或输入模型名称');
      return;
    }

    setIsSaving(true);
    const success = await saveConfig(localConfig);
    if (success) {
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    }
    setIsSaving(false);
  };

  return (
    <div className="config-panel card">
      <div className="config-header">
        <h3>
          <Settings size={20} />
          模型配置
        </h3>
        <button
          className={`btn btn-small ${isSaving ? 'loading' : ''}`}
          onClick={handleSave}
          disabled={isSaving}
        >
          {saveSuccess ? '✓ 已保存' : (
            <>
              <Save size={16} style={{ marginRight: 6 }} />
              保存配置
            </>
          )}
        </button>
      </div>

      <div className="config-grid">
        <div className="config-item">
          <label className="form-label">模型提供商</label>
          <select
            className="form-select"
            value={localConfig.provider}
            onChange={handleProviderChange}
          >
            <option value="hermes">Hermes (本地)</option>
            <option value="openai">OpenAI</option>
            <option value="custom">Custom API</option>
          </select>
        </div>

        {localConfig.provider === 'hermes' && (
          <div className="config-item">
            <label className="form-label">Hermes URL</label>
            <input
              type="text"
              className="form-input"
              value={localConfig.hermes_url}
              onChange={handleHermesUrlChange}
              placeholder="http://localhost:8080/api/chat"
            />
          </div>
        )}

        {localConfig.provider === 'openai' && (
          <div className="config-item">
            <label className="form-label">OpenAI API Key</label>
            <input
              type="password"
              className="form-input"
              value={localConfig.openai_api_key || ''}
              onChange={handleOpenaiKeyChange}
              placeholder="sk-..."
            />
          </div>
        )}

        {localConfig.provider === 'custom' && (
          <>
            <div className="config-item">
              <label className="form-label">Custom Base URL</label>
              <input
                type="text"
                className="form-input"
                value={localConfig.custom_base_url}
                onChange={handleCustomUrlChange}
                placeholder="http://example.com/v1"
              />
            </div>

            <div className="config-item">
              <label className="form-label">Custom Model</label>
              <div className="model-select-wrapper">
                {availableModels.length > 0 ? (
                  <select
                    className="form-select"
                    value={localConfig.custom_model || ''}
                    onChange={handleCustomModelChange}
                  >
                    <option value="">请选择模型...</option>
                    {availableModels.map((model, index) => (
                      <option key={index} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    className="form-input"
                    value={localConfig.custom_model || ''}
                    onChange={handleCustomModelChange}
                    placeholder="输入模型名称"
                  />
                )}
                <button
                  className="detect-btn"
                  onClick={handleDetectModels}
                  disabled={isDetecting}
                  title="检测可用模型"
                >
                  <RefreshCw size={16} className={isDetecting ? 'spinning' : ''} />
                </button>
              </div>
              {detectionError && (
                <div className="error-message">{detectionError}</div>
              )}
              {availableModels.length > 0 && (
                <div className="success-message">
                  ✓ 找到 {availableModels.length} 个模型
                </div>
              )}
            </div>

            <div className="config-item">
              <label className="form-label">Custom API Key (可选)</label>
              <input
                type="password"
                className="form-input"
                value={localConfig.custom_api_key || ''}
                onChange={handleCustomApiKeyChange}
                placeholder="Bearer token (可选)"
              />
            </div>
          </>
        )}

        <div className="config-item">
          <label className="form-label">Temperature</label>
          <input
            type="number"
            className="form-input"
            value={localConfig.temperature}
            onChange={handleTemperatureChange}
            min="0"
            max="2"
            step="0.1"
          />
        </div>
      </div>

      {localConfig.provider === 'custom' && (
        <div className="config-hint">
          💡 点击刷新按钮自动检测 API 支持的模型列表，然后从下拉框选择
        </div>
      )}
    </div>
  );
};

export default ConfigPanel;
