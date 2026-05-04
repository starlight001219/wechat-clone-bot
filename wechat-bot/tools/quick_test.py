"""快速测试机器人能否启动"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'omni-bot-sdk-oss', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config
print(f"配置: 目标={config.settings.target_name}, DeepSeek={bool(config.settings.openai_api_key)}")

from wechat.handler import WeChatHandler

handler = WeChatHandler()
if not handler.start():
    print("启动失败！")
    sys.exit(1)

print("机器人已启动，3秒后关闭...")
time.sleep(3)
handler.stop()
print("测试完成")
