import json
import logging
import os
import time
from datetime import date
import tomllib

import requests

from rich.logging import RichHandler
import rich.traceback

from runtime_config import load_runtime_config


def config_logger(log_level: str, use_proxy: bool):
    current_date = date.today().strftime('%Y-%m-%d')
    if not os.path.exists('logs'):
        os.mkdir('logs')
    logger = logging.getLogger()
    logger.handlers.clear()

    file_handler = logging.FileHandler(f'./logs/{current_date}.log', encoding='utf-8')
    logger.addHandler(file_handler)
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    file_handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # enable nicer tracebacks
    rich.traceback.install()

    def filter_code(text):
        filter_key = ['code', 'cred', 'token']
        try:
            j = json.loads(text)
            if not j.get('data'):
                return text
            data = j['data']
            for i in filter_key:
                if i in data:
                    data[i] = '*****'
            return json.dumps(j, ensure_ascii=False)
        except:
            return text

    _get = requests.get
    _post = requests.post

    def get(*args, **kwargs):
        if use_proxy:
            kwargs.update({
                'proxies': {
                    'https': 'http://localhost:8000',
                },
                'verify': False
            })
        response = _get(*args, **kwargs)
        logger.debug(f'GET {args[0]} - {response.status_code} - {filter_code(response.text)}')
        return response

    def post(*args, **kwargs):
        if use_proxy:
            kwargs.update({
                'proxies': {
                    'https': 'http://localhost:8000',
                },
                'verify': False
            })
        response = _post(*args, **kwargs)
        logger.debug(f'POST {args[0]} - {response.status_code} - {filter_code(response.text)}')
        return response

    # 替换 requests 中的方法
    requests.get = get
    requests.post = post


if __name__ == '__main__':
    runtime_config = load_runtime_config()
    config_logger(runtime_config.log_level, runtime_config.use_proxy)

    import push
    from skyland import start

    for warning in runtime_config.warnings:
        logging.warning(warning)

    with open("pyproject.toml", "rb") as f:
        print(f'skyland-as v{tomllib.load(f)["project"]["version"]}')
    print('Repo link: https://github.com/Rewindex/skyland-as')
    logging.info('=========starting==========')
    start_time = time.time()
    success, all_logs = start(
        runtime_config.accounts,
        hide_sign_details=runtime_config.hide_sign_details,
    )
    if runtime_config.push_enabled:
        push.push(
            all_logs,
            services=runtime_config.push_services,
            sc3_sendkey=runtime_config.sc3_sendkey,
            sc3_uid=runtime_config.sc3_uid,
            tg_bot_token=runtime_config.tg_bot_token,
            tg_chat_id=runtime_config.tg_chat_id,
        )
    else:
        logging.info('已禁用推送，跳过发送结果')
    end_time = time.time()
    logging.info(f'complete with {(end_time - start_time) * 1000} ms')
    logging.info('===========ending============')

    if runtime_config.exit_when_fail and not success:
        exit(1)
