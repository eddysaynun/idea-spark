/*
 * 前端日志工具
 * 将日志输出到控制台和文件
 */

class Logger {
  constructor(options = {}) {
    this.level = options.level || 'info'; // debug, info, warn, error
    this.prefix = options.prefix || '[IdeaGenerator]';
    this.logs = [];
    this.maxLogs = 1000;
    this.isEnabled = options.isEnabled !== false;
    
    this.levels = {
      debug: 0,
      info: 1,
      warn: 2,
      error: 3
    };
  }

  _shouldLog(level) {
    if (!this.isEnabled) return false;
    return this.levels[level] >= this.levels[this.level];
  }

  _log(level, message, data = null) {
    if (!this._shouldLog(level)) return;

    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      level,
      message,
      data,
      prefix: this.prefix
    };

    // 存储日志
    this.logs.push(logEntry);
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }

    // 控制台输出
    const consoleMethod = level === 'error' ? 'error' : 
                          level === 'warn' ? 'warn' : 
                          level === 'debug' ? 'debug' : 'log';
    
    const formattedMessage = `[${timestamp.split('T')[1].split('.')[0]}] ${this.prefix} [${level.toUpperCase()}] ${message}`;
    
    if (data) {
      console[consoleMethod](formattedMessage, data);
    } else {
      console[consoleMethod](formattedMessage);
    }
  }

  debug(message, data = null) {
    this._log('debug', message, data);
  }

  info(message, data = null) {
    this._log('info', message, data);
  }

  warn(message, data = null) {
    this._log('warn', message, data);
  }

  error(message, data = null) {
    this._log('error', message, data);
  }

  // 导出日志为 JSON
  exportLogs() {
    return JSON.stringify(this.logs, null, 2);
  }

  // 清空日志
  clear() {
    this.logs = [];
  }

  // 下载日志文件
  downloadLogs() {
    const blob = new Blob([this.exportLogs()], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `idea-generator-frontend-${new Date().toISOString().split('T')[0]}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }
}

// 创建全局日志实例
export const logger = new Logger({
  prefix: '[Frontend]',
  level: 'info'
});

// 导出日志到文件 (如果浏览器支持)
export async function saveLogsToFile() {
  try {
    const logs = logger.exportLogs();
    const blob = new Blob([logs], { type: 'application/json' });
    
    // 使用 Fetch API 保存到本地存储
    const filename = `idea-generator-frontend-${new Date().toISOString().split('T')[0]}.log`;
    
    // 触发下载
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    logger.info(`Logs saved to ${filename}`);
  } catch (error) {
    logger.error('Failed to save logs:', error);
  }
}

export default logger;
