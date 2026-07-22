import html
import json
import logging
import re
from datetime import date

import requests


def _clean_game_name(game: str) -> str:
    return re.sub(r'^[^\w\u4e00-\u9fff]+', '', game).strip() or '未知'


def _normalize_detail(detail: str) -> str:
    return detail.strip().replace(',', '、')


def _parse_log_entry(log: str) -> dict[str, str]:
    text = log.strip()
    success_pattern = re.compile(
        r'^\[(?P<game>[^\]]+)\]角色(?P<role>.*)\((?P<channel>.*)\)签到成功，获得了[:：]?(?P<detail>.+)$'
    )
    failure_pattern = re.compile(
        r'^\[(?P<game>[^\]]+)\]角色(?P<role>.*)\((?P<channel>.*)\)签到失败了！原因[:：](?P<detail>.+)$'
    )
    generic_failure_pattern = re.compile(r'^签到失败，原因[:：](?P<detail>.+)$')

    match = success_pattern.match(text)
    if match:
        data = match.groupdict()
        return {
            'game': _clean_game_name(data['game']),
            'role': data['role'].strip() or '未知',
            'channel': data['channel'].strip() or '未知',
            'status': '✅ 成功',
            'detail': _normalize_detail(data['detail']),
        }

    match = failure_pattern.match(text)
    if match:
        data = match.groupdict()
        return {
            'game': _clean_game_name(data['game']),
            'role': data['role'].strip() or '未知',
            'channel': data['channel'].strip() or '未知',
            'status': '❌ 失败',
            'detail': data['detail'].strip() or '未知原因',
        }

    match = generic_failure_pattern.match(text)
    if match:
        return {
            'game': '未知',
            'role': '未知',
            'channel': '未知',
            'status': '⚠️ 异常',
            'detail': match.group('detail').strip() or text,
        }

    return {
        'game': '未知',
        'role': '未知',
        'channel': '未知',
        'status': '⚠️ 异常',
        'detail': text or '未知输出',
    }


def _determine_status(entries: list[dict[str, str]]) -> tuple[str, str]:
    if not entries:
        return '✅', '无输出'

    has_success = False
    has_failure = False
    has_error = False

    for entry in entries:
        status = entry['status']
        if status == '✅ 成功':
            has_success = True
        elif status == '❌ 失败':
            has_failure = True
        else:
            has_error = True

    if not has_success and (has_failure or has_error):
        return '❌', '全部失败'
    if has_failure or has_error:
        return '⚠️', '部分成功'
    return '✅', '全部成功'


def _count_status(entries: list[dict[str, str]]) -> tuple[int, int, int]:
    success_count = sum(1 for entry in entries if entry['status'] == '✅ 成功')
    failure_count = sum(1 for entry in entries if entry['status'] == '❌ 失败')
    error_count = sum(1 for entry in entries if entry['status'] == '⚠️ 异常')
    return success_count, failure_count, error_count


def _build_short_summary(status_text: str, success_count: int, failure_count: int, error_count: int) -> str:
    parts = [status_text, f'成功 {success_count}', f'失败 {failure_count}']
    if error_count:
        parts.append(f'异常 {error_count}')
    return '，'.join(parts)


def _escape_html(text: str) -> str:
    return html.escape(text)


def _group_by_game(entries: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for entry in entries:
        game = entry['game']
        if game not in groups:
            groups[game] = []
        groups[game].append(entry)
    return groups


def _format_telegram_message(entries: list[dict[str, str]], status_text: str, emoji: str) -> str:
    if not entries:
        return f'{emoji} <b>森空岛自动签到结果</b>\n\n今日无可用账号或无输出'

    success_count, failure_count, error_count = _count_status(entries)
    short = _build_short_summary(status_text, success_count, failure_count, error_count)

    lines = [
        f'{emoji} <b>森空岛自动签到结果</b>',
        '',
        f'📅 日期：{date.today().strftime("%Y-%m-%d")}',
        f'📊 {_escape_html(short)}',
        '',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    groups = _group_by_game(entries)
    for game, game_entries in groups.items():
        lines.append(f'🎮 <b>{_escape_html(game)}</b>')
        for entry in game_entries:
            role = _escape_html(entry['role'])
            channel = _escape_html(entry['channel'])
            status = _escape_html(entry['status'])
            detail = _escape_html(entry['detail'])
            lines.append(f'   {role}（{channel}）- {status}')
            lines.append(f'      {detail}')
        lines.append('')

    return '\n'.join(lines)


def push_telegram(all_logs: list[str], bot_token: str = '', chat_id: str = ''):
    bot_token = bot_token.strip()
    chat_id = chat_id.strip()
    if not bot_token:
        logging.info("未设置 TG_BOT_TOKEN，跳过 Telegram 推送")
        return
    if not chat_id:
        logging.info("未设置 TG_CHAT_ID，跳过 Telegram 推送")
        return

    entries = [_parse_log_entry(log) for log in all_logs]
    emoji, status_text = _determine_status(entries)

    text = _format_telegram_message(entries, status_text, emoji)

    api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(api, json=payload, timeout=10)
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('ok'):
                    logging.info("Telegram 推送成功")
                else:
                    logging.error(f"Telegram 推送失败：{result.get('description', '未知错误')}")
            except json.JSONDecodeError:
                logging.warning("Telegram 推送响应不是有效的 JSON")
                logging.info("Telegram 推送成功")
        else:
            logging.error(f"Telegram 推送失败，HTTP 状态码：{response.status_code}, 响应：{response.text}")
    except requests.RequestException as e:
        logging.error(f"Telegram 推送网络错误", exc_info=e)
    except Exception as e:
        logging.error(f"Telegram 推送未知错误", exc_info=e)
