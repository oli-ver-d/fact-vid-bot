import os

from telegram import Update, Bot, ForceReply
from telegram.ext import CommandHandler, Updater, Application, ContextTypes
from dotenv import load_dotenv
from main import generate_video


load_dotenv()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /generate is issued."""
    chat_id = update.effective_message.chat_id
    await context.bot.send_message(chat_id, text=f'Generating', parse_mode="MarkdownV2")
    filename, caption = generate_video()
    await context.bot.send_message(chat_id, text=f'`{caption}`', parse_mode="MarkdownV2")
    await context.bot.send_video(chat_id, open(filename, 'rb'))


def main():
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate_command))
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
