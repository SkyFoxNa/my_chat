import sys
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
import asyncio
import requests


class HttpError(Exception):
    pass


async def get_exchange():
    response = await request(f'https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5')
    return response


def get_exchange_data(one_day_ago):
    # URL для запроса курса валют
    url = 'https://api.privatbank.ua/p24api/exchange_rates'
    # Параметры запроса
    params = {
        'json': '',
        'date': one_day_ago
    }
    # Отправка GET-запроса
    response = requests.get(url, params = params)

    # Проверка статуса ответа
    if response.status_code == 200 :
        # Декодируем JSON-ответ
        data = response.json()
        # response = await request(f'https://api.privatbank.ua/p24api/exchange_rates?date={one_day_ago}')
        return data


async def display(exchange):
    res_list = []
    res = [
        {
            f"{el.get('ccy')}": {
                "buy": float(el.get("buy")),
                "sale" : float(el.get("sale")),
            }
        }
        for el in exchange
    ]
    res_list.append(f": Курс валют")
    pattern = r"|{:^10}|{:^10}|{:^10}|"
    res_list.append(pattern.format("currency", "sale", "buy"))
    for el in res :
        currency, *_ = el.keys()
        buy = el.get(currency).get("buy")
        sale = el.get(currency).get("sale")

        res_list.append(pattern.format(currency, sale, buy))

    return res_list


async def display_data( counter, additional_currency) :
    current_date = datetime.now().date()
    res_list = [f"Курс валют"]
    pattern = r"|{:^10}|{:^10}|{:^10}|"
    pattern_data = r"|{:^30}|"
    res_list.append(pattern.format("currency", "sale", "buy"))

    for count in range(int(counter)) :
        one_day_ago = current_date - timedelta(days = count)
        one_day_ago_str = one_day_ago.strftime("%d.%m.%Y")
        # time.sleep(1.5)
        exchange = get_exchange_data(one_day_ago_str)

        res_list.append(pattern_data.format(str(exchange['date'])))

        res = [
            {
                f"{el.get('currency')}" : {
                    "buy" : float(el.get("purchaseRateNB")),
                    "sale" : float(el.get("saleRateNB")),
                }
            }
            for el in exchange["exchangeRate"]
        ]

        for el in res :
            currency, *_ = el.keys()
            if currency in ("EUR", "USD", *additional_currency) :
                currency, *_ = el.keys()
                buy = el.get(currency).get("buy")
                sale = el.get(currency).get("sale")

                res_list.append(pattern.format(currency, sale, buy))

    return res_list


async def request(url: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    raise HttpError(f"Error status: {resp.status} for {url}")
        except (aiohttp.ClientConnectorError, aiohttp.InvalidURL) as err:
            raise HttpError(f'Connection error: {url}', str(err))


async def main(message):
    try:
        message_spit = message.split(" ")
        for item in message_spit[:]:
            if item.strip() == '' or item.strip() == ' ':
                message_spit.remove(item)
        if len(message_spit) == 0:
            print(f"Server: Обробляю повідомлення {message}, зачекайте ...")
            exchange = await get_exchange()
            res_list = await display(exchange)

            for el in res_list:
                print(el)

        elif message_spit[0].isdigit():
            for el in message_spit[1:]:
                if el.isdigit():
                    print(f"Валюта повинна бути символьна")

            print(f"Server: Обробляю повідомлення {message}, зачекайте ...")
            additional_currency = [el for el in message_spit[1:]]
            counter = 10 if int(message_spit[0]) >= 10 else int(message_spit[0])
            exchange = await display_data(counter, additional_currency)
            for el in exchange:
                print(el)

        elif message_spit[0:]:
            for el in message_spit[0:]:
                if el.isdigit():
                    print(f"Валюта повинна бути символьна")

            additional_currency = [el for el in message_spit[0:]]
            print(f"Server: Обробляю повідомлення {message}, зачекайте ...")
            exchange = await display_data(1, additional_currency)
            for el in exchange :
                print(el)
    except HttpError as err:
        print(err)
        return None


if __name__ == '__main__':
    if len(sys.argv) == 1:
        messages = ''
    else:
        arguments = sys.argv[1:]
        messages = ' '.join(arguments)
    try:
        asyncio.run(main(messages))
    except KeyboardInterrupt :
        print("\nShutdown")
