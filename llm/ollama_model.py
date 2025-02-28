from contextlib import contextmanager
import logging
from ollama import Client
from typing import Optional, List, Dict

import requests
from .base_llm import BaseLLM

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OllamaModel(BaseLLM):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "DeepSeek-R1-Distill-Qwen-14B:Q6_K_L",
        ebedding_model_name: str = "nomic-embed-text-v1:Q6_K",
        user_role: str = "user",
        system_prompt: Optional[str] = None,
    ):
        """
        初始化 Ollama 模型接口。

        :param base_url: Ollama 服务器地址。
        :param model_name: 模型名称。
        :param system_prompt: （可选）系统级提示词，用于设定模型行为。
        :param temperature: 控制输出多样性，默认0.2（值越低，输出越确定）。
        """
        self.base_url = base_url
        self.model_name = model_name
        self.bedding_model_name = ebedding_model_name
        self.user_role = user_role
        self.system_prompt = system_prompt
        self.client = Client(host=base_url, timeout=300)

    @contextmanager
    def _api_session(self):
        """Context manager for API connections"""
        try:
            yield self.client
        finally:
            if hasattr(self, "client") and self.client:
                self.client.close()
                logger.debug("Closed API connection")

    def generate_response(
        self, prompt: str, additional_messages: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        调用 Ollama API 生成响应。

        :param prompt: 用户输入内容。
        :param additional_messages: （可选）额外历史消息，可用于多轮对话。
        :return: 模型返回的文本响应。
        """
        messages = []

        # 添加 system prompt（如果设置）
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 添加额外对话历史
        if additional_messages:
            messages.extend(additional_messages)

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{"role": self.user_role, "content": prompt}],
            )

            logger.info(f"Response from Ollama model: {response}")

            if not response:
                logger.error("None response format from LLM")
                return None

            return response.message.content.strip()
        except requests.exceptions.Timeout:
            logger.error("Request to Ollama API timed out")
            # 你可以选择返回一个默认值或执行其他操作
            return None
        except Exception as e:
            raise RuntimeError(f"Ollama Client 请求失败: {e}")

    def generate_text_embedding(self, prompt):
        response = self.client.embeddings(model=self.bedding_model_name, prompt=prompt)
        return response.get("embedding", [])

    def __del__(self):
        """Cleanup method to ensure resources are properly released"""
        try:
            self.client = None
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
