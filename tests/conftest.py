import sys
import types


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class _Filter:
    class EventMessageType:
        ALL = "ALL"

    def command(self, *args, **kwargs):
        return lambda func: func

    def event_message_type(self, *args, **kwargs):
        return lambda func: func

    def on_llm_request(self, *args, **kwargs):
        return lambda func: func

    def on_agent_begin(self, *args, **kwargs):
        return lambda func: func


class _Plain:
    def __init__(self, text):
        self.text = text


class _Record:
    type = "record"

    def __init__(self, file=None, url=None, path=None, data=None):
        self.file = file
        self.url = url
        self.path = path
        self.data = data


class _ProviderRequest:
    def __init__(self):
        self.prompt = ""
        self.image_urls = []
        self.audio_urls = []
        self.extra_user_content_parts = []


class _Timeout:
    def __init__(self, *args, **kwargs):
        pass


class _AsyncClient:
    def __init__(self, *args, **kwargs):
        pass


api = types.ModuleType("astrbot.api")
api.AstrBotConfig = dict
api.logger = _Logger()

message_components = types.ModuleType("astrbot.api.message_components")
message_components.Plain = _Plain
message_components.Record = _Record

event = types.ModuleType("astrbot.api.event")
event.AstrMessageEvent = object
event.filter = _Filter()

provider = types.ModuleType("astrbot.api.provider")
provider.ProviderRequest = _ProviderRequest

class _Star:
    def __init__(self, context=None):
        self.context = context


class _Context:
    def __init__(self):
        self.registered_web_apis = []

    def register_web_api(self, route, view_handler, methods, desc):
        self.registered_web_apis.append((route, view_handler, methods, desc))


star = types.ModuleType("astrbot.api.star")
star.Context = _Context
star.Star = _Star

core_star = types.ModuleType("astrbot.core.star.star")
core_star.StarMetadata = type("StarMetadata", (), {})
core_provider_entities = types.ModuleType("astrbot.core.provider.entities")
core_provider_entities.ProviderRequest = _ProviderRequest

httpx = types.ModuleType("httpx")
httpx.Timeout = _Timeout
httpx.AsyncClient = _AsyncClient
httpx.HTTPError = Exception

sys.modules.setdefault("astrbot", types.ModuleType("astrbot"))
sys.modules["astrbot.api"] = api
sys.modules["astrbot.api.message_components"] = message_components
sys.modules["astrbot.api.event"] = event
sys.modules["astrbot.api.provider"] = provider
sys.modules["astrbot.api.star"] = star
sys.modules.setdefault("astrbot.core", types.ModuleType("astrbot.core"))
sys.modules.setdefault("astrbot.core.star", types.ModuleType("astrbot.core.star"))
sys.modules.setdefault("astrbot.core.provider", types.ModuleType("astrbot.core.provider"))
sys.modules["astrbot.core.star.star"] = core_star
sys.modules["astrbot.core.provider.entities"] = core_provider_entities
sys.modules["httpx"] = httpx
