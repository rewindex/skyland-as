import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional


DEFAULT_GAMES = ['arknights', 'endfield']
VALID_GAMES = set(DEFAULT_GAMES)
TRUTHY_VALUES = {'1', 'true', 'on', 'yes'}
VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR'}
DEFAULT_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'skyland-as.json')
)


@dataclass
class RuntimeConfig:
    config_path: str
    accounts: list[dict[str, Any]]
    use_proxy: bool
    exit_when_fail: bool
    hide_sign_details: bool
    log_level: str
    no_push: bool
    push_services: list[str] = field(default_factory=list)
    sc3_sendkey: str = ''
    sc3_uid: str = ''
    tg_bot_token: str = ''
    tg_chat_id: str = ''
    warnings: list[str] = field(default_factory=list)

    @property
    def push_enabled(self) -> bool:
        return not self.no_push


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Skland auto sign-in runner')
    parser.add_argument('--config', default=DEFAULT_CONFIG_PATH, help='Path to the config file')
    parser.add_argument('--token', help='Comma-separated account tokens')
    parser.add_argument('--games', help='Comma-separated game codes, e.g. arknights,endfield')
    parser.add_argument('--push-services', help='Comma-separated push services')
    parser.add_argument('--sc3-sendkey', help='ServerChan3 sendkey')
    parser.add_argument('--sc3-uid', help='ServerChan3 uid')
    parser.add_argument('--tg-bot-token', help='Telegram Bot token')
    parser.add_argument('--tg-chat-id', help='Telegram chat ID')
    parser.add_argument('--use-proxy', action='store_true', default=None, help='Enable local HTTPS proxy')
    parser.add_argument('--exit-when-fail', action='store_true', default=None, help='Exit with code 1 on failure')
    parser.add_argument('--hide-sign-details', action='store_true', default=None, help='Hide per-role sign details in logs')
    parser.add_argument('--log-level', help='Log level: DEBUG, INFO, WARNING, ERROR')
    parser.add_argument('--no-push', action='store_true', default=None, help='Disable push notifications')
    return parser.parse_args(argv)


def _parse_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY_VALUES


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(',')
    return [item.strip() for item in items if str(item).strip()]


def _resolve_value(cli_value: Any, config_value: Any, env_value: Any, default: Any = None) -> Any:
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    if env_value is not None:
        return env_value
    return default


def _parse_user_token(token: str) -> str:
    try:
        return json.loads(token)['data']['content']
    except Exception:
        return token


def _normalize_games(raw_games: Any, warnings: list[str]) -> list[str]:
    if not raw_games:
        return DEFAULT_GAMES.copy()

    games = _split_csv(raw_games)
    valid_games = []
    for game in games:
        if game in VALID_GAMES:
            valid_games.append(game)
        else:
            warnings.append(f'未知的游戏类型: {game}，将被忽略')

    return valid_games or DEFAULT_GAMES.copy()


def _normalize_log_level(raw_level: Any, warnings: list[str]) -> str:
    level = str(raw_level or 'INFO').upper()
    if level not in VALID_LOG_LEVELS:
        warnings.append(f'未知的日志级别: {raw_level}，将使用 INFO')
        return 'INFO'
    return level


def _load_config_data(config_path: str, explicit_config_path: bool) -> dict[str, Any]:
    if not os.path.exists(config_path):
        if explicit_config_path:
            raise FileNotFoundError(f'配置文件不存在: {config_path}')
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f'配置文件 JSON 解析失败: {exc}') from exc
    except OSError as exc:
        raise OSError(f'读取配置文件失败: {exc}') from exc


def _build_accounts(args: argparse.Namespace, config_data: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    if args.token:
        games = _normalize_games(args.games, warnings)
        return [
            {
                'token': _parse_user_token(token),
                'games': games.copy(),
            }
            for token in _split_csv(args.token)
        ]

    config_accounts = config_data.get('accounts')
    if config_accounts:
        accounts = []
        for account in config_accounts:
            token = str(account.get('token', '')).strip()
            if not token:
                continue
            accounts.append({
                'token': _parse_user_token(token),
                'games': _normalize_games(account.get('games'), warnings),
            })
        if accounts:
            return accounts

    env_token = os.environ.get('TOKEN')
    if env_token:
        return [
            {
                'token': _parse_user_token(token),
                'games': DEFAULT_GAMES.copy(),
            }
            for token in _split_csv(env_token)
        ]

    raise ValueError('未找到账号信息，请使用命令行参数、配置文件或环境变量提供 TOKEN')


def load_runtime_config(argv: Optional[list[str]] = None) -> RuntimeConfig:
    argv = argv if argv is not None else sys.argv[1:]
    args = _parse_args(argv)
    warnings: list[str] = []
    explicit_config_path = any(arg == '--config' or arg.startswith('--config=') for arg in argv)
    config_path = os.path.abspath(args.config)
    config_data = _load_config_data(config_path, explicit_config_path)
    runtime_config = config_data.get('runtime', {})
    push_config = config_data.get('push', {})
    serverchan3_config = push_config.get('serverchan3', {})
    telegram_config = push_config.get('telegram', {})

    accounts = _build_accounts(args, config_data, warnings)
    use_proxy = _parse_bool(_resolve_value(args.use_proxy, runtime_config.get('use_proxy'), os.environ.get('USE_PROXY'), False))
    exit_when_fail = _parse_bool(
        _resolve_value(args.exit_when_fail, runtime_config.get('exit_when_fail'), os.environ.get('EXIT_WHEN_FAIL'), False)
    )
    hide_sign_details = _parse_bool(
        _resolve_value(args.hide_sign_details, runtime_config.get('hide_sign_details'), os.environ.get('HIDE_SIGN_DETAILS'), False)
    )
    no_push = _parse_bool(_resolve_value(args.no_push, runtime_config.get('no_push'), os.environ.get('NO_PUSH'), False))
    log_level = _normalize_log_level(
        _resolve_value(args.log_level, runtime_config.get('log_level'), os.environ.get('LOG_LEVEL'), 'INFO'),
        warnings,
    )
    push_services = _split_csv(
        _resolve_value(args.push_services, push_config.get('services'), os.environ.get('PUSH_SERVICES'), '')
    )
    sc3_sendkey = str(
        _resolve_value(args.sc3_sendkey, serverchan3_config.get('sendkey'), os.environ.get('SC3_SENDKEY'), '')
    ).strip()
    sc3_uid = str(_resolve_value(args.sc3_uid, serverchan3_config.get('uid'), os.environ.get('SC3_UID'), '')).strip()
    tg_bot_token = str(
        _resolve_value(args.tg_bot_token, telegram_config.get('bot_token'), os.environ.get('TG_BOT_TOKEN'), '')
    ).strip()
    tg_chat_id = str(
        _resolve_value(args.tg_chat_id, telegram_config.get('chat_id'), os.environ.get('TG_CHAT_ID'), '')
    ).strip()

    return RuntimeConfig(
        config_path=config_path,
        accounts=accounts,
        use_proxy=bool(use_proxy),
        exit_when_fail=bool(exit_when_fail),
        hide_sign_details=bool(hide_sign_details),
        log_level=log_level,
        no_push=bool(no_push),
        push_services=push_services,
        sc3_sendkey=sc3_sendkey,
        sc3_uid=sc3_uid,
        tg_bot_token=tg_bot_token,
        tg_chat_id=tg_chat_id,
        warnings=warnings,
    )
