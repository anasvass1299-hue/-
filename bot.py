import asyncio
import logging
import os
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)

# Read sensitive values from environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("BOT_TOKEN environment variable is not set. Exiting.")
    raise SystemExit("BOT_TOKEN environment variable is required")

DEVELOPER_ID = int(os.environ.get("DEVELOPER_ID", "8257098912"))
DB_PATH = os.environ.get("DB_PATH", "bot_database.db")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            first_name TEXT,
                            points INTEGER DEFAULT 0,
                            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS daily_stats (
                            date DATE PRIMARY KEY,
                            messages_count INTEGER DEFAULT 0,
                            sessions_count INTEGER DEFAULT 0,
                            new_users_count INTEGER DEFAULT 0
                        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS orders (
                            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            status TEXT DEFAULT 'completed'
                        )''')
        await db.commit()

async def register_user(user_id, username, first_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not await cursor.fetchone():
            await db.execute("INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)", 
                             (user_id, username, first_name))
            today = datetime.now().date().isoformat()
            await db.execute("INSERT OR IGNORE INTO daily_stats (date) VALUES (?)", (today,))
            await db.execute("UPDATE daily_stats SET new_users_count = new_users_count + 1 WHERE date = ?", (today,))
        await db.commit()

async def update_stats(msg=False, session=False):
    today = datetime.now().date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO daily_stats (date) VALUES (?)", (today,))
        if msg:
            await db.execute("UPDATE daily_stats SET messages_count = messages_count + 1 WHERE date = ?", (today,))
        if session:
            await db.execute("UPDATE daily_stats SET sessions_count = sessions_count + 1 WHERE date = ?", (today,))
        await db.commit()

async def get_stats_data(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        today = datetime.now().date().isoformat()
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT new_users_count, messages_count, sessions_count FROM daily_stats WHERE date = ?", (today,))
        row = await cursor.fetchone()
        new_users = row[0] if row else 0
        messages = row[1] if row else 0
        sessions = row[2] if row else 0
        cursor = await db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        points_row = await cursor.fetchone()
        points = points_row[0] if points_row else 0
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'completed'", (user_id,))
        orders_count = (await cursor.fetchone())[0]
        return total_users, new_users, messages, sessions, points, orders_count

def get_user_kb(points, orders_count):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"💰 رصيدي ({points})", callback_data="u_balance"))
    builder.row(InlineKeyboardButton(text="🚀 تمويل قناتك أو مجموعتك", callback_data="u_promote"))
    builder.row(InlineKeyboardButton(text="🛒 شراء نقاط", callback_data="u_buy"), InlineKeyboardButton(text="🎁 تجميع نقاط", callback_data="u_collect"))
    builder.row(InlineKeyboardButton(text="🏷️ استخدام كود متجر", callback_data="u_code"), InlineKeyboardButton(text="📦 طلباتي", callback_data="u_orders"))
    builder.row(InlineKeyboardButton(text="📞 الدعم الفني", callback_data="u_support"))
    builder.row(
        InlineKeyboardButton(text="🤖 صانع بوتات", callback_data="u_factory"),
        InlineKeyboardButton(text="🛡️ حماية ذكاء", callback_data="u_guard"),
        InlineKeyboardButton(text="🏦 بنك شحن", callback_data="u_bank")
    )
    builder.row(InlineKeyboardButton(text=f"✅ طلبات تم اكتمالها ({orders_count})", callback_data="u_completed"))
    return builder.as_markup()

DEV_MAIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚙️ إعدادات", callback_data="d_settings"), InlineKeyboardButton(text="📄 محتوى", callback_data="d_content")],
    [InlineKeyboardButton(text="👥 المستخدمون", callback_data="d_users"), InlineKeyboardButton(text="💳 الاشتراكات", callback_data="d_subs")],
    [InlineKeyboardButton(text="📢 إذاعات", callback_data="d_broadcast"), InlineKeyboardButton(text="💬 رسائل المستخدمين", callback_data="d_msgs")],
    [InlineKeyboardButton(text="🛒 المتجر الإلكتروني", callback_data="d_store"), InlineKeyboardButton(text="🛠 النظام والدعم", callback_data="d_system")],
    [InlineKeyboardButton(text="🔔 إشعار دخول شخص", callback_data="d_notify_in"), InlineKeyboardButton(text="🚫 إشعار حظر البوت", callback_data="d_notify_ban")],
    [InlineKeyboardButton(text="🎛 لوحة تحكم البوت", callback_data="d_bot_control")]
])

SUB_MENUS = {
    'd_settings': ["إعدادات البوت العامة", "الصلاحيات والإدارة", "إعدادات الرسائل", "الاشتراكات والدفع", "الإشعارات", "النسخ الاحتياطي", "إعادة تشغيل البوت"],
    'd_content': ["رسالة الترحيب", "رسالة الحظر", "رسالة القناة الإجبارية", "رسالة رابط الهدية", "رسالة أكواد المتجر"],
    'd_users': ["إحصائيات المستخدمين", "البحث عن مستخدم", "تصدير البيانات", "المستخدمون المحظورون", "المستخدمون النشطون", "إرسال نقاط للجميع", "إذاعة للمستخدمين"],
    'd_subs': ["الباقات", "إضافة باقة", "المشتركون", "طرق الدفع", "أكواد الخصم", "الإحصائيات"],
    'd_broadcast': ["إذاعة نصية", "صورة", "فيديو", "ملف", "للمشتركين فقط", "سجل الإذاعات"],
    'd_msgs': ["الرد على الرسائل", "إرسال رسالة خاصة", "سجل المحادثات", "الرسائل المبلغ عنها"],
    'd_store': ["المنتجات", "الطلبات", "الأقسام", "طرق الدفع", "أكواد الخصم", "إحصائيات المبيعات"],
    'd_system': ["إعدادات النظام", "الأمان والحماية", "النسخ الاحتياطي", "سجل العمليات", "تذاكر الدعم", "تحديث النظام"],
    'd_notify_in': ["تفعيل/تعطيل"],
    'd_notify_ban': ["تفعيل/تعطيل"],
    'd_bot_control': ["إحصائيات البوت", "سجل العمليات", "ربط القنوات", "تنظيف البيانات", "إعادة تشغيل البوت"]
}

def get_sub_kb(menu_key):
    builder = InlineKeyboardBuilder()
    items = SUB_MENUS.get(menu_key, [])
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(text=items[i], callback_data=f"sub_{items[i]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(text=items[i+1], callback_data=f"sub_{items[i+1]}"))
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="d_main"))
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    await register_user(user.id, user.username, user.first_name)
    await update_stats(session=True)
    total, new, msgs, sessions, points, orders = await get_stats_data(user.id)
    username_display = f"@{user.username}" if user.username else "لا يوجد"
    user_text = (
        f"أهلاً بك {user.first_name}\n"
        f"معرفك: {username_display}\n"
        f"أيديك: {user.id}\n\n"
        f"👥 عدد مستخدمين البوت: {total}"
    )
    user_markup = get_user_kb(points, orders)
    if user.id == DEVELOPER_ID:
        dev_text = (
            "⚙️ لوحة التحكم 🤖\n\n"
            "━━━ إحصائيات اليوم ━━━\n"
            f"👥 الإجمالي: {total}\n"
            f"🆕 مستخدمون جدد: {new}\n"
            f"💬 الرسائل: {msgs}\n"
            f"🔄 الجلسات: {sessions}\n"
            "⚡ الاستجابة: 0ms\n\n"
            f"🕐 آخر نشاط: {datetime.now().strftime('%H:%M:%S')}"
        )
        await message.answer(dev_text, reply_markup=DEV_MAIN_KB)
        await message.answer(user_text, reply_markup=user_markup)
    else:
        await message.answer(user_text, reply_markup=user_markup)

@dp.callback_query(F.data == "d_main")
async def back_to_main(callback: types.CallbackQuery):
    if callback.from_user.id != DEVELOPER_ID: return
    total, new, msgs, sessions, _, _ = await get_stats_data(callback.from_user.id)
    text = (
        "⚙️ لوحة التحكم 🤖\n\n"
        "━━━ إحصائيات اليوم ━━━\n"
        f"👥 الإجمالي: {total}\n"
        f"🆕 مستخدمون جدد: {new}\n"
        f"💬 الرسائل: {msgs}\n"
        f"🔄 الجلسات: {sessions}\n"
        "⚡ الاستجابة: 0ms\n\n"
        f"🕐 آخر نشاط: {datetime.now().strftime('%H:%M:%S')}"
    )
    await callback.message.edit_text(text, reply_markup=DEV_MAIN_KB)

@dp.callback_query(F.data.startswith("d_"))
async def dev_sub_menu(callback: types.CallbackQuery):
    if callback.from_user.id != DEVELOPER_ID: return
    menu_key = callback.data
    await callback.message.edit_text(f"قسم: {menu_key.replace('d_', '')}", reply_markup=get_sub_kb(menu_key))

@dp.callback_query(F.data.startswith("sub_"))
async def sub_item_click(callback: types.CallbackQuery):
    if callback.from_user.id != DEVELOPER_ID: return
    item_name = callback.data.replace("sub_", "")
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="d_main")]])
    await callback.message.edit_text(f"خيار: {item_name}", reply_markup=back_kb)

@dp.callback_query(F.data.startswith("u_"))
async def user_btn_click(callback: types.CallbackQuery):
    await callback.answer(f"تم الضغط على خيار في واجهة المستخدم")

@dp.message()
async def all_msgs(message: types.Message):
    await update_stats(msg=True)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
