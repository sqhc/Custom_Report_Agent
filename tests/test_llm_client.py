"""LLM 客户端与后端切换测试

全部使用 mock，**不触网**、不依赖 ollama / openai 是否安装。
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.llm_client import (
    BaseLLMClient,
    OllamaClient,
    OpenAICompatibleClient,
    get_llm_client,
    reset_llm_client,
)
from src.agent.reasoning import AIReasoner, Reasoner
from src.utils.config import Config, mask_secret
from src.utils.llm_errors import LLMClientError, LLMConfigError, LLMNotInstalledError

# 导入时快照，供测试后还原，避免测试之间互相污染
_ORIGINAL_CONFIG = {
    name: getattr(Config, name)
    for name in (
        'LLM_BACKEND', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL',
        'OPENAI_TIMEOUT', 'OPENAI_FALLBACK_MODEL', 'LLM_MAX_RETRIES',
        'LLM_RETRY_BACKOFF', 'OLLAMA_HOST', 'OLLAMA_MODEL', 'OLLAMA_TIMEOUT',
    )
}


class ConfigTestCase(unittest.TestCase):
    """提供 Config 打桩与全局客户端重置的基类"""

    def setUp(self):
        reset_llm_client()

    def tearDown(self):
        for name, value in _ORIGINAL_CONFIG.items():
            setattr(Config, name, value)
        reset_llm_client()

    @staticmethod
    def use_backend(backend: str, **overrides):
        """打桩 Config 属性（Config 在导入期读取环境变量，故需直接改类属性）"""
        Config.LLM_BACKEND = backend
        for name, value in overrides.items():
            setattr(Config, name, value)


def _fake_openai_module(create_side_effect=None, create_return=None):
    """构造一个可注入 sys.modules 的假 openai 模块

    同时提供 OpenAICompatibleClient 重试判定所需的异常类型。
    """
    module = types.ModuleType('openai')

    class APIError(Exception):
        def __init__(self, message, status_code=None):
            super().__init__(message)
            self.status_code = status_code

    class APITimeoutError(APIError):
        pass

    class APIConnectionError(APIError):
        pass

    class RateLimitError(APIError):
        pass

    class InternalServerError(APIError):
        pass

    module.APIError = APIError
    module.APITimeoutError = APITimeoutError
    module.APIConnectionError = APIConnectionError
    module.RateLimitError = RateLimitError
    module.InternalServerError = InternalServerError

    # 假的 OpenAI 客户端
    completions = MagicMock()
    if create_side_effect is not None:
        completions.create.side_effect = create_side_effect
    else:
        completions.create.return_value = create_return

    client_instance = MagicMock()
    client_instance.chat.completions = completions

    def _openai_factory(**kwargs):
        client_instance.init_kwargs = kwargs
        return client_instance

    module.OpenAI = _openai_factory
    module._client_instance = client_instance
    module._completions = completions
    return module


def _completion(content, finish="stop"):
    """构造一个假的 chat.completions.create 返回值"""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish
    response = MagicMock()
    response.choices = [choice]
    return response


class TestBackendSelection(ConfigTestCase):
    """工厂函数按 LLM_BACKEND 返回对应客户端"""

    def test_default_backend_is_ollama(self):
        """未设置 LLM_BACKEND 时返回 OllamaClient（向后兼容锚点）"""
        self.use_backend('ollama', OPENAI_API_KEY='')
        client = get_llm_client()
        self.assertIsInstance(client, OllamaClient)
        self.assertEqual(client.backend, 'ollama')
        self.assertEqual(client.model, Config.OLLAMA_MODEL)

    def test_openai_backend_returns_openai_client(self):
        """LLM_BACKEND=openai 且提供了 key 时返回 OpenAICompatibleClient"""
        self.use_backend('openai', OPENAI_API_KEY='sk-test', OPENAI_MODEL='deepseek-chat')
        fake = _fake_openai_module(create_return=_completion('hi'))
        with patch.dict(sys.modules, {'openai': fake}):
            client = get_llm_client()
        self.assertIsInstance(client, OpenAICompatibleClient)
        self.assertEqual(client.backend, 'openai')
        self.assertEqual(client.model, 'deepseek-chat')

    def test_backend_is_case_insensitive(self):
        """LLM_BACKEND 大小写不敏感"""
        self.use_backend('OpenAI', OPENAI_API_KEY='sk-test')
        fake = _fake_openai_module(create_return=_completion('hi'))
        with patch.dict(sys.modules, {'openai': fake}):
            client = get_llm_client()
        self.assertIsInstance(client, OpenAICompatibleClient)

    def test_invalid_backend_raises(self):
        """非法后端取值应报错并列出合法取值"""
        self.use_backend('anthropic')
        with self.assertRaises(LLMConfigError) as ctx:
            get_llm_client()
        message = str(ctx.exception)
        self.assertIn('ollama', message)
        self.assertIn('openai', message)

    def test_factory_returns_cached_instance(self):
        """默认返回单例；force_new 返回新实例"""
        self.use_backend('ollama')
        first = get_llm_client()
        self.assertIs(get_llm_client(), first)
        self.assertIsNot(get_llm_client(force_new=True), first)


class TestOpenAIConfigValidation(ConfigTestCase):
    """启动期配置校验"""

    def test_missing_api_key_raises_clear_error(self):
        """缺少 OPENAI_API_KEY 时启动即报错，且提示变量名"""
        self.use_backend('openai', OPENAI_API_KEY='')
        with self.assertRaises(LLMConfigError) as ctx:
            get_llm_client()
        message = str(ctx.exception)
        self.assertIn('OPENAI_API_KEY', message)
        self.assertIn('export', message)

    def test_blank_api_key_raises(self):
        """只有空白的 key 同样视为未提供"""
        self.use_backend('openai', OPENAI_API_KEY='   ')
        with self.assertRaises(LLMConfigError):
            get_llm_client()

    def test_ollama_backend_ignores_missing_api_key(self):
        """关键回归保护：ollama 模式下缺少 OPENAI_API_KEY 不得报错"""
        self.use_backend('ollama', OPENAI_API_KEY='', OPENAI_MODEL='')
        client = get_llm_client()  # 不应抛出异常
        self.assertIsInstance(client, OllamaClient)

    def test_invalid_base_url_raises(self):
        """OPENAI_BASE_URL 格式非法时报错"""
        self.use_backend('openai', OPENAI_API_KEY='sk-test', OPENAI_BASE_URL='ftp://x')
        with self.assertRaises(LLMConfigError) as ctx:
            get_llm_client()
        self.assertIn('OPENAI_BASE_URL', str(ctx.exception))

    def test_empty_model_raises(self):
        """OPENAI_MODEL 为空时报错"""
        self.use_backend('openai', OPENAI_API_KEY='sk-test', OPENAI_MODEL='')
        with self.assertRaises(LLMConfigError) as ctx:
            get_llm_client()
        self.assertIn('OPENAI_MODEL', str(ctx.exception))


class TestOpenAIClientCalling(ConfigTestCase):
    """远程调用与重试行为"""

    def _make_client(self, fake_module):
        with patch.dict(sys.modules, {'openai': fake_module}):
            return OpenAICompatibleClient(
                api_key='sk-test', base_url='https://api.test/v1',
                model='test-model', max_retries=3, retry_backoff=0,
            )

    def test_missing_openai_library_raises_helpful_error(self):
        """未安装 openai 时抛出含 pip 提示的错误，而非 ImportError"""
        self.use_backend('openai', OPENAI_API_KEY='sk-test')
        # 模拟 openai 未安装
        with patch.dict(sys.modules, {'openai': None}):
            with patch('builtins.__import__', side_effect=_raising_import('openai')):
                with self.assertRaises(LLMNotInstalledError) as ctx:
                    OpenAICompatibleClient(api_key='sk-test')
        message = str(ctx.exception)
        self.assertIn('openai', message.lower())

    def test_successful_chat(self):
        fake = _fake_openai_module(create_return=_completion('你好'))
        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            self.assertEqual(
                client.chat([{"role": "user", "content": "hi"}]), '你好'
            )

    def test_generate_builds_system_and_user_messages(self):
        fake = _fake_openai_module(create_return=_completion('ok'))
        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            client.generate('问题', system='你是助手')
        sent = fake._completions.create.call_args.kwargs['messages']
        self.assertEqual(sent[0], {"role": "system", "content": "你是助手"})
        self.assertEqual(sent[1], {"role": "user", "content": "问题"})

    def test_retries_on_500_then_succeeds(self):
        """5xx 可重试：失败两次后成功，且状态码出现在日志/异常路径中"""
        fake = _fake_openai_module()
        error = fake.InternalServerError('server boom', 500)
        fake._completions.create.side_effect = [error, error, _completion('恢复了')]

        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            result = client.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(result, '恢复了')
        self.assertEqual(fake._completions.create.call_count, 3)

    def test_retries_on_rate_limit(self):
        """429 限流可重试"""
        fake = _fake_openai_module()
        fake._completions.create.side_effect = [
            fake.RateLimitError('slow down', 429), _completion('ok')
        ]
        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), 'ok')
        self.assertEqual(fake._completions.create.call_count, 2)

    def test_no_retry_on_401(self):
        """401 属于不可重试错误：立即失败且消息含状态码"""
        fake = _fake_openai_module()
        fake._completions.create.side_effect = fake.APIError('bad key', 401)

        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            with self.assertRaises(LLMClientError) as ctx:
                client.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn('401', str(ctx.exception))
        self.assertEqual(fake._completions.create.call_count, 1)
        self.assertEqual(ctx.exception.attempts, 1)

    def test_no_retry_on_400(self):
        """400 参数错误不可重试"""
        fake = _fake_openai_module()
        fake._completions.create.side_effect = fake.APIError('bad request', 400)
        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            with self.assertRaises(LLMClientError):
                client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(fake._completions.create.call_count, 1)

    def test_exhausted_retries_reports_status_and_attempts(self):
        """重试耗尽后异常包含状态码与尝试次数"""
        fake = _fake_openai_module()
        fake._completions.create.side_effect = fake.APIError('still down', 503)

        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            with self.assertRaises(LLMClientError) as ctx:
                client.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertIn('503', str(ctx.exception))
        self.assertEqual(fake._completions.create.call_count, 3)

    def test_max_retries_configurable(self):
        """重试次数可配置"""
        fake = _fake_openai_module()
        fake._completions.create.side_effect = fake.APIError('down', 500)
        with patch.dict(sys.modules, {'openai': fake}):
            client = OpenAICompatibleClient(
                api_key='sk-test', model='m', max_retries=1, retry_backoff=0
            )
            with self.assertRaises(LLMClientError):
                client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(fake._completions.create.call_count, 1)

    def test_sdk_internal_retry_disabled(self):
        """确认关闭了 SDK 内建重试，避免双重重试"""
        fake = _fake_openai_module(create_return=_completion('ok'))
        self._make_client(fake)
        self.assertEqual(fake._client_instance.init_kwargs.get('max_retries'), 0)

    def test_null_content_returns_empty_string(self):
        """content 为 None 时返回空串而非崩溃"""
        fake = _fake_openai_module(create_return=_completion(None))
        client = self._make_client(fake)
        with patch.dict(sys.modules, {'openai': fake}):
            self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), '')

    def test_stream_skips_none_delta_content(self):
        """流式响应中 delta.content 为 None 的块应被跳过"""
        def _chunk(content):
            delta = MagicMock()
            delta.content = content
            choice = MagicMock()
            choice.delta = delta
            chunk = MagicMock()
            chunk.choices = [choice]
            return chunk

        fake = _fake_openai_module()
        fake._completions.create.return_value = [
            _chunk(None), _chunk('你'), _chunk(None), _chunk('好')
        ]
        client = self._make_client(fake)
        seen = []
        with patch.dict(sys.modules, {'openai': fake}):
            text = client.chat_stream(
                [{"role": "user", "content": "hi"}], callback=seen.append
            )
        self.assertEqual(text, '你好')
        self.assertEqual(seen, ['你', '好'])


class TestReasonerCompatibility(ConfigTestCase):
    """AIReasoner 对外接口保持不变"""

    def test_reasoner_alias(self):
        """Reasoner 是 AIReasoner 的别名"""
        self.assertIs(Reasoner, AIReasoner)

    def test_reasoner_uses_injected_client(self):
        """支持依赖注入，且公开属性仍然可用"""
        fake_client = MagicMock(spec=BaseLLMClient)
        fake_client.model = 'injected-model'
        fake_client.backend = 'ollama'
        fake_client.is_available.return_value = True

        reasoner = AIReasoner(client=fake_client)
        self.assertEqual(reasoner.model, 'injected-model')
        self.assertTrue(reasoner.is_available())

    def test_reasoner_default_is_ollama(self):
        """默认配置下 Reasoner 使用本地 Ollama"""
        self.use_backend('ollama')
        reasoner = AIReasoner()
        self.assertEqual(reasoner.client.backend, 'ollama')
        self.assertEqual(reasoner.model, Config.OLLAMA_MODEL)

    def test_chat_returns_none_on_failure(self):
        """调用失败时返回 None（与改造前一致，不抛异常）"""
        fake_client = MagicMock(spec=BaseLLMClient)
        fake_client.model = 'm'
        fake_client.backend = 'ollama'
        fake_client.is_available.return_value = True
        fake_client.chat.side_effect = LLMClientError('boom', status_code=500)

        reasoner = AIReasoner(client=fake_client)
        self.assertIsNone(reasoner.chat('hi'))

    def test_chat_unavailable_returns_none(self):
        """AI 不可用时返回 None"""
        fake_client = MagicMock(spec=BaseLLMClient)
        fake_client.model = 'm'
        fake_client.backend = 'ollama'
        fake_client.is_available.return_value = False

        reasoner = AIReasoner(client=fake_client)
        self.assertIsNone(reasoner.chat('hi'))
        self.assertFalse(reasoner.is_available())

    def test_analyze_data_parses_json(self):
        """analyze_data 仍能解析 JSON 响应"""
        fake_client = MagicMock(spec=BaseLLMClient)
        fake_client.model = 'm'
        fake_client.backend = 'ollama'
        fake_client.is_available.return_value = True
        fake_client.chat.return_value = '{"analysis": "ok", "columns": ["a"]}'

        reasoner = AIReasoner(client=fake_client)
        result = reasoner.analyze_data('preview', ['a'])
        self.assertEqual(result['analysis'], 'ok')

    def test_extract_customs_info_parses_markdown_json(self):
        """extract_customs_info 能去除 markdown 围栏"""
        fake_client = MagicMock(spec=BaseLLMClient)
        fake_client.model = 'm'
        fake_client.backend = 'ollama'
        fake_client.is_available.return_value = True
        fake_client.chat.return_value = '```json\n{"exporter": "ACME"}\n```'

        reasoner = AIReasoner(client=fake_client)
        result = reasoner.extract_customs_info('raw')
        self.assertEqual(result['exporter'], 'ACME')

    def test_extract_customs_info_failure_returns_error_dict(self):
        """提取失败时返回包含 error 的字典"""
        fake_client = MagicMock(spec=BaseLLMClient)
        fake_client.model = 'm'
        fake_client.backend = 'ollama'
        fake_client.is_available.return_value = True
        fake_client.chat.return_value = 'not json at all'

        reasoner = AIReasoner(client=fake_client)
        result = reasoner.extract_customs_info('raw')
        self.assertIn('error', result)


class TestLegacyClientBackend(ConfigTestCase):
    """legacy src/utils/llm_client.py 也遵守 LLM_BACKEND"""

    def test_legacy_defaults_to_ollama(self):
        from src.utils.llm_client import LLMClient, reset_llm_client as reset_legacy

        self.use_backend('ollama')
        reset_legacy()
        client = LLMClient()
        self.assertEqual(client.backend, 'ollama')
        self.assertEqual(client.primary_model, Config.OLLAMA_MODEL)

    def test_legacy_switches_to_openai(self):
        from src.utils.llm_client import LLMClient, reset_llm_client as reset_legacy

        self.use_backend(
            'openai', OPENAI_API_KEY='sk-test',
            OPENAI_MODEL='deepseek-chat', OPENAI_FALLBACK_MODEL='',
        )
        reset_legacy()
        client = LLMClient()
        self.assertEqual(client.backend, 'openai')
        self.assertEqual(client.primary_model, 'deepseek-chat')
        # 远程模式未配置降级模型时不应有默认降级模型
        self.assertEqual(client.fallback_model, '')

    def test_legacy_ollama_keeps_fallback_default(self):
        """ollama 模式的默认降级模型保持原样"""
        from src.utils.llm_client import LLMClient, reset_llm_client as reset_legacy

        self.use_backend('ollama')
        reset_legacy()
        client = LLMClient()
        self.assertEqual(client.fallback_model, 'glm-4.7-flash')

    def test_legacy_ollama_missing_key_is_fine(self):
        """ollama 模式缺少 OPENAI_API_KEY 不影响 legacy 工厂"""
        from src.utils.llm_client import get_llm_client as legacy_get, reset_llm_client as reset_legacy

        self.use_backend('ollama', OPENAI_API_KEY='')
        reset_legacy()
        client = legacy_get()
        self.assertEqual(client.backend, 'ollama')


class TestMaskSecret(unittest.TestCase):
    """密钥脱敏"""

    def test_masks_long_key(self):
        masked = mask_secret('sk-1234567890abcdef')
        self.assertNotIn('1234567890', masked)
        self.assertTrue(masked.startswith('sk-'))

    def test_short_key_fully_hidden(self):
        self.assertEqual(mask_secret('abc'), '***')

    def test_none_and_empty(self):
        self.assertEqual(mask_secret(None), '<未设置>')
        self.assertEqual(mask_secret(''), '<未设置>')


def _raising_import(blocked_name):
    """返回一个在导入指定模块时抛 ImportError 的 __import__ 替身"""
    import builtins
    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == blocked_name:
            raise ImportError(f"mocked: no module named {blocked_name}")
        return real_import(name, *args, **kwargs)

    return _import


if __name__ == '__main__':
    unittest.main(verbosity=2)
