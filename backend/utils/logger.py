"""
日志配置模块
将日志输出到文件和控制台
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
import datetime


def setup_logging(project_name: str, log_dir: str = None, level: int = logging.INFO):
    """
    设置日志系统
    
    Args:
        project_name: 项目名称 (用于日志文件名)
        log_dir: 日志目录 (默认在项目根目录/logs)
        level: 日志级别
    """
    # 确定日志目录
    if log_dir is None:
        # 自动检测是前端还是后端
        if 'backend' in os.getcwd():
            log_dir = os.path.join(os.path.dirname(os.getcwd()), 'backend', 'logs')
        elif 'frontend' in os.getcwd():
            log_dir = os.path.join(os.path.dirname(os.getcwd()), 'frontend', 'logs')
        else:
            log_dir = os.path.join(os.getcwd(), 'logs')
    
    # 创建日志目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # 文件处理器 (简化文件名)
    log_file = os.path.join(log_dir, f'{project_name}.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    # 错误日志文件 (只记录 ERROR 及以上)
    error_log_file = os.path.join(log_dir, f'{project_name}_error.log')
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    root_logger.addHandler(error_handler)
    
    logging.info(f"📝 Logging initialized: {log_dir}")
    return log_dir


# 便捷函数
def get_logger(name: str = __name__):
    """获取日志器实例"""
    return logging.getLogger(name)
