from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        """genereate response based on the prompt"""
        pass

    @abstractmethod
    def generate_text_embedding(self, prompt: str) -> str:
        """genereate ebedding based on the prompt"""
        pass
