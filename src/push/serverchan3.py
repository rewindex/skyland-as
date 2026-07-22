import json
import logging
import re
from datetime import date

import requests


def _clean_game_name(game: str) -> str:
    return re.sub(r'^[^\w\u4e00-\u9fff]+', '', game).strip() or '未知'


def _escape_table_cell(text: str) -> str:
    return text.replace('|', '\\|').replace('\n', '<br>')


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
    """
    确定整体签到状态
    :param entries: 结构化签到结果
    :return: (emoji, 状态文案)
    """
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


def _build_markdown_table(entries: list[dict[str, str]]) -> str:
    lines = [
        '| 游戏 | 角色 | 渠道 | 状态 | 详情 |',
        '| --- | --- | --- | --- | --- |',
    ]
    for entry in entries:
        lines.append(
            '| {game} | {role} | {channel} | {status} | {detail} |'.format(
                game=_escape_table_cell(entry['game']),
                role=_escape_table_cell(entry['role']),
                channel=_escape_table_cell(entry['channel']),
                status=_escape_table_cell(entry['status']),
                detail=_escape_table_cell(entry['detail']),
            )
        )
    return '\n'.join(lines)


def _build_short_summary(status_text: str, success_count: int, failure_count: int, error_count: int) -> str:
    parts = [status_text, f'成功 {success_count}', f'失败 {failure_count}']
    if error_count:
        parts.append(f'异常 {error_count}')
    return '，'.join(parts)


def _format_serverchan_desp(entries: list[dict[str, str]], status_text: str) -> str:
    """
    格式化 Server 酱推送内容
    :param entries: 结构化签到结果日志列表
    :param status_text: 整体状态文案
    :return: 格式化后的推送内容
    """
    if not entries:
        return '今日无可用账号或无输出'

    success_count, failure_count, error_count = _count_status(entries)
    lines = [
        '## 森空岛自动签到结果',
        '',
        f'**状态**：{status_text}  ',
        f'**日期**：{date.today().strftime("%Y-%m-%d")}  ',
        f'**成功**：{success_count}  ',
        f'**失败**：{failure_count}  ',
    ]
    if error_count:
        lines.append(f'**异常**：{error_count}  ')
    lines.extend([
        '',
        _build_markdown_table(entries),
    ])
    return '\n'.join(lines)


def push_serverchan3(all_logs: list[str], sendkey: str = '', uid: str = ''):
    """
    Server 酱³ 推送
    通过运行配置控制：
      sendkey: 必填
      uid: 可选（若不设，将自动从 sendkey 中提取）
    :param all_logs: 签到结果日志列表
    """
    sendkey = sendkey.strip()
    if not sendkey:
        logging.info("未设置 SC3_SENDKEY，跳过 Server 酱 推送")
        return

    uid = uid.strip() or None

    entries = [_parse_log_entry(log) for log in all_logs]
    emoji, status_text = _determine_status(entries)
    title = f'{emoji} | 森空岛自动签到成果 - {date.today().strftime("%Y-%m-%d")}'
    success_count, failure_count, error_count = _count_status(entries)
    short = _build_short_summary(status_text, success_count, failure_count, error_count)

    # 格式化推送内容
    desp = _format_serverchan_desp(entries, status_text)

    # 构建 API 地址和请求参数
    api = f"https://sctapi.ftqq.com/{sendkey}.send"
    payload = {
        "title": title or "通知",
        "short": short,
        "desp": desp or "",
    }

    # 发送请求
    try:
        response = requests.post(api, json=payload, timeout=10)
        if response.status_code == 200:
            # 尝试解析响应
            try:
                result = response.json()
                if result.get('ok') or result.get('code') == 0:
                    logging.info("Server 酱 推送成功")
                else:
                    logging.error(f"Server 酱 推送失败：{result.get('message', '未知错误')}")
            except json.JSONDecodeError:
                logging.warning("Server 酱 推送响应不是有效的 JSON")
                logging.info("Server 酱 推送成功")
        else:
            logging.error(f"Server 酱 推送失败，HTTP 状态码：{response.status_code}, 响应：{response.text}")
    except requests.RequestException as e:
        logging.error(f"Server 酱 推送网络错误", exc_info=e)
    except Exception as e:
        logging.error(f"Server 酱 推送未知错误", exc_info=e)
