import { useState, useEffect } from 'react';
import { useApp } from '../context/app-context';
import { configAPI } from '../api';
import { Settings, Save, RefreshCw, ShieldCheck } from 'lucide-react';
import './ConfigPanel.css';

const ConfigPanel = () => {
  const { config, loadConfig, loadModels, saveConfig } = useApp();
  const [adminToken, setAdminToken] = useState('');
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isConfigLoaded, setIsConfigLoaded] = useState(false);
  const [localConfig, setLocalConfig] = useState({ ...config, api_key: '' });
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [detectionError, setDetectionError] = useState('');

  useEffect(() => {
    setLocalConfig({ ...config, api_key: '' });
  }, [config]);

  const handleBaseUrlChange = (e) => {
    setLocalConfig({ ...localConfig, base_url: e.target.value });
    setAvailableModels([]);
    setDetectionError('');
  };

  const handleModelChange = (e) => {
    setLocalConfig({ ...localConfig, model: e.target.value });
  };

  const handleApiKeyChange = (e) => {
    setLocalConfig({ ...localConfig, api_key: e.target.value });
  };

  const handleTemperatureChange = (e) => {
    setLocalConfig({ ...localConfig, temperature: parseFloat(e.target.value) });
  };

  const handleLoadConfig = async () => {
    setIsLoadingConfig(true);
    setDetectionError('');
    const success = await loadConfig(adminToken);
    setIsConfigLoaded(success);
    if (!success) setDetectionError('无法读取配置，请检查管理员令牌或服务端安全设置');
    setIsLoadingConfig(false);
  };

  const handleDetectModels = async () => {
    if (!localConfig.base_url) {
      setDetectionError('请先填写 API Base URL');
      return;
    }

    setIsDetecting(true);
    setDetectionError('');

    try {
      const saved = await saveConfig(localConfig, adminToken);
      if (!saved) throw new Error('无法应用当前连接配置');
      const data = await configAPI.detectModels(adminToken);

      if (data.success && data.models.length > 0) {
        setAvailableModels(data.models);
        setLocalConfig({ ...localConfig, model: data.models[0] });
        await loadModels();
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
    if (!localConfig.model) {
      setDetectionError('请选择或输入模型名称');
      return;
    }

    setIsSaving(true);
    const success = await saveConfig(localConfig, adminToken);
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
          {saveSuccess ? '✓ 已应用' : (
            <>
              <Save size={16} style={{ marginRight: 6 }} />
              应用到当前进程
            </>
          )}
        </button>
      </div>

      <div className="admin-access">
        <div className="admin-access-copy">
          <ShieldCheck size={18} />
          <div>
            <strong>管理员访问</strong>
            <span>令牌仅保存在当前页面内存，刷新或离开本页即清除。</span>
          </div>
        </div>
        <div className="admin-access-control">
          <input
            type="password"
            className="form-input"
            value={adminToken}
            onChange={(event) => setAdminToken(event.target.value)}
            placeholder="管理员令牌（本机开发可留空）"
            autoComplete="off"
            aria-label="管理员令牌"
          />
          <button type="button" onClick={handleLoadConfig} disabled={isLoadingConfig}>
            {isLoadingConfig ? '读取中…' : isConfigLoaded ? '重新读取' : '读取配置'}
          </button>
        </div>
      </div>

      <div className="config-grid">
            <div className="config-item">
              <label className="form-label">API Base URL</label>
              <input
                type="text"
                className="form-input"
                value={localConfig.base_url || ''}
                onChange={handleBaseUrlChange}
                placeholder="https://api.example.com/v1"
              />
            </div>

            <div className="config-item">
              <label className="form-label">默认模型</label>
              <div className="model-select-wrapper">
                {availableModels.length > 0 ? (
                  <select
                    className="form-select"
                    value={localConfig.model || ''}
                    onChange={handleModelChange}
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
                    value={localConfig.model || ''}
                    onChange={handleModelChange}
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
              <label className="form-label">API Key（可选）</label>
              <input
                type="password"
                className="form-input"
                value={localConfig.api_key || ''}
                onChange={handleApiKeyChange}
                placeholder={localConfig.has_api_key ? '已配置；留空保持不变' : 'Bearer token（可选）'}
              />
            </div>

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

      <div className="config-hint">
        点击刷新按钮检测兼容 API 提供的模型；检测结果会同步到工作台模型选择器。
      </div>
      <div className="config-hint security-hint">
        配置修改只在当前后端进程内生效，服务重启后恢复环境变量配置，不会写入磁盘。
      </div>
    </div>
  );
};

export default ConfigPanel;
