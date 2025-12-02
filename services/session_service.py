import uuid
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .base_service import BaseService

class SessionService(BaseService):
    """会话管理服务"""

    def __init__(self):
        super().__init__()
        self.chat_sessions = {}  # 存储每个会话的历史
        self.session_timeout = 3600  # 会话超时时间（秒）
        self._lock = threading.Lock()  # 线程锁，保护chat_sessions字典

    def initialize(self, session_timeout: int = 3600, **kwargs):
        """初始化会话服务"""
        super().initialize(**kwargs)
        self.session_timeout = session_timeout
        self.logger.info(f"会话服务初始化完成，超时时间: {session_timeout}秒")

    def get_or_create_session(self, session_id: Optional[str] = None) -> tuple[str, Dict]:
        """获取或创建会话
        
        Args:
            session_id: 可选的会话ID
                - None: 创建新会话
                - 字符串: 尝试获取已有会话，不存在则尝试从缓存加载，仍不存在则抛出异常
        
        Returns:
            (session_id, session_data)
        
        Raises:
            Exception: 当指定session_id但会话已被清理时
        """
        # 场景1：创建新会话（session_id为None）
        if not session_id:
            session_id = str(uuid.uuid4())
            with self._lock:
                self.chat_sessions[session_id] = {
                    'messages': [],
                    'created_at': datetime.now(),
                    'last_activity': datetime.now()
                }
            self.logger.info(f"创建新会话: {session_id}")
            return session_id, self.chat_sessions[session_id]
        
        # 场景2：会话在内存中
        if session_id in self.chat_sessions:
            with self._lock:
                self.chat_sessions[session_id]['last_activity'] = datetime.now()
            return session_id, self.chat_sessions[session_id]
        
        # 场景3：尝试从缓存加载
        session_data = self._load_from_cache(session_id)
        if session_data:
            # 加载成功，恢复到内存
            with self._lock:
                self.chat_sessions[session_id] = session_data
                self.chat_sessions[session_id]['last_activity'] = datetime.now()
            self.logger.info(f"从缓存恢复会话: {session_id}")
            return session_id, self.chat_sessions[session_id]
        
        # 场景4：会话不存在且无缓存 - 抛出异常
        raise Exception(f"会话已被清理，请刷新页面开始新对话")

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取指定会话"""
        return self.chat_sessions.get(session_id)

    def add_user_message(self, session_id: str, content: str):
        """添加用户消息到会话"""
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]['messages'].append({
                "role": "user",
                "content": content
            })
            self.chat_sessions[session_id]['last_activity'] = datetime.now()

    def add_assistant_message(self, session_id: str, content: str):
        """添加助手消息到会话"""
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]['messages'].append({
                "role": "assistant",
                "content": content
            })
            self.chat_sessions[session_id]['last_activity'] = datetime.now()

    def clear_session(self, session_id: str) -> bool:
        """清空会话历史"""
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]['messages'] = []
            self.chat_sessions[session_id]['last_activity'] = datetime.now()
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            return True
        return False

    def clean_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []

        for session_id, session in self.chat_sessions.items():
            if now - session['last_activity'] > timedelta(seconds=self.session_timeout):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.chat_sessions[session_id]

        if expired_sessions:
            self.logger.info(f"清理了 {len(expired_sessions)} 个过期会话")

    def save_session_to_file(self, session_id: str, filename: Optional[str] = None, system_prompt: str = '', selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """保存会话到文件"""
        if session_id not in self.chat_sessions:
            raise Exception("会话不存在")

        try:
            # 确保chatSave目录存在
            chat_save_dir = 'chatSave'
            if not os.path.exists(chat_save_dir):
                os.makedirs(chat_save_dir)

            # 生成文件名
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"chat_{timestamp}.json"

            if not filename.endswith('.json'):
                filename += '.json'

            # 准备要保存的数据
            session_data = self.chat_sessions[session_id]
            save_data = {
                'session_id': session_id,
                'created_at': session_data['created_at'].isoformat(),
                'last_activity': session_data['last_activity'].isoformat(),
                'messages': session_data['messages'],
                'model': None,
                'selected_tools': selected_tools or [],
                'system_prompt': system_prompt
            }

            # 保存文件
            file_path = os.path.join(chat_save_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            return {
                'filename': filename,
                'path': file_path,
                'message_count': len(session_data['messages'])
            }

        except Exception as e:
            self.logger.error(f"保存会话失败: {e}")
            raise

    def load_session_from_file(self, filename: str) -> Dict[str, Any]:
        """从文件加载会话"""
        if not filename:
            raise Exception("文件名不能为空")

        try:
            # 确保文件名安全
            filename = os.path.basename(filename)
            if not filename.endswith('.json'):
                filename += '.json'

            file_path = os.path.join('chatSave', filename)

            if not os.path.exists(file_path):
                raise Exception("文件不存在")

            # 加载文件
            with open(file_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)

            # 创建新会话
            session_id = str(uuid.uuid4())
            self.chat_sessions[session_id] = {
                'messages': save_data.get('messages', []),
                'created_at': datetime.fromisoformat(save_data.get('created_at', datetime.now().isoformat())),
                'last_activity': datetime.now()
            }

            return {
                'session_id': session_id,
                'messages': save_data.get('messages', []),
                'model': save_data.get('model'),
                'selected_tools': save_data.get('selected_tools', []),
                'system_prompt': save_data.get('system_prompt', '')
            }

        except Exception as e:
            self.logger.error(f"加载会话失败: {e}")
            raise

    def list_saved_sessions(self) -> List[Dict[str, Any]]:
        """获取已保存的会话列表"""
        try:
            chat_save_dir = 'chatSave'
            if not os.path.exists(chat_save_dir):
                return []

            files = []
            for filename in os.listdir(chat_save_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(chat_save_dir, filename)
                    stat = os.stat(file_path)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            files.append({
                                'filename': filename,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'message_count': len(data.get('messages', [])),
                                'created_at': data.get('created_at', ''),
                                'model': data.get('model', ''),
                                'selected_tools_count': len(data.get('selected_tools', [])),
                                'has_system_prompt': bool(data.get('system_prompt', '').strip())
                            })
                    except Exception as e:
                        self.logger.warning(f"读取文件信息失败: {filename}, {e}")
                        files.append({
                            'filename': filename,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'error': str(e)
                        })

            # 按修改时间排序，最新的在前
            files.sort(key=lambda x: x['modified'], reverse=True)
            return files

        except Exception as e:
            self.logger.error(f"获取会话列表失败: {e}")
            raise

    def delete_saved_session(self, filename: str) -> bool:
        """删除已保存的会话文件"""
        if not filename:
            raise Exception("文件名不能为空")

        try:
            # 确保文件名安全
            filename = os.path.basename(filename)
            if not filename.endswith('.json'):
                filename += '.json'

            file_path = os.path.join('chatSave', filename)

            if not os.path.exists(file_path):
                return False

            os.remove(file_path)
            return True

        except Exception as e:
            self.logger.error(f"删除会话文件失败: {e}")
            raise

    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        return {
            'total_sessions': len(self.chat_sessions),
            'total_messages': sum(len(session['messages']) for session in self.chat_sessions.values()),
            'session_timeout': self.session_timeout
        }

    def _get_cache_path(self, session_id: str) -> str:
        """获取缓存文件路径"""
        cache_dir = 'serverChatCache'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return os.path.join(cache_dir, f"session_{session_id}.json")

    def _save_to_cache(self, session_id: str) -> bool:
        """保存会话到缓存"""
        try:
            cache_path = self._get_cache_path(session_id)
            session_data = self.chat_sessions[session_id]
            
            save_data = {
                'session_id': session_id,
                'messages': session_data['messages'],
                'created_at': session_data['created_at'].isoformat(),
                'last_activity': session_data['last_activity'].isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"会话已缓存: {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"缓存会话失败 {session_id}: {e}")
            return False

    def _load_from_cache(self, session_id: str) -> Optional[Dict]:
        """从缓存加载会话"""
        try:
            cache_path = self._get_cache_path(session_id)
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            return {
                'messages': save_data.get('messages', []),
                'created_at': datetime.fromisoformat(save_data['created_at']),
                'last_activity': datetime.fromisoformat(save_data['last_activity'])
            }
        except Exception as e:
            self.logger.error(f"从缓存加载会话失败 {session_id}: {e}")
            return None

    def cache_inactive_sessions(self, inactive_threshold: int = 3600):
        """将不活跃会话缓存到文件并从内存释放
        
        Args:
            inactive_threshold: 不活跃阈值（秒），默认1小时
        """
        now = datetime.now()
        cached_sessions = []
        
        with self._lock:
            for session_id, session in list(self.chat_sessions.items()):
                if now - session['last_activity'] > timedelta(seconds=inactive_threshold):
                    if self._save_to_cache(session_id):
                        del self.chat_sessions[session_id]
                        cached_sessions.append(session_id)
        
        if cached_sessions:
            self.logger.info(f"缓存了 {len(cached_sessions)} 个不活跃会话")
        
        # 清理过期缓存文件（24小时）
        self._clean_expired_cache(max_age_hours=24)

    def _clean_expired_cache(self, max_age_hours: int = 24):
        """清理过期的缓存文件"""
        try:
            cache_dir = 'serverChatCache'
            if not os.path.exists(cache_dir):
                return
            
            now = datetime.now()
            deleted_count = 0
            
            for filename in os.listdir(cache_dir):
                if filename.startswith('session_') and filename.endswith('.json'):
                    file_path = os.path.join(cache_dir, filename)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if now - file_mtime > timedelta(hours=max_age_hours):
                        os.remove(file_path)
                        deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(f"清理了 {deleted_count} 个过期缓存文件（超过{max_age_hours}小时）")
        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {e}")