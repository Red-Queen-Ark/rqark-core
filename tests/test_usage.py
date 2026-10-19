from openai.types.chat import ChatCompletionChunk
from openai.types.completion_usage import CompletionTokensDetails, CompletionUsage, PromptTokensDetails

from rqark_core._core.stream import ChunkHandler
from rqark_core.types.chat import AssistantMessage, Chunk, Usage


def _chunk(usage: CompletionUsage) -> ChatCompletionChunk:
    return ChatCompletionChunk(id='c1', choices=[], created=0, model='m', object='chat.completion.chunk', usage=usage)


async def _handle(usage: CompletionUsage) -> ChunkHandler:
    handler = ChunkHandler(_noop)
    await handler.handle(_chunk(usage))
    return handler


async def _noop(chunk: Chunk) -> None:
    return None


def test_usage_details_default_to_zero_and_keep_positional_order():
    usage = Usage(1, 2, 3)
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (1, 2, 3)
    assert usage.cached_tokens == 0
    assert usage.reasoning_tokens == 0


def test_cache_hit_rate_is_cached_over_prompt():
    assert Usage(100, 10, 110, cached_tokens=40).cache_hit_rate == 0.4
    assert Usage(0, 10, 10, cached_tokens=0).cache_hit_rate == 0.0


async def test_usage_reads_cached_and_reasoning_tokens():
    handler = await _handle(CompletionUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120, prompt_tokens_details=PromptTokensDetails(cached_tokens=64), completion_tokens_details=CompletionTokensDetails(reasoning_tokens=8)))
    assert handler.usage == Usage(100, 20, 120, cached_tokens=64, reasoning_tokens=8)


async def test_usage_tolerates_missing_details():
    handler = await _handle(CompletionUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120))
    assert handler.usage == Usage(100, 20, 120, cached_tokens=0, reasoning_tokens=0)


async def test_usage_tolerates_details_without_cached_or_reasoning():
    handler = await _handle(CompletionUsage(prompt_tokens=7, completion_tokens=3, total_tokens=10, prompt_tokens_details=PromptTokensDetails(audio_tokens=2), completion_tokens_details=CompletionTokensDetails(audio_tokens=1)))
    assert handler.usage == Usage(7, 3, 10, cached_tokens=0, reasoning_tokens=0)


async def test_empty_usage_does_not_replace_a_recorded_one():
    handler = ChunkHandler(_noop)
    assert handler.usage is None
    await handler.handle(_chunk(CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2, prompt_tokens_details=PromptTokensDetails(cached_tokens=1))))
    await handler.handle(ChatCompletionChunk(id='c2', choices=[], created=0, model='m', object='chat.completion.chunk'))
    assert handler.usage == Usage(1, 1, 2, cached_tokens=1)


async def test_assistant_message_carries_usage_into_to_dict():
    message = AssistantMessage('yo', usage=Usage(100, 20, 120, cached_tokens=64, reasoning_tokens=8))
    assert message.to_dict()['usage'] == {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120, 'cached_tokens': 64, 'reasoning_tokens': 8}


def test_to_dict_omits_usage_when_absent():
    assert 'usage' not in AssistantMessage('yo').to_dict()


def test_usage_round_trips_through_to_dict():
    original = Usage(10, 5, 15, cached_tokens=3, reasoning_tokens=2)
    assert Usage(**original.to_dict()) == original
