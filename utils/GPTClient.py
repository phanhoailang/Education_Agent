from openai import AzureOpenAI

class GPTClient:
    def __init__(self, api_key, endpoint, model, api_version):
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        self.model = model

    def chat(self, messages, temperature=0.3, max_tokens=1500, timeout=30):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
        return response.choices[0].message.content.strip()

    def call(self, prompt: str, temperature=0.3, max_tokens=1500, timeout=30):
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
