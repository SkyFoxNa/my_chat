import asyncio
import logging
import os

import aiofiles
import httpx
import requests
import websockets
import names
from datetime import datetime, timedelta
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK

logging.basicConfig(level=logging.INFO)

LOG_PATH = 'log/log.txt'
LOD_DIRECTORY = 'log'


async def log_command(command_log):
    if not os.path.exists(LOD_DIRECTORY):
        os.makedirs(LOD_DIRECTORY)

    async with aiofiles.open(LOG_PATH, 'a') as f:
        await f.write(f"{command_log}\n")


async def request(url: str) -> dict | str:
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        if r.status_code == 200:
            result = r.json()
            return result
        else:
            return "Не вийшло в мене взнати курс. Приват не відповідає :)"


async def get_exchange():
    response = await request(f'https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5')
    return response


# async def get_exchange_data(one_day_ago):
#     response = await request(f'https://api.privatbank.ua/p24api/exchange_rates?date={one_day_ago}')
#     return response

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


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def display(self, exchange, ws: WebSocketServerProtocol):
        res_list = []
        res = [
            {
                f"{el.get('ccy')}" : {
                    "buy" : float(el.get("buy")),
                    "sale" : float(el.get("sale")),
                }
            }
            for el in exchange
        ]
        res_list.append(f"{ws.name}: Курс валют")
        pattern = r"|{:^10}|{:^10}|{:^10}|"
        res_list.append(pattern.format("currency", "sale", "buy"))
        for el in res :
            currency, *_ = el.keys()
            buy = el.get(currency).get("buy")
            sale = el.get(currency).get("sale")

            res_list.append(pattern.format(currency, sale, buy))

        return res_list

    async def display_data(self, ws: WebSocketServerProtocol, counter, additional_currency):
        current_date = datetime.now().date()
        res_list = [f"{ws.name}: Курс валют"]
        pattern = r"|{:^10}|{:^10}|{:^10}|"
        pattern_data = r"|{:^30}|"
        res_list.append(pattern.format("currency", "sale", "buy"))

        for count in range(int(counter)):
            one_day_ago = current_date - timedelta(days = count)
            one_day_ago_str = one_day_ago.strftime("%d.%m.%Y")
            # time.sleep(1.5)
            exchange = get_exchange_data(one_day_ago_str)

            res_list.append(pattern_data.format(str(exchange['date'])))

            res = [
                {
                    f"{el.get('currency')}": {
                        "buy" : float(el.get("purchaseRateNB")),
                        "sale" : float(el.get("saleRateNB")),
                    }
                }
                for el in exchange["exchangeRate"]
            ]

            for el in res:
                currency, *_ = el.keys()
                if currency in ("EUR", "USD", *additional_currency):

                    currency, *_ = el.keys()
                    buy = el.get(currency).get("buy")
                    sale = el.get(currency).get("sale")

                    res_list.append(pattern.format(currency, sale, buy))

        return res_list

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            message_spit = message.split(" ")
            for item in message_spit[:]:
                if item.strip() == '' or item.strip() == ' ':
                    message_spit.remove(item)

            if message_spit[0] == "exchange":
                if message_spit[0] == "exchange" and len(message_spit) == 1:
                    await self.send_to_clients(f"Server: Обробляю повідомлення {message} {ws.name}, зачекайте ...")
                    exchange = await get_exchange()
                    res_list = await self.display(exchange, ws)

                    for el in res_list:
                        await self.send_to_clients(el)
                    await log_command(f'{datetime.now().strftime("%d-%m-%Y %H:%M:%S")} Username: {ws.name} Message: {message}')

                    # await self.send_to_clients(exchange)
                elif message_spit[1].isdigit():
                    for el in message_spit[2:]:
                        if el.isdigit():
                            await self.send_to_clients(f"Валюта повинна бути символьна")

                    await self.send_to_clients(f"Server: Обробляю повідомлення {message} {ws.name}, зачекайте ...")
                    additional_currency = [el for el in message_spit[2:]]
                    counter = 10 if int(message_spit[1]) >= 10 else int(message_spit[1])
                    exchange = await self.display_data(ws, counter, additional_currency)
                    for el in exchange:
                        await self.send_to_clients(el)
                    # await self.send_to_clients(str(exchange))
                    await log_command(f'{datetime.now().strftime("%d-%m-%Y %H:%M:%S")} Username: {ws.name} Message: {message}')

                elif message_spit[1:]:
                    for el in message_spit[1:]:
                        if el.isdigit():
                            await self.send_to_clients(f"Валюта повинна бути символьна")

                    additional_currency = [el for el in message_spit[1:]]
                    await self.send_to_clients(f"Server: Обробляю повідомлення {message} {ws.name}, зачекайте ...")
                    exchange = await self.display_data(ws, 1, additional_currency)
                    for el in exchange :
                        await self.send_to_clients(el)
                    await log_command(f'{datetime.now().strftime("%d-%m-%Y %H:%M:%S")} Username: {ws.name} Message: {message}')

            elif message in ['Hello server', 'Hi server', 'server']:
                await ws.send(f"Server: Моє вітання {ws.name}!!!")
                await log_command(f'{datetime.now().strftime("%d-%m-%Y %H:%M:%S")} Username: {ws.name} Message: {message}')
            else:
                await self.send_to_clients(f"{ws.name}: {message}")
                await log_command(f'{datetime.now().strftime("%d-%m-%Y %H:%M:%S")} Username: {ws.name} Message: {message}')


async def main():
    await log_command(f'{datetime.now().strftime("%d-%m-%Y %H:%M:%S")} Server start')
    server = Server()
    async with websockets.serve(server.ws_handler, '0.0.0.0', 8080):
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    # asyncio.run(main())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown")
