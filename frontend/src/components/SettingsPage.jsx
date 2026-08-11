import React from 'react';
import ConfigPanel from './ConfigPanel';
import './SettingsPage.css';

const SettingsPage = () => {
  return (
    <div className="settings-page">
      <div className="page-header">
        <h1 className="page-title">设置</h1>
        <p className="page-subtitle">配置模型参数和偏好设置</p>
      </div>

      <ConfigPanel />
    </div>
  );
};

export default SettingsPage;
