from utils.GPTClient import GPTClient
import time

class SearchGPTClient(GPTClient):
    def __init__(self, *args, max_retries=3, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_retries = max_retries

    def call(self, prompt: str, temperature=0.3, max_tokens=1500) -> str:
        for attempt in range(self.max_retries):
            try:
                return super().call(prompt, temperature, max_tokens)
            except Exception as e:
                print(f"Retry {attempt+1}/{self.max_retries} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
