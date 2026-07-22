# skyland.py from FancyCabbage/skyland-auto-sign(master#4da03e0) 
# !! Modified
import hashlib
import hmac
import json
import logging
import re
import threading
import time
from urllib import parse

import requests

from SecuritySm import get_d_id

app_code = '4ca99fa6b56cc2ba'

http_local = threading.local()
header = {
    'cred': '',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1',
    'Accept-Encoding': 'gzip',
    'Connection': 'close',
    'X-Requested-With': 'com.hypergryph.skland'
}
header_login = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1',
    'Accept-Encoding': 'gzip',
    'Connection': 'close',
    'dId': get_d_id(),
    'X-Requested-With': 'com.hypergryph.skland'
}

# 签名请求头一定要这个顺序，否则失败
# timestamp是必填的,其它三个随便填,不要为none即可
header_for_sign = {
    'platform': '3',
    'timestamp': '',
    'dId': header_login['dId'],
    'vName': '1.0.0'
}

# 签到url
sign_url_mapping = {
    'arknights': 'https://zonai.skland.com/api/v1/game/attendance',
    'endfield': 'https://zonai.skland.com/web/v1/game/endfield/attendance'
}

# 绑定的角色url
binding_url = "https://zonai.skland.com/api/v1/game/player/binding"
# 使用token获得认证代码
grant_code_url = "https://as.hypergryph.com/user/oauth2/v2/grant"
# 使用认证代码获得cred
cred_code_url = "https://zonai.skland.com/web/v1/user/auth/generate_cred_by_code"
# refresh
refresh_token_url = "https://zonai.skland.com/web/v1/auth/refresh"


game_name_mapping = {
    'arknights': '明日方舟',
    'endfield': '明日方舟：终末地',
}


def _mask_token(token: str) -> str:
    if not token:
        return 'unknown'
    if len(token) <= 8:
        return f'{token[:2]}***'
    return f'{token[:4]}...{token[-4:]}'


def _display_game_name(game: str) -> str:
    return game_name_mapping.get(game, game)


def _display_games(games: list[str]) -> str:
    return ', '.join(_display_game_name(game) for game in games)


def _summarize_logs(logs: list[str]) -> tuple[int, int, int]:
    success_count = 0
    failure_count = 0
    error_count = 0
    for log in logs:
        if '签到成功' in log:
            success_count += 1
        elif '签到失败了' in log:
            failure_count += 1
        else:
            error_count += 1
    return success_count, failure_count, error_count


def _extract_game_name_from_log(log: str) -> str:
    match = re.match(r'^\[(?P<game>[^\]]+)\]', log)
    if not match:
        return '未知'
    return re.sub(r'^[^\w\u4e00-\u9fff]+', '', match.group('game')).strip() or '未知'


def _summarize_logs_by_game(logs: list[str]) -> list[str]:
    summary: dict[str, dict[str, int]] = {}
    for log in logs:
        game = _extract_game_name_from_log(log)
        if game not in summary:
            summary[game] = {
                'success': 0,
                'failure': 0,
                'error': 0,
            }
        if '签到成功' in log:
            summary[game]['success'] += 1
        elif '签到失败了' in log:
            summary[game]['failure'] += 1
        else:
            summary[game]['error'] += 1

    lines = []
    for game, counts in summary.items():
        lines.append(
            f'{game}：成功 {counts["success"]}，失败 {counts["failure"]}，异常 {counts["error"]}'
        )
    return lines


def _format_runtime_log(log: str) -> str:
    success_pattern = re.compile(
        r'^\[(?P<game>[^\]]+)\]角色(?P<role>.*)\((?P<channel>.*)\)签到成功，获得了[:：]?(?P<detail>.+)$'
    )
    failure_pattern = re.compile(
        r'^\[(?P<game>[^\]]+)\]角色(?P<role>.*)\((?P<channel>.*)\)签到失败了！原因[:：](?P<detail>.+)$'
    )
    generic_pattern = re.compile(r'^签到失败，原因[:：](?P<detail>.+)$')

    match = success_pattern.match(log)
    if match:
        data = match.groupdict()
        game = re.sub(r'^[^\w\u4e00-\u9fff]+', '', data['game']).strip() or '未知游戏'
        role = data['role'].strip() or '未知角色'
        channel = data['channel'].strip() or '未知渠道'
        detail = data['detail'].strip() or '无奖励'
        return f'[成功] {game} / {role} / {channel} -> {detail}'

    match = failure_pattern.match(log)
    if match:
        data = match.groupdict()
        game = re.sub(r'^[^\w\u4e00-\u9fff]+', '', data['game']).strip() or '未知游戏'
        role = data['role'].strip() or '未知角色'
        channel = data['channel'].strip() or '未知渠道'
        detail = data['detail'].strip() or '未知原因'
        return f'[失败] {game} / {role} / {channel} -> {detail}'

    match = generic_pattern.match(log)
    if match:
        return f'[异常] {match.group("detail").strip() or log}'

    return f'[异常] {log}'


def generate_signature(path, body_or_query):
    """
    获得签名头
    接口地址+方法为Get请求？用query否则用body+时间戳+ 请求头的四个重要参数（dId，platform，timestamp，vName）.toJSON()
    将此字符串做HMAC加密，算法为SHA-256，密钥token为请求cred接口会返回的一个token值
    再将加密后的字符串做MD5即得到sign
    :param path: 请求路径（不包括网址）
    :param body_or_query: 如果是GET，则是它的query。POST则为它的body
    :return: 计算完毕的sign
    """
    # "don't change the time of device" problem seems fixed
    t = str(int(time.time()))
    token = http_local.token.encode('utf-8')
    header_ca = json.loads(json.dumps(header_for_sign))
    header_ca['timestamp'] = t
    header_ca_str = json.dumps(header_ca, separators=(',', ':'))
    s = path + body_or_query + t + header_ca_str
    hex_s = hmac.new(token, s.encode('utf-8'), hashlib.sha256).hexdigest()
    md5 = hashlib.md5(hex_s.encode('utf-8')).hexdigest().encode('utf-8').decode('utf-8')
    if not getattr(http_local, 'hide_sign_details', False):
        logging.info(f'算出签名: {md5}')
    return md5, header_ca


def get_sign_header(url: str, method, body, h):
    p = parse.urlparse(url)
    if method.lower() == 'get':
        h['sign'], header_ca = generate_signature(p.path, p.query)
    else:
        h['sign'], header_ca = generate_signature(p.path, json.dumps(body) if body is not None else '')
    for i in header_ca:
        h[i] = header_ca[i]
    return h


def get_cred_by_token(token):
    grant_code = get_grant_code(token)
    return get_cred(grant_code)


def get_grant_code(token):
    response = requests.post(grant_code_url, json={
        'appCode': app_code,
        'token': token,
        'type': 0
    }, headers=header_login)
    resp = response.json()
    if response.status_code != 200:
        raise Exception(f'获得认证代码失败：{resp}')
    if resp.get('status') != 0:
        raise Exception(f'获得认证代码失败：{resp["msg"]}')
    return resp['data']['code']


def get_cred(grant):
    resp = requests.post(cred_code_url, json={
        'code': grant,
        'kind': 1
    }, headers=header_login).json()
    if resp['code'] != 0:
        raise Exception(f'获得cred失败：{resp["message"]}')
    return resp['data']


def refresh_token():
    headers = get_sign_header(refresh_token_url, 'get', None, http_local.header)
    resp = requests.get(refresh_token_url, headers=headers).json()
    if resp.get('code') != 0:
        raise Exception(f'刷新token失败:{resp["message"]}')
    http_local.token = resp['data']['token']


def get_binding_list():
    v = []
    resp = requests.get(binding_url, headers=get_sign_header(binding_url, 'get', None, http_local.header)).json()

    if resp['code'] != 0:
        logging.error(f"请求角色列表出现问题：{resp['message']}")
        if resp.get('message') == '用户未登录':
            logging.error(f'用户登录可能失效了，请检查token是否正确！')
            return []
    for i in resp['data']['list']:
        # 也许有些游戏没有签到功能？
        if i.get('appCode') not in ('arknights', 'endfield'):
            continue
        for j in i.get('bindingList'):
            j['appCode'] = i['appCode']
        v.extend(i['bindingList'])
    return v


def sign_for_arknights(data: dict):
    # 返回是否成功，消息
    body = {
        'gameId': data.get('gameId'),
        'uid': data.get('uid')
    }
    url = sign_url_mapping['arknights']
    headers = get_sign_header(url, 'post', body, http_local.header)
    resp = requests.post(url, headers=headers, json=body).json()
    game_name = "♜ 明日方舟"#data.get('gameName')
    channel = data.get("channelName")
    nickname = data.get('nickName') or ''
    if resp.get('code') != 0:
        return [
            f'[{game_name}]角色{nickname}({channel})签到失败了！原因：{resp["message"]}']
    result = ''
    awards = resp['data']['awards']
    for j in awards:
        res = j['resource']
        result += f'{res["name"]}×{j.get("count") or 1}'
    return [f'[{game_name}]角色{nickname}({channel})签到成功，获得了{result}']


def sign_for_endfield(data: dict):
    roles: list[dict] = data.get('roles')
    game_name = "🔩 明日方舟：终末地"#data.get('gameName')
    channel = data.get("channelName")
    result = []
    for i in roles:
        nickname = i.get('nickname') or ''
        resp = do_sign_for_endfield(i)
        j = resp.json()
        if j['code'] != 0:
            result.append(f'[{game_name}]角色{nickname}({channel})签到失败了！原因:{j["message"]}')
        else:
            awards_result = []
            result_data: dict = j['data']
            result_info_map: dict = result_data['resourceInfoMap']
            for a in result_data['awardIds']:
                award_id = a['id']
                awards = result_info_map[award_id]
                award_name = awards['name']
                award_count = awards['count']
                awards_result.append(f'{award_name}×{award_count}')

            result.append(f'[{game_name}]角色{nickname}({channel})签到成功，获得了:{",".join(awards_result)}')
    return result


def do_sign_for_endfield(role: dict):
    url = sign_url_mapping['endfield']
    headers = get_sign_header(url, 'post', None, http_local.header)
    headers.update({
        'Content-Type': 'application/json',
        # FIXME b服不知道是不是这样
        # gameid_roleid_serverid
        'sk-game-role': f'3_{role["roleId"]}_{role["serverId"]}',
        'referer': 'https://game.skland.com/',
        'origin': 'https://game.skland.com/'
    })
    return requests.post(url, headers=headers)


def do_sign(cred_resp, games=None, hide_sign_details=False):
    """
    执行签到
    :param cred_resp: 认证响应，包含token和cred
    :param games: 要签到的游戏列表，默认全部游戏
    :return: (是否成功, 签到日志列表)
    """
    http_local.token = cred_resp['token']
    http_local.header = header.copy()
    http_local.header['cred'] = cred_resp['cred']
    http_local.hide_sign_details = hide_sign_details
    characters = get_binding_list()
    success = True
    logs_out = []  # 新增：用于 Server酱³ 的汇总文本

    # 默认签到所有游戏
    if games is None:
        games = ['arknights', 'endfield']

    logging.info(f'获取到 {len(characters)} 个可签到角色')
    if not characters:
        logging.warning('未获取到可签到角色，本账号将跳过')
        return success, logs_out
    if hide_sign_details:
        logging.info('已启用安全日志模式：隐藏角色名、渠道和奖励等详细签到信息')

    for i in characters:
        app_code = i['appCode']
        # 检查是否需要签到该游戏
        if app_code not in games:
            logging.info(f'跳过游戏：{_display_game_name(app_code)}')
            continue

        msg = None
        if app_code == 'arknights':
            msg = sign_for_arknights(i)
        elif app_code == 'endfield':
            msg = sign_for_endfield(i)
        if not msg:
            continue

        for log_line in msg:
            logs_out.append(log_line)
            if not hide_sign_details:
                logging.info(_format_runtime_log(log_line))

    if hide_sign_details and logs_out:
        for summary_line in _summarize_logs_by_game(logs_out):
            logging.info(f'游戏汇总：{summary_line}')

    success_count, failure_count, error_count = _summarize_logs(logs_out)
    logging.info(
        f'账号签到完成：成功 {success_count}，失败 {failure_count}，异常 {error_count}'
    )

    return success, logs_out





def start(accounts, hide_sign_details=False):
    success = True
    all_logs = []  # 新增：汇总所有账号/角色的输出
    total_accounts = len(accounts)
    logging.info(f'本次共载入 {total_accounts} 个账号')

    for index, account in enumerate(accounts, start=1):
        token = account.get('token')
        games = account.get('games', ['arknights', 'endfield'])
        account_label = f'账号 {index}/{total_accounts} ({_mask_token(token)})'
        try:
            logging.info(f'[{account_label}] 开始签到，游戏：{_display_games(games)}')
            logging.info(f'[{account_label}] 正在获取认证信息')
            cred_resp = get_cred_by_token(token)
            logging.info(f'[{account_label}] 认证成功，开始执行签到')
            sign_success, logs_out = do_sign(
                cred_resp,
                games,
                hide_sign_details=hide_sign_details,
            )
            all_logs.extend(logs_out)
            success_count, failure_count, error_count = _summarize_logs(logs_out)
            logging.info(
                f'[{account_label}] 处理完成，成功 {success_count}，失败 {failure_count}，异常 {error_count}'
            )
            if not sign_success:
                success = False
        except Exception as ex:
            err = f'签到失败，原因：{str(ex)}'
            logging.error(f'[{account_label}] {err}', exc_info=ex)
            all_logs.append(err)
            success = False
    success_count, failure_count, error_count = _summarize_logs(all_logs)
    logging.info(
        f'全部账号签到完成：成功 {success_count}，失败 {failure_count}，异常 {error_count}'
    )

    return success, all_logs
