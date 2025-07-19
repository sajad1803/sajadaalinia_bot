
import json
import asyncio
import logging
import websockets
from aiohttp import ClientSession
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_traders():
    try:
        with open("traders.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_traders(traders):
    with open("traders.json", "w") as f:
        json.dump(traders, f)

tracked_traders = load_traders()

async def send_telegram_message(app, chat_id, text):
    try:
        await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def ws_listener(app):
    url = "wss://api.hyperliquid.xyz/ws"

    async with ClientSession() as session:
        async with websockets.connect(url) as ws:
            logger.info("Connected to Hyperliquid WebSocket")

            for trader in tracked_traders:
                subscribe_msg = {
                    "method": "subscribe",
                    "params": {
                        "address": trader.lower()
                    },
                    "id": 1
                }
                await ws.send(json.dumps(subscribe_msg))

            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("method") == "update" and data.get("params"):
                        params = data["params"]
                        if params.get("type") == "order_created":
                            order = params.get("order")
                            trader_address = order.get("trader").lower()
                            if trader_address in [t.lower() for t in tracked_traders]:
                                if order.get("trader_role") != "user":
                                    continue
                                entry = order.get("price")
                                sl = order.get("stop_loss")
                                tp = order.get("take_profit")
                                symbol = order.get("symbol")
                                url_profile = f"https://app.hyperliquid.xyz/trader/{trader_address}"
                                text = (
                                    f"*New Trade Opened*
"
                                    f"👤 Trader: [{trader_address}]({url_profile})
"
                                    f"📊 Symbol: {symbol}
"
                                    f"🎯 Entry Price: {entry}
"
                                    f"⛔ Stop Loss: {sl}
"
                                    f"✅ Take Profit: {tp}
"
                                )
                                await send_telegram_message(app, ADMIN_CHAT_ID, text)
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    await asyncio.sleep(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Use /add <address> to track a trader.")

async def add_trader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /add <trader_address>")
        return
    trader = context.args[0].lower()
    if trader in tracked_traders:
        await update.message.reply_text("Trader already tracked.")
        return
    tracked_traders.append(trader)
    save_traders(tracked_traders)
    await update.message.reply_text(f"Added trader: {trader}")

async def remove_trader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /remove <trader_address>")
        return
    trader = context.args[0].lower()
    if trader not in tracked_traders:
        await update.message.reply_text("Trader not found.")
        return
    tracked_traders.remove(trader)
    save_traders(tracked_traders)
    await update.message.reply_text(f"Removed trader: {trader}")

async def list_traders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tracked_traders:
        await update.message.reply_text("No traders tracked.")
        return
    msg = "Tracked Traders:\n" + "\n".join(tracked_traders)
    await update.message.reply_text(msg)

async def main():
    global ADMIN_CHAT_ID
    import os
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_trader))
    app.add_handler(CommandHandler("remove", remove_trader))
    app.add_handler(CommandHandler("list", list_traders))

    loop = asyncio.get_event_loop()
    loop.create_task(ws_listener(app))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
