import asyncio
import datetime
import time
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import TimedOut, NetworkError

from config import API_TOKEN, VIP_USERS, WHITELIST_USERS
from database import (
    init_db,
    create_booking,
    remove_booking,
    get_schedule,
    get_booked_places,
    restore_bookings,
    create_temp_booking,
    create_temp_bookings_table,
    get_temp_booked_places,
    delete_booking,
    delete_temp_booking,
    check_is_permtemp_status,
    get_booked_places_for_button,
    get_permanent_booking_for_day,
    get_user_temp_booking_for_day,
    restore_bookings_manually,
    get_temp_booked_info,
    delete_temp_bookings_from_temp_handler,
)
from places import PLACES


def is_authorized(user_id):
    return user_id in VIP_USERS or user_id in WHITELIST_USERS


async def notify_users(context, message):
    all_users = VIP_USERS + WHITELIST_USERS
    for user_id in all_users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = (
        update.message.from_user.id
        if update.message
        else update.callback_query.from_user.id
    )
    username = (
        update.message.from_user.username
        if update.message
        else update.callback_query.from_user.username
    )

    if not username:
        await update.message.reply_text(
            "Пожалуйста, укажите ваше имя пользователя (username), чтобы продолжить использование бота."
        )
        return

    if not is_authorized(user_id):
        (
            await update.message.reply_text(
                "У вас нет доступа для использования этого бота."
            )
            if update.message
            else await update.callback_query.answer(
                "У вас нет доступа для использования этого бота."
            )
        )
        return

    permanent_bookings_count = get_booked_places_for_button(username)

    keyboard = [[InlineKeyboardButton("Расписание", callback_data="schedule")]]

    if permanent_bookings_count < 3:
        keyboard.append(
            [InlineKeyboardButton("Забронировать перманентно", callback_data="book")]
        )

    keyboard.append(
        [InlineKeyboardButton("Забронировать временно", callback_data="temp_book")]
    )
    keyboard.append([InlineKeyboardButton("Удалить бронь", callback_data="remove")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        message = await update.callback_query.message.reply_text(
            "Выберите действие:", reply_markup=reply_markup
        )
    else:
        message = await update.message.reply_text(
            "Выберите действие:", reply_markup=reply_markup
        )

    context.job_queue.run_once(
        delete_message,
        60,
        data={"chat_id": message.chat.id, "message_id": message.message_id},
    )

    if update.message:
        context.job_queue.run_once(
            delete_message,
            5,
            data={
                "chat_id": update.message.chat.id,
                "message_id": update.message.message_id,
            },
        )


async def delete_message(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    message_id = job.data["message_id"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except telegram.error.BadRequest:
        pass


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>Добро пожаловать в бот для бронирования парковочных мест.</b> Ниже представлены основные функции бота и ограничения, которые необходимо учитывать.\n\n"
        "Бот принимает только команду /start из Меню. Доступ выдается по ID администратором бота.\n\n"
        "<b>Перманентное бронирование:</b>\n"
        "Вы можете забронировать место на определенные дни недели. Учтите, что у вас может быть не более трех перманентных броней одновременно и не может быть большой одной перманентной брони на день.\n\n"
        "<b>Временное бронирование:</b>\n"
        "Вы можете временно забронировать свободное место. Временные брони действуют только на одну неделю, после чего место автоматически становится доступным для других пользователей или владение бронью возвращается тому, кто ранее перманентно забронировал место. Не может быть большой одной временной брони на день.\n\n"
        "<b>Удаление брони:</b>\n"
        "Вы можете удалить свои брони (как временные, так и перманентные). Если место было забронировано другим пользователем, вы не сможете его удалить.\n\n"
        "<b>VIP-функции:</b>\n"
        "Если вы являетесь VIP-пользователем, у вас есть возможность забронировать места, которые уже были забронированы другими пользователями. Вы также можете удалять брони других пользователей.\n\n"
        "<b>Необходимость указания username:</b>\n"
        "Для использования бота необходимо указать имя пользователя (username). Бот не будет работать, если ваше имя пользователя не указано.\n"
    )

    user_message_id = update.message.message_id
    user_chat_id = update.message.chat.id

    context.job_queue.run_once(
        delete_message, 5, data={"chat_id": user_chat_id, "message_id": user_message_id}
    )

    await update.message.reply_text(help_text, parse_mode="HTML")


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    schedule = get_schedule()
    today = datetime.date.today()

    russian_days = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]
    monday = today - datetime.timedelta(days=today.weekday())

    response = "Расписание:\n"

    for i in range(7):
        date = monday + datetime.timedelta(days=i)
        day_name = russian_days[i]

        if date < today:
            date += datetime.timedelta(weeks=1)

        underline_length = 30
        response += f"{'-' * underline_length}\n"
        response += f"<i><b>{
            day_name}</b></i> ({date.strftime('%d-%m-%Y')}):\n"

        for place in PLACES:
            user = schedule.get(day_name, {}).get(place, None)
            if len(str(place)) == 2:
                space_padding = "   "
            elif len(str(place)) == 3:
                space_padding = " "
            else:
                space_padding = " "

            if user is None:
                response += f"  Место {place}{space_padding}: ✅ Свободно\n"
            else:
                booking_status = check_is_permtemp_status(place, user, day_name)
                response += f"  Место {place}{
                    space_padding}: ❌ (@{user}, {booking_status})\n"

    await update.callback_query.message.delete()
    await update.callback_query.message.reply_text(response, parse_mode="HTML")


async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())

    russian_days = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    keyboard = [
        [
            InlineKeyboardButton(
                russian_days[i],
                callback_data=f"choose_day_{
                                      russian_days[i]}",
            )
        ]
        for i in range(7)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "Выберите день для бронирования:", reply_markup=reply_markup
    )


async def temp_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())

    russian_days = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    keyboard = [
        [
            InlineKeyboardButton(
                russian_days[i],
                callback_data=f"choose_temp_day_{
                                      russian_days[i]}",
            )
        ]
        for i in range(7)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "Выберите день для временного бронирования:", reply_markup=reply_markup
    )


async def choose_temp_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.callback_query.data.split("_")[3]
    context.user_data["selected_temp_day"] = day
    keyboard = [
        [
            InlineKeyboardButton(
                f"Место {place}",
                callback_data=f"temp_book_{
                                      day}_{place}",
            )
        ]
        for place in PLACES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"Выберите место для временного бронирования на {day}:",
        reply_markup=reply_markup,
    )


async def handle_temp_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data.split("_")
    day = data[2]
    place = data[3]
    user_id = update.callback_query.from_user.id
    username = update.callback_query.from_user.username

    today = datetime.date.today()
    russian_days = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]
    day_index = russian_days.index(day)
    monday = today - datetime.timedelta(days=today.weekday())
    reservation_date = monday + datetime.timedelta(days=day_index)

    if reservation_date < today:
        reservation_date += datetime.timedelta(days=7)

    restore_date = reservation_date

    user_permanent_booking = get_permanent_booking_for_day(username, day)

    if user_permanent_booking:
        permanent_place = user_permanent_booking["place"]
        message = await update.callback_query.message.reply_text(
            f"❌ У вас уже забронировано место {permanent_place} на {day}. "
            f"Удалите эту бронь, чтобы забронировать место {place} на {day}."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={"chat_id": message.chat.id, "message_id": message.message_id},
        )
        return

    user_temp_booking = get_user_temp_booking_for_day(username, day)
    if user_temp_booking:
        temp_place = user_temp_booking["place"]
        message = await update.callback_query.message.reply_text(
            f"❌ У вас уже временно забронировано место {temp_place} на {day}. "
            f"Удалите эту бронь, чтобы забронировать место {place} на {day}."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={"chat_id": message.chat.id, "message_id": message.message_id},
        )
        return

    booked_user, is_temp_booking = get_temp_booked_places(place, day)

    if booked_user is None:
        create_temp_booking(place, username, reservation_date, restore_date, day)
        await notify_users(
            context,
            f"✅ Пользователь @{username} временно забронировал место {place} на {reservation_date}.",
        )
        message = await update.callback_query.message.reply_text(
            f"✅ Успешно временно забронировано: место {place} на {reservation_date}."
        )
    elif user_id in VIP_USERS:
        if is_temp_booking:
            delete_temp_booking(place, booked_user, reservation_date)
            delete_temp_bookings_from_temp_handler(place, booked_user, day)

        create_temp_booking(place, username, reservation_date, restore_date, day)
        await notify_users(
            context,
            f"✅ VIP @{username} временно забронировал место {place} на {reservation_date}, которое было ранее забронировано пользователем @{booked_user}.",
        )
        message = await update.callback_query.message.reply_text(
            f"✅ Успешно временно забронировано: место {place} на {reservation_date} (ранее забронировано пользователем @{booked_user})."
        )
    else:
        if is_temp_booking:
            message = await update.callback_query.message.reply_text(
                f"❌ Место {place} уже временно забронировано пользователем @{booked_user} на {reservation_date}."
            )
        else:
            message = await update.callback_query.message.reply_text(
                f"❌ Место {place} уже забронировано пользователем @{booked_user} на {reservation_date}."
            )

    context.job_queue.run_once(
        delete_message,
        20,
        data={"chat_id": message.chat.id, "message_id": message.message_id},
    )
    await update.callback_query.message.delete()


async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.callback_query.data.split("_")[2]
    context.user_data["selected_day"] = day
    keyboard = [
        [
            InlineKeyboardButton(
                f"Место {place}",
                callback_data=f"book_{
                                      day}_{place}",
            )
        ]
        for place in PLACES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"Выберите место для бронирования на {day}:", reply_markup=reply_markup
    )


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())

    russian_days = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    keyboard = [
        [
            InlineKeyboardButton(
                russian_days[i],
                callback_data=f"choose_remove_day_{
                                      russian_days[i]}",
            )
        ]
        for i in range(7)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "Выберите день для удаления брони:", reply_markup=reply_markup
    )


async def choose_remove_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.callback_query.data.split("_")[3]
    context.user_data["remove_day"] = day
    keyboard = [
        [
            InlineKeyboardButton(
                f"Место {place}",
                callback_data=f"remove_{
                                      day}_{place}",
            )
        ]
        for place in PLACES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"Выберите место для удаления брони на {day}:", reply_markup=reply_markup
    )


async def handle_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data.split("_")
    day = data[1]
    place = data[2]
    user_id = update.callback_query.from_user.id
    username = update.callback_query.from_user.username

    user_permanent_booking = get_permanent_booking_for_day(username, day)

    if user_permanent_booking:
        permanent_place = user_permanent_booking["place"]
        message = await update.callback_query.message.reply_text(
            f"❌ У вас уже забронировано место {permanent_place} на {day}. "
            f"Удалите эту бронь, чтобы забронировать место {place} на {day}."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={"chat_id": message.chat.id, "message_id": message.message_id},
        )
        return

    user_temp_booking = get_user_temp_booking_for_day(username, day)
    if user_temp_booking:
        temp_place = user_temp_booking["place"]
        message = await update.callback_query.message.reply_text(
            f"❌ У вас уже временно забронировано место {temp_place} на {day}. "
            f"Удалите эту бронь, чтобы забронировать место {place} на {day}."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={"chat_id": message.chat.id, "message_id": message.message_id},
        )
        return

    booked_user = get_booked_places(place, day)

    if booked_user and user_id in VIP_USERS:
        delete_booking(place, day)
        create_booking(place, username, day)
        await notify_users(
            context,
            f"✅ VIP @{username} забронировал место {place} на {day}, которое было ранее забронировано пользователем @{booked_user}.",
        )
    elif booked_user is None:
        create_booking(place, username, day)
        await notify_users(
            context, f"✅ Пользователь @{username} забронировал место {place} на {day}."
        )
    else:
        message = await update.callback_query.message.reply_text(
            f"❌ Место {place} уже забронировано пользователем @{booked_user} на {day}."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={"chat_id": message.chat.id, "message_id": message.message_id},
        )
        return

    await update.callback_query.message.delete()
    message_success = await update.callback_query.message.reply_text(
        f"✅ Успешно забронировано: место {place} на {day}."
    )
    context.job_queue.run_once(
        delete_message,
        20,
        data={
            "chat_id": message_success.chat.id,
            "message_id": message_success.message_id,
        },
    )


async def handle_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    username = update.callback_query.from_user.username
    day = context.user_data.get("remove_day")
    place = update.callback_query.data.split("_")[2]

    booked_user = get_booked_places(place, day)
    temp_booked_info = get_temp_booked_info(place, day)

    if user_id in VIP_USERS:
        original_user = temp_booked_info.get("original_user", None)
        temp_user = temp_booked_info.get("user", None)

        if original_user and temp_user == username and original_user != username:
            restore_bookings_manually(place, day)

        remove_booking(place, booked_user, day, manually_deleted=False)
        await notify_users(
            context,
            f"❌ VIP @{username} удалил бронь с места {place}, ранее забронированное пользователем @{booked_user} на {day}.",
        )
        message_success = await update.callback_query.message.reply_text(
            f"✅ Успешно удалено: место {place} на {day}."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={
                "chat_id": message_success.chat.id,
                "message_id": message_success.message_id,
            },
        )

    elif booked_user == username:
        remove_booking(place, booked_user, day, manually_deleted=True)

        if temp_booked_info:
            message_success = await update.callback_query.message.reply_text(
                f"✅ Вы удалили свою бронь на {place} на {day}"
            )
        else:
            message_success = await update.callback_query.message.reply_text(
                f"✅ Успешно удалено: место {place} на {day}."
            )

        context.job_queue.run_once(
            delete_message,
            20,
            data={
                "chat_id": message_success.chat.id,
                "message_id": message_success.message_id,
            },
        )
        await notify_users(
            context,
            f"❌ Пользователь @{username} удалил свою бронь на {place} на {day}.",
        )
    else:
        await update.callback_query.answer(
            f"Вы не можете удалить бронь на место {place} на день {day}, так как оно забронировано другим пользователем."
        )
        message = await update.callback_query.message.reply_text(
            f"❌ Ошибка: место {place} уже забронировано другим пользователем."
        )
        context.job_queue.run_once(
            delete_message,
            20,
            data={"chat_id": message.chat.id, "message_id": message.message_id},
        )

    await update.callback_query.message.delete()


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "schedule":
        await schedule(update, context)
    elif query.data == "book":
        await book(update, context)
    elif query.data.startswith("choose_day_"):
        await choose_day(update, context)
    elif query.data == "remove":
        await remove(update, context)
    elif query.data.startswith("choose_remove_day_"):
        await choose_remove_day(update, context)
    elif query.data.startswith("book_"):
        await handle_booking(update, context)
    elif query.data.startswith("remove_"):
        await handle_removal(update, context)
    elif query.data == "temp_book":
        await temp_book(update, context)
    elif query.data.startswith("choose_temp_day_"):
        await choose_temp_day(update, context)
    elif query.data.startswith("temp_book_"):
        await handle_temp_booking(update, context)
    elif query.data == "back":
        await start(update, context)


async def clear_webhook(application):
    await application.bot.delete_webhook(drop_pending_updates=True)


def main():
    init_db()
    create_temp_bookings_table()
    restore_bookings()

    application = Application.builder().token(API_TOKEN).build()

    application.job_queue.run_once(
        lambda _: asyncio.create_task(clear_webhook(application)), when=0
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & ~filters.Regex("^/start$")
            & ~filters.Regex("^/info$"),
            lambda update, context: update.message.delete(),
        )
    )

    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
