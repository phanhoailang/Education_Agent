import google.generativeai as genai
from typing import List, Dict, Any, Optional

class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, 
             max_tokens: int = 1500, timeout: int = 30) -> str:
        try:
            # Convert OpenAI format to Gemini format
            gemini_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    gemini_messages.append({
                        "role": "user",
                        "parts": [msg["content"]]
                    })
                elif msg["role"] == "assistant":
                    gemini_messages.append({
                        "role": "model", 
                        "parts": [msg["content"]]
                    })
            response = self.model.generate_content(
                gemini_messages,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def call(self, prompt: str, temperature: float = 0.3, 
             max_tokens: int = 1500, timeout: int = 30) -> str:
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )