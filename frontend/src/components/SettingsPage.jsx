import ConfigPanel from './ConfigPanel';
import './SettingsPage.css';

const SettingsPage = () => {
  return (
    <div className="settings-page">
      <div className="content-heading">
        <p className="eyebrow"><span /> MODEL CONNECTION</p>
        <h1>模型设置</h1>
        <p>连接任意 OpenAI-compatible 模型服务。密钥仅存在于后端进程内存，不会落盘或回传浏览器。</p>
      </div>

      <ConfigPanel />
    </div>
  );
};

export default SettingsPage;
