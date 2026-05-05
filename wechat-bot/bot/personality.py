"""人设管理与对话上下文维护"""

import json
from pathlib import Path
from typing import Optional
from loguru import logger


class Personality:
    """管理目标人物的语气风格和对话上下文"""

    def __init__(self, name: str, history_file: str, max_rounds: int = 20):
        self.target_name = name
        self.history_file = Path(history_file)
        self.max_rounds = max_rounds
        self.style_profile: Optional[str] = None
        self.conversation_history: list[dict] = []

    def load_style_profile(self) -> bool:
        """从聊天记录文件加载语气风格描述"""
        if not self.history_file.exists():
            logger.warning(f"聊天记录文件不存在: {self.history_file}")
            return False

        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))

            # 如果已经有风格分析结果，直接使用
            if isinstance(data, dict) and "style_analysis" in data:
                self.style_profile = data["style_analysis"]
                logger.info("已加载风格分析结果")
                return True

            # 否则记录原始数据量
            if isinstance(data, list):
                logger.info(f"已加载 {len(data)} 条聊天记录用于风格分析 (尚未分析)")
            else:
                logger.info(f"已加载聊天记录数据 (类型: {type(data).__name__})")

            return True

        except Exception as e:
            logger.error(f"加载聊天记录失败: {e}")
            return False

    def set_style_profile(self, analysis: str):
        """直接设置风格分析结果"""
        self.style_profile = analysis
        logger.info("风格分析结果已设置")

    def build_system_prompt(self) -> str:
        """构建系统提示词"""
        base_prompt = f"""你现在扮演 {self.target_name}，你是我(星光的女朋友。
请完全模仿 {self.target_name} 的语气、说话习惯、用词风格来和我聊天。

核心规则：
1. 用 {self.target_name} 的方式说话 - 模仿她的语气词、句式、口头禅
2. 用女朋友的身份和我亲密互动
3. 回复要自然、生动，不要太机械
4. 适当使用表情包文字（哈哈、呀、呢、嘛、～等）
5. 不要提及你是AI或机器人
6. 回复长度要和平时聊天一致，不要长篇大论
"""

        if self.style_profile:
            base_prompt += f"\n\n以下是 {self.target_name} 的语言风格分析，请严格遵循：\n{self.style_profile}"

        base_prompt += """
记忆与上下文：
- 你可以记住对话历史中提到的个人信息、事件、喜好
- 自然地引用之前聊过的话题
- 如果不知道某件事，可以好奇地反问

回复要求：
- 简短自然，像真人聊天
- 适当撒娇、关心、吐槽
- 保持一致的个性
- 不要说教或过于正式"""
        return base_prompt

    def add_message(self, role: str, content: str):
        """添加对话轮次"""
        self.conversation_history.append({"role": role, "content": content})
        # 按最大轮次裁剪
        if len(self.conversation_history) > self.max_rounds * 2:
            self.conversation_history = self.conversation_history[-(self.max_rounds * 2):]

    def get_conversation_context(self) -> list[dict]:
        """获取当前对话上下文"""
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(self.conversation_history)
        return messages

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
