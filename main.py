"""
Admin panel funksiyalari
Bu faylni main.py bilan bir papkaga qo'ying
"""
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MANDATORY_CHANNEL, ADMIN_IDS, DATA_DIR, USERS_FILE, PRODUCTS_FILE, ORDERS_FILE, STATS_FILE

# States
ADD_PHOTO, ADD_NAME, ADD_PRICE, ADD_DESC, BROADCAST_MESSAGE = 1, 2, 3, 4, 6

# Yangi fayllar
REFERRALS_FILE = f"{DATA_DIR}/referrals.json"
SETTINGS_FILE = f"{DATA_DIR}/settings.json"

def load_json(filename, default=None):
    if default is None:
        default = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_admin_keyboard():
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Mahsulot qo'shish"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("🔢 Hisob-kitob"), KeyboardButton("⭐ Top Referallar")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("💰 Haftalik Hisobot")],
        [KeyboardButton("⚙️ Sozlamalar"), KeyboardButton("🔙 Orqaga")]
    ], resize_keyboard=True)

# MAHSULOT QO'SHISH
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin emas!")
        return ConversationHandler.END
    
    context.user_data.clear()
    await update.message.reply_text("📸 Mahsulot rasmini yuboring:\n\n/cancel - Bekor qilish")
    return ADD_PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, rasm yuboring!\n\n/cancel - Bekor qilish")
        return ADD_PHOTO
    
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ Rasm qabul qilindi!\n\n📝 Mahsulot nomini kiriting:")
    return ADD_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"✅ Nom: <b>{update.message.text}</b>\n\n💰 Narxini kiriting (faqat raqam):", parse_mode='HTML')
    return ADD_PRICE

async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(' ', '').replace(',', ''))
        context.user_data['price'] = price
        await update.message.reply_text(f"✅ Narx: <b>{price:,}</b> so'm\n\n📄 Mahsulot haqida yozing:", parse_mode='HTML')
        return ADD_DESC
    except:
        await update.message.reply_text("❌ Faqat raqam kiriting!\n\n/cancel - Bekor qilish")
        return ADD_PRICE

async def receive_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    
    products = load_json(PRODUCTS_FILE, {})
    product_id = f"G{len(products) + 1}"
    
    product = {
        'id': product_id,
        'name': context.user_data['name'],
        'price': context.user_data['price'],
        'description': description,
        'photo_id': context.user_data['photo'],
        'created_at': datetime.now().isoformat()
    }
    
    products[product_id] = product
    save_json(PRODUCTS_FILE, products)
    
    await update.message.reply_text(
        f"✅ Mahsulot qo'shildi!\n\n"
        f"🆔 ID: <b>{product_id}</b>\n"
        f"🛍 Nom: {context.user_data['name']}\n"
        f"💰 Narx: {context.user_data['price']:,} so'm",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )
    
    # KANALGA YUBORISH
    try:
        settings = load_json(SETTINGS_FILE, {'delivery_available': True, 'admin_username': 'admin'})
        
        delivery_text = ""
        if settings.get('delivery_available', True):
            admin_user = settings.get('admin_username', 'admin')
            delivery_text = f"\n\n🚚 Yetkazib berish: @{admin_user}"
        
        channel_text = (
            f"🆕 <b>Yangi mahsulot!</b>\n\n"
            f"🛍 <b>{product['name']}</b>\n\n"
            f"💰 Narxi: <b>{product['price']:,}</b> so'm\n\n"
            f"📝 Ma'lumot:\n{product['description']}"
            f"{delivery_text}\n\n"
            f"🤖 Buyurtma berish: @{context.bot.username}\n"
            f"🆔 Mahsulot ID: <code>{product_id}</code>"
        )
        
        await context.bot.send_photo(
            chat_id=MANDATORY_CHANNEL,
            photo=product['photo_id'],
            caption=channel_text,
            parse_mode='HTML'
        )
        
        await update.message.reply_text("📢 Mahsulot kanalga ham yuborildi!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Kanalga yuborib bo'lmadi: {str(e)}")
    
    context.user_data.clear()
    return ConversationHandler.END

# STATISTIKA
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0, 'products': {}})
    products = load_json(PRODUCTS_FILE, {})
    
    text = "📊 <b>Statistika</b>\n\n🏆 <b>Top mahsulotlar:</b>\n\n"
    
    sorted_products = sorted(stats.get('products', {}).items(), key=lambda x: x[1], reverse=True)
    
    for i, (pid, count) in enumerate(sorted_products[:5], 1):
        pname = products.get(pid, {}).get('name', 'Noma\'lum')
        text += f"{i}. {pname} - {count} ta\n"
    
    if not sorted_products:
        text += "Hali buyurtmalar yo'q"
    
    await update.message.reply_text(text, parse_mode='HTML')

# HISOB-KITOB
async def show_calculations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0})
    
    text = (
        f"🔢 <b>Hisob-kitob</b>\n\n"
        f"📥 Jami: {stats['total']}\n"
        f"✅ Qabul: {stats['accepted']}\n"
        f"❌ Rad: {stats['rejected']}\n"
        f"⏳ Kutilmoqda: {stats['total'] - stats['accepted'] - stats['rejected']}\n\n"
        f"📊 Foiz: {(stats['accepted'] / stats['total'] * 100 if stats['total'] > 0 else 0):.1f}%"
    )
    await update.message.reply_text(text, parse_mode='HTML')

# TOP REFERALLAR
async def show_top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    referrals = load_json(REFERRALS_FILE, {})
    users = load_json(USERS_FILE, {})
    
    # Sortlash
    sorted_refs = sorted(referrals.items(), key=lambda x: x[1]['count'], reverse=True)
    
    text = "⭐ <b>Top 3 Referal Liderlari</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (user_id, data) in enumerate(sorted_refs[:3], 0):
        user_info = users.get(user_id, {})
        user_name = user_info.get('name', 'Foydalanuvchi')
        count = data['count']
        
        text += f"{medals[i]} <b>{user_name}</b>\n"
        text += f"   ⭐ Yulduzlar: {count}\n"
        text += f"   🆔 ID: {user_id}\n\n"
    
    if not sorted_refs:
        text += "Hali referallar yo'q"
    
    await update.message.reply_text(text, parse_mode='HTML')

# HAFTALIK HISOBOT
async def show_weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_json(STATS_FILE, {'total': 0, 'accepted': 0, 'rejected': 0, 'weekly': []})
    orders = load_json(ORDERS_FILE, {})
    
    # Oxirgi 7 kunlik buyurtmalar
    week_ago = datetime.now() - timedelta(days=7)
    
    weekly_orders = []
    total_price = 0
    
    for order in orders.values():
        try:
            order_date = datetime.fromisoformat(order['created_at'])
            if order_date >= week_ago and order['status'] == 'accepted':
                weekly_orders.append(order)
                total_price += order.get('price', 0)
        except:
            pass
    
    text = (
        f"💰 <b>Haftalik Hisobot</b>\n\n"
        f"📅 Oxirgi 7 kun\n\n"
        f"📦 Buyurtmalar: {len(weekly_orders)} ta\n"
        f"💵 Jami summa: <b>{total_price:,}</b> so'm\n\n"
    )
    
    if len(weekly_orders) > 0:
        avg = total_price / len(weekly_orders)
        text += f"📊 O'rtacha: {avg:,.0f} so'm"
    else:
        text += "Bu haftada sotuvlar bo'lmagan"
    
    await update.message.reply_text(text, parse_mode='HTML')

# SOZLAMALAR
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_json(SETTINGS_FILE, {'delivery_available': True, 'admin_username': 'admin'})
    
    delivery_status = "✅ Yoqilgan" if settings.get('delivery_available', True) else "❌ O'chirilgan"
    admin_user = settings.get('admin_username', 'admin')
    
    text = (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🚚 Yetkazib berish: {delivery_status}\n"
        f"👤 Admin username: @{admin_user}\n\n"
        f"Sozlamalarni o'zgartirish uchun settings.json faylini tahrirlang."
    )
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Yetkazib berishni o'zgartirish", callback_data="toggle_delivery")
    ]])
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

# BROADCAST
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin emas!")
        return ConversationHandler.END
    
    users = load_json(USERS_FILE, {})
    user_count = len(users)
    
    await update.message.reply_text(
        f"📢 <b>Broadcast</b>\n\n"
        f"👥 Jami foydalanuvchilar: {user_count}\n\n"
        f"Xabaringizni yozing:",
        parse_mode='HTML'
    )
    return BROADCAST_MESSAGE

async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    users = load_json(USERS_FILE, {})
    
    await update.message.reply_text("📤 Xabar yuborilmoqda...")
    
    success = 0
    failed = 0
    
    for user_id in users.keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 <b>Xabar:</b>\n\n{message}",
                parse_mode='HTML'
            )
            success += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"✅ Broadcast tugadi!\n\n"
        f"✅ Yuborildi: {success}\n"
        f"❌ Xato: {failed}",
        reply_markup=get_admin_keyboard()
    )
    
    return ConversationHandler.END
