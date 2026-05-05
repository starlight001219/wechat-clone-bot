"""
Quick test: StyleLearner + DeepSeek API
Tests whether the persona prompt + real chat examples produce natural replies.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.style_learner import StyleLearner
from openai import OpenAI
import config

# Show style examples
style = StyleLearner()
if style.available:
    print(f"Style examples loaded: {style.count} messages\n")
    print("=== Sample examples ===")
    for i, ex in enumerate(style.get_examples(5), 1):
        print(f"  {i}. {ex}")
    print()

    # Show the full prompt template (abbreviated)
    prompt = style.build_system_prompt(name=config.config.target_name, example_count=5)
    print("=== Prompt structure ===")
    print(prompt[:500])
    print(f"... (total {len(prompt)} chars)")
else:
    print("No style examples found!")

# Test DeepSeek API
print("\n=== Testing DeepSeek API ===")
cfg = config.config
client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_api_base)

# Get a proper prompt with examples
prompt_template = style.build_system_prompt(name=cfg.target_name, example_count=15)
test_message = "在干嘛呢今天？"
full_prompt = prompt_template.format(
    name=cfg.target_name,
    context="(暂无历史记录)",
    message=test_message,
)

print(f"Prompt length: {len(full_prompt)} chars")
print(f"Sending to {cfg.llm_model}...\n")

resp = client.chat.completions.create(
    model=cfg.llm_model,
    messages=[{"role": "user", "content": full_prompt}],
    temperature=0.8,
    max_tokens=500,
)
reply = resp.choices[0].message.content.strip()

print(f">> {test_message}")
print(f"<< {reply}")
print()

# Test 2
test_message2 = "明天要不要一起去吃饭？"
full_prompt2 = prompt_template.format(
    name=cfg.target_name,
    context=f"对方: {test_message}\n你: {reply}",
    message=test_message2,
)
resp2 = client.chat.completions.create(
    model=cfg.llm_model,
    messages=[{"role": "user", "content": full_prompt2}],
    temperature=0.8,
    max_tokens=500,
)
reply2 = resp2.choices[0].message.content.strip()
print(f">> {test_message2}")
print(f"<< {reply2}")
print()

# Test 3 - exam stress
test_message3 = "下周线代考试了，我好慌"
full_prompt3 = prompt_template.format(
    name=cfg.target_name,
    context="",
    message=test_message3,
)
resp3 = client.chat.completions.create(
    model=cfg.llm_model,
    messages=[{"role": "user", "content": full_prompt3}],
    temperature=0.8,
    max_tokens=500,
)
reply3 = resp3.choices[0].message.content.strip()
print(f">> {test_message3}")
print(f"<< {reply3}")
