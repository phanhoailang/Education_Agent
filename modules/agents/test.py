from modules.agents.SlideContentWriterAgent import SlideContentWriterAgent
import os
from dotenv import load_dotenv
# Load environment variables

# Mock LLM cho test
class MockLLM:
    def chat(self, messages, temperature=0.4):
        return '{"meta": {"title": "Test"}, "slides": [{"type": "title", "title": "Test Slide", "bullets": [], "speaker_notes": "Test"}]}'

# Test
agent = SlideContentWriterAgent(MockLLM())
if agent.authenticate():
    print("🎉 Ready to create slides!")