"""集成测试：使用**真实 openai SDK** 对接本地 mock HTTP 服务

与 ``test_llm_client.py``（全 mock，永远运行）不同，本文件验证真实的
HTTP 交互细节：请求路径、鉴权头、请求体结构、SSE 流式解析、
以及真实 SDK 抛出的异常是否被正确映射为带状态码的重试行为。

若未安装 ``openai``，整个模块会被跳过（不影响本地 Ollama 模式的使用者）。

运行：
    pip install "openai>=1.0.0"
    pytest tests/test_llm_integration.py -v
"""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import Config
from src.utils.llm_errors import LLMClientError

try:
    import openai  # noqa: F401
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def _completion(text):
    return {
        "id": "chatcmpl-mock", "object": "chat.completion", "created": 0,
        "model": "mock-model",
        "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": text},
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class _MockHandler(BaseHTTPRequestHandler):
    """按预设脚本依次返回响应的 mock OpenAI 服务"""

    plan = []
    log = []
    stream_body = b''

    def log_message(self, *args):
        pass  # 静音访问日志

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length) or b'{}')
        _MockHandler.log.append({
            'path': self.path,
            'auth': self.headers.get('Authorization'),
            'body': body,
        })

        if _MockHandler.stream_body:
            data = _MockHandler.stream_body
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        status, payload = _MockHandler.plan.pop(0) if _MockHandler.plan else (200, None)
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@unittest.skipUnless(OPENAI_AVAILABLE, 'openai 未安装，跳过集成测试')
class TestOpenAIIntegration(unittest.TestCase):
    """真实 SDK + mock 服务的端到端行为"""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), _MockHandler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _MockHandler.plan = []
        _MockHandler.log = []
        _MockHandler.stream_body = b''
        self._orig = {n: getattr(Config, n) for n in
                      ('LLM_BACKEND', 'OPENAI_API_KEY', 'OPENAI_BASE_URL',
                       'OPENAI_MODEL', 'OPENAI_FALLBACK_MODEL')}
        Config.LLM_BACKEND = 'openai'
        Config.OPENAI_API_KEY = 'sk-integration'
        Config.OPENAI_BASE_URL = self.base_url
        Config.OPENAI_MODEL = 'mock-model'
        Config.OPENAI_FALLBACK_MODEL = ''

    def tearDown(self):
        for name, value in self._orig.items():
            setattr(Config, name, value)

    def _client(self, max_retries=3, **kwargs):
        from src.agent.llm_client import OpenAICompatibleClient
        return OpenAICompatibleClient(
            api_key='sk-integration', base_url=self.base_url,
            model='mock-model', max_retries=max_retries, retry_backoff=0, **kwargs
        )

    def test_real_request_shape(self):
        """验证真实 HTTP 请求的路径、鉴权头与请求体"""
        _MockHandler.plan.append((200, _completion('你好')))
        client = self._client()
        self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), '你好')

        req = _MockHandler.log[-1]
        self.assertEqual(req['path'], '/v1/chat/completions')
        self.assertEqual(req['auth'], 'Bearer sk-integration')
        self.assertEqual(req['body']['model'], 'mock-model')
        self.assertEqual(req['body']['messages'], [{"role": "user", "content": "hi"}])

    def test_generate_injects_system_message(self):
        _MockHandler.plan.append((200, _completion('ok')))
        client = self._client()
        client.generate('问题', system='系统')
        roles = [m['role'] for m in _MockHandler.log[-1]['body']['messages']]
        self.assertEqual(roles, ['system', 'user'])

    def test_401_not_retried(self):
        """真实 SDK 的 401 异常应映射为不可重试错误"""
        _MockHandler.plan.append((401, {"error": {"message": "invalid api key"}}))
        client = self._client()
        with self.assertRaises(LLMClientError) as ctx:
            client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(len(_MockHandler.log), 1)

    def test_429_retried_then_succeeds(self):
        _MockHandler.plan.extend([
            (429, {"error": {"message": "slow down"}}),
            (429, {"error": {"message": "slow down"}}),
            (200, _completion('重试成功')),
        ])
        client = self._client()
        self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), '重试成功')
        self.assertEqual(len(_MockHandler.log), 3)

    def test_500_exhausts_and_reports_status(self):
        _MockHandler.plan.extend([(500, None)] * 3)
        client = self._client()
        with self.assertRaises(LLMClientError) as ctx:
            client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertEqual(len(_MockHandler.log), 3)

    def test_real_sse_streaming(self):
        """真实 SSE 流式响应解析"""
        chunks = [None, '流', None, '式', '好']
        parts = []
        for text in chunks:
            payload = {
                "id": "c", "object": "chat.completion.chunk", "created": 0,
                "model": "m",
                "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
            }
            parts.append(b'data: ' + json.dumps(payload).encode() + b'\n\n')
        _MockHandler.stream_body = b''.join(parts) + b'data: [DONE]\n\n'

        client = self._client()
        seen = []
        text = client.chat_stream([{"role": "user", "content": "hi"}], callback=seen.append)
        self.assertEqual(text, '流式好')
        self.assertEqual(seen, ['流', '式', '好'])

    def test_reasoner_end_to_end_over_http(self):
        """AIReasoner 远程链路端到端可用"""
        from src.agent.reasoning import AIReasoner
        from src.agent.llm_client import reset_llm_client

        reset_llm_client()
        _MockHandler.plan.append(
            (200, _completion('{"analysis": "远程分析成功"}'))
        )
        reasoner = AIReasoner()
        self.assertEqual(reasoner.client.backend, 'openai')
        self.assertEqual(reasoner.analyze_data('preview', ['a'])['analysis'], '远程分析成功')

        _MockHandler.plan.append((200, _completion('```json\n{"exporter": "ACME"}\n```')))
        self.assertEqual(reasoner.extract_customs_info('raw')['exporter'], 'ACME')
        reset_llm_client()


if __name__ == '__main__':
    unittest.main(verbosity=2)
