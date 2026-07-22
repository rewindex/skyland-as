import logging
from .serverchan3 import push_serverchan3
from .telegram import push_telegram


def push(
    all_logs: list[str],
    services: list[str],
    sc3_sendkey: str = '',
    sc3_uid: str = '',
    tg_bot_token: str = '',
    tg_chat_id: str = '',
):
    """
    推送签到结果
    :param all_logs: 签到结果日志列表
    """
    logging.info("开始推送结果")

    if not services:
        # 未指定推送服务时，默认全部跳过
        logging.info("未指定推送服务，跳过推送")
        logging.info("推送结束")
        return

    logging.info(f"将使用以下推送服务：{', '.join(services)}")

    for service in services:
        try:
            if service == 'serverchan3':
                push_serverchan3(all_logs, sendkey=sc3_sendkey, uid=sc3_uid)
            elif service == 'telegram':
                push_telegram(all_logs, bot_token=tg_bot_token, chat_id=tg_chat_id)
            else:
                logging.warning(f"未知的推送服务：{service}")
        except Exception as e:
            logging.error(f"[Push] {service}时出现问题", exc_info=e)

    logging.info("推送结束")
