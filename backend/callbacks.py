from langchain_core.callbacks import BaseCallbackHandler
from logger_utils import get_daily_logger


class ChatBICallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.log = get_daily_logger('langchain')

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.log.info("LLM 开始调用: %s", serialized.get("name", "unknown"))

    def on_llm_end(self, response, **kwargs):
        token_info = ""
        if hasattr(response, 'llm_output') and response.llm_output:
            token_info = f" tokens={response.llm_output}"
        self.log.info("LLM 调用完成%s", token_info)

    def on_llm_error(self, error, **kwargs):
        self.log.error("LLM 调用失败: %s", error)

    def on_chain_start(self, serialized, inputs, **kwargs):
        self.log.info("节点开始: %s", serialized.get("name", "unknown"))

    def on_chain_end(self, outputs, **kwargs):
        self.log.info("节点完成")

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.log.info("SQL 开始执行: %s", input_str)
