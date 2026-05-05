import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.memory import save_context
from backend.models.chat import ChatQueryRequest
from backend.routers.auth import get_current_user
from backend.services.admin_service import get_runtime_model_settings, record_query_audit
from backend.services.chat_service import (
    _build_cache_key,
    _build_confirmation_marker,
    _call_model_stream,
    _classify_and_generate_stream,
    _correct_sql,
    _detect_analysis_mode,
    _execute_sql,
    _generate_fallback_sql,
    _run_arima_tool,
    _render_chart,
    _build_analyst_prompt,
    _result_preview_to_json,
    build_session_context,
    resolve_intent_from_session,
)
from backend.services.security import validate_sql
from backend.services.session_service import (
    add_message,
    get_messages,
    update_title_if_placeholder,
    user_can_access_session,
)
from semantic_layer import get_cache, set_cache

router = APIRouter(prefix='/api/chat/stream', tags=['chat_stream'])


def _sse_event(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data_str = json.dumps(data, ensure_ascii=False)
    else:
        data_str = data
    return f'event: {event}\ndata: {data_str}\n\n'


@router.post('/query')
async def stream_query(req: ChatQueryRequest, user: dict = Depends(get_current_user)):
    is_admin = user['role'] in {'admin', 'superadmin'}
    if not user_can_access_session(req.session_id, user['username'], is_admin):
        raise HTTPException(status_code=404, detail='会话不存在或无权访问')

    async def generate() -> AsyncGenerator[str, None]:
        started_at = time.perf_counter()
        sql_text = ''
        chart_path = None
        result_preview = None
        answer = ''

        try:
            runtime = await asyncio.to_thread(get_runtime_model_settings)
            messages = await asyncio.to_thread(get_messages, req.session_id)
            context_package = build_session_context(messages)
            context_text = context_package.get('context_package_text') or context_package.get('context_text') or ''
            intent_plan = resolve_intent_from_session(req.question, context_package)
            cache_key = _build_cache_key(req.question, context_package.get('context_text', ''), intent_plan)
            cached = await asyncio.to_thread(get_cache, cache_key)
            if cached:
                yield _sse_event('executing', {'message': '命中缓存，正在整理回答...'})
                await asyncio.sleep(0.03)
                content = cached.get('answer_text', '')
                sql_text = cached.get('sql_text') or ''
                result_preview = cached.get('result_preview')
                chart_path = cached.get('chart_path')
                answer = content
                for chunk in _stream_text_chunks(content):
                    yield _sse_event('token', chunk)
                    await asyncio.sleep(0.01)
                yield _sse_event('done', {
                    'sql_text': sql_text or None,
                    'result_preview': result_preview,
                    'chart_url': chart_path,
                    'from_cache': True,
                })
                await _persist_result(
                    req.session_id,
                    req.question,
                    user['username'],
                    answer,
                    sql_text or None,
                    result_preview,
                    chart_path,
                    started_at,
                    'success',
                    None,
                    from_cache=True,
                )
                return

            if intent_plan.get('needs_confirmation'):
                answer = intent_plan.get('confirmation_question') or '我需要确认一下你的意图，请补充更多信息。'
                sql_text = _build_confirmation_marker(intent_plan)
                for chunk in _stream_text_chunks(answer):
                    yield _sse_event('token', chunk)
                    await asyncio.sleep(0.01)
                yield _sse_event('done', {
                    'sql_text': sql_text,
                    'result_preview': None,
                    'chart_url': None,
                    'from_cache': False,
                })
                await _persist_result(
                    req.session_id,
                    req.question,
                    user['username'],
                    answer,
                    sql_text,
                    None,
                    None,
                    started_at,
                    'success',
                    None,
                    from_cache=False,
                )
                return

            if intent_plan.get('intent_type') == 'forecast':
                arima_stages = [
                    '正在准备历史数据...',
                    '正在进行ARIMA预测...',
                    '正在生成图表...',
                ]
                for stage_message in arima_stages[:2]:
                    yield _sse_event('executing', {'message': stage_message})
                    await asyncio.sleep(0.03)

                tscode = str(intent_plan.get('tscode') or '').strip().upper()
                try:
                    n_days = int(intent_plan.get('n_days') or 7)
                except (TypeError, ValueError):
                    n_days = 7
                arima_result = await asyncio.to_thread(_run_arima_tool, tscode, n_days)
                yield _sse_event('executing', {'message': arima_stages[2]})
                await asyncio.sleep(0.03)

                answer = arima_result.get('content', '')
                sql_text = arima_result.get('sql_text') or ''
                result_preview = arima_result.get('result_preview')
                chart_path = arima_result.get('chart_path')
                status = arima_result.get('status', 'success')
                error_message = arima_result.get('error_message')

                if chart_path:
                    yield _sse_event('chart_generated', {'chart_path': chart_path})
                    await asyncio.sleep(0.03)

                for chunk in _stream_text_chunks(answer):
                    yield _sse_event('token', chunk)
                    await asyncio.sleep(0.01)

                yield _sse_event('done', {
                    'sql_text': sql_text or None,
                    'result_preview': result_preview,
                    'chart_url': chart_path,
                    'from_cache': False,
                })

                if status == 'success':
                    await asyncio.to_thread(
                        set_cache,
                        cache_key,
                        sql_text or None,
                        result_preview,
                        answer,
                        chart_path,
                        settings.query_cache_ttl,
                    )

                await _persist_result(
                    req.session_id,
                    req.question,
                    user['username'],
                    answer,
                    sql_text or None,
                    result_preview,
                    chart_path,
                    started_at,
                    status,
                    error_message,
                    from_cache=False,
                )
                return

            # Step 1+2 合并: 意图分类 + SQL 生成（流式输出，用户感知延迟从15-25s降至2-3s）
            yield _sse_event('thinking', {'message': '正在分析问题...'})
            await asyncio.sleep(0.03)
            resolved_prompt = str(intent_plan.get('normalized_question') or req.question)

            import queue as thread_queue
            thinking_token_queue: thread_queue.Queue[str] = thread_queue.Queue()

            def thinking_token_callback(token: str):
                thinking_token_queue.put(token)

            loop = asyncio.get_running_loop()
            classify_future = loop.run_in_executor(
                None,
                _classify_and_generate_stream,
                resolved_prompt,
                context_text,
                thinking_token_callback,
            )

            while not classify_future.done() or not thinking_token_queue.empty():
                try:
                    token = thinking_token_queue.get(timeout=0.05)
                    yield _sse_event('token', token)
                except thread_queue.Empty:
                    await asyncio.sleep(0.01)

            classify_result = classify_future.result()
            data_query = classify_result.get('data_query', True)
            reply = classify_result.get('reply', '')
            if not data_query:
                answer = reply or '你好！有什么股票数据需要查询吗？'
                for chunk in _stream_text_chunks(answer):
                    yield _sse_event('token', chunk)
                    await asyncio.sleep(0.01)
                yield _sse_event('done', {
                    'sql_text': None,
                    'result_preview': None,
                    'chart_url': None,
                    'from_cache': False,
                })
                await _persist_result(req.session_id, req.question, user['username'], answer, None, None, None, started_at, 'success', None)
                return

            sql_text = classify_result.get('sql', '')
            if not sql_text:
                sql_text = _generate_fallback_sql(resolved_prompt)
            sql_text = validate_sql(sql_text, settings.max_result_rows)

            yield _sse_event('executing', {'message': '正在执行查询...'})
            await asyncio.sleep(0.03)

            # Step 3: 执行 SQL（带重试修正）
            import pandas as pd
            df: pd.DataFrame | None = None
            last_error = ''
            max_retry = max(1, runtime['retry_count'] + 1)
            for attempt in range(max_retry):
                try:
                    df = await asyncio.to_thread(_execute_sql, sql_text)
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < max_retry - 1:
                        yield _sse_event('executing', {'message': f'查询出错，正在修正...（第{attempt + 1}次）'})
                        await asyncio.sleep(0.03)
                        correction = await asyncio.to_thread(_correct_sql, resolved_prompt, sql_text, last_error)
                        if correction.get('needs_sql', True) and correction.get('sql'):
                            sql_text = validate_sql(correction['sql'], settings.max_result_rows)
                        else:
                            answer = correction.get('answer', f'SQL 执行多次失败：{last_error}')
                            for chunk in _stream_text_chunks(answer):
                                yield _sse_event('token', chunk)
                                await asyncio.sleep(0.01)
                            yield _sse_event('done', {
                                'sql_text': sql_text,
                                'result_preview': None,
                                'chart_url': None,
                                'from_cache': False,
                            })
                            await _persist_result(req.session_id, req.question, user['username'], answer, sql_text, None, None, started_at, 'failed', last_error)
                            return
                    else:
                        answer = f'SQL 执行失败，已重试{max_retry}次。错误信息：{last_error}'
                        for chunk in _stream_text_chunks(answer):
                            yield _sse_event('token', chunk)
                            await asyncio.sleep(0.01)
                        yield _sse_event('done', {
                            'sql_text': sql_text,
                            'result_preview': None,
                            'chart_url': None,
                            'from_cache': False,
                        })
                        await _persist_result(req.session_id, req.question, user['username'], answer, sql_text, None, None, started_at, 'failed', last_error)
                        return

            if df is None or df.empty:
                answer = '查询结果为空。'
                for chunk in _stream_text_chunks(answer):
                    yield _sse_event('token', chunk)
                    await asyncio.sleep(0.01)
                yield _sse_event('done', {
                    'sql_text': sql_text,
                    'result_preview': None,
                    'chart_url': None,
                    'from_cache': False,
                })
                await _persist_result(req.session_id, req.question, user['username'], answer, sql_text, None, None, started_at, 'success', None)
                return

            # Step 4: 生成图表
            chart_path = await asyncio.to_thread(_render_chart, df)
            if chart_path:
                yield _sse_event('chart_generated', {'chart_path': chart_path})
                await asyncio.sleep(0.03)

            result_preview = await asyncio.to_thread(_result_preview_to_json, df)

            # Step 5: 流式分析
            yield _sse_event('summarizing', {'message': '正在分析数据...'})
            await asyncio.sleep(0.03)

            analysis_mode = _detect_analysis_mode(resolved_prompt)
            system_prompt = _build_analyst_prompt(resolved_prompt, df, analysis_mode)
            user_content = f'用户问题：{resolved_prompt}\n\nSQL：{sql_text}\n\n查询结果：\n{df.head(20).to_markdown(index=False)}'

            import queue as thread_queue_analysis
            token_queue: thread_queue_analysis.Queue[str] = thread_queue_analysis.Queue()

            def token_callback(token: str):
                token_queue.put(token)

            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(
                None,
                _call_model_stream,
                [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_content},
                ],
                token_callback,
                0.3,
            )

            while not future.done() or not token_queue.empty():
                try:
                    token = token_queue.get(timeout=0.05)
                    yield _sse_event('token', token)
                except thread_queue.Empty:
                    await asyncio.sleep(0.01)

            answer = future.result()
            if not answer.strip():
                answer = f'查询完成，返回 {len(df)} 行数据。\n\n{df.head(20).to_markdown(index=False)}'

            yield _sse_event('done', {
                'sql_text': sql_text,
                'result_preview': result_preview,
                'chart_url': chart_path,
                'from_cache': False,
            })

            set_cache(cache_key, sql_text, result_preview, answer, chart_path, settings.query_cache_ttl)
            await _persist_result(req.session_id, req.question, user['username'], answer, sql_text, result_preview, chart_path, started_at, 'success', None)

        except Exception as exc:
            yield _sse_event('error', {'message': str(exc)})
            try:
                await _persist_result(req.session_id, req.question, user['username'], '', None, None, None, started_at, 'failed', str(exc))
            except Exception:
                pass

    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


async def _persist_result(
    session_id: str,
    question: str,
    username: str,
    answer: str,
    sql_text: str | None,
    result_preview: str | None,
    chart_path: str | None,
    started_at: float,
    status: str,
    error_message: str | None,
    from_cache: bool = False,
):
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    try:
        await asyncio.to_thread(save_context, session_id, question, answer)
    except Exception:
        pass
    try:
        await asyncio.to_thread(add_message, session_id, 'user', question)
    except Exception:
        pass
    try:
        await asyncio.to_thread(
            add_message, session_id, 'assistant', answer,
            sql_text=sql_text, result_preview=result_preview, chart_path=chart_path,
        )
    except Exception:
        pass
    try:
        await asyncio.to_thread(update_title_if_placeholder, session_id, question)
    except Exception:
        pass
    try:
        await asyncio.to_thread(
            record_query_audit,
            username=username,
            session_id=session_id,
            question=question,
            sql_text=sql_text,
            duration_ms=duration_ms,
            from_cache=from_cache,
            chart_generated=bool(chart_path),
            status=status,
            error_message=error_message,
        )
    except Exception:
        pass


def _stream_text_chunks(text: str, chunk_size: int = 24) -> list[str]:
    clean_text = text or ''
    return [clean_text[index:index + chunk_size] for index in range(0, len(clean_text), chunk_size)] or ['']
