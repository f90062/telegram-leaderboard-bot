import logging, json, os, random
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import pytz

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN        = os.getenv('TELEGRAM_TOKEN', 'YOUR_TOKEN')
ADMIN_ID     = int(os.getenv('ADMIN_ID', '0'))
GROUP_ID     = int(os.getenv('GROUP_ID', '0'))
TZ           = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Taipei'))
RESET_HOUR   = int(os.getenv('RESET_HOUR', '8'))
RESET_MINUTE = int(os.getenv('RESET_MINUTE', '0'))
DATA_FILE    = 'game_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'scores': {}, 'active_games': {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def rank_icon(r):
    return '🥇' if r==1 else '🥈' if r==2 else '🥉' if r==3 else f'{r}st'

def leaderboard_text(scores):
    if not scores:
        return '📊 本週排行榜\n\n還沒有人玩，快來試試！'
    s = sorted(scores.items(), key=lambda x: (-x[1]['score'], x[1]['attempts']))
    lines = ['📊 本週排行榜\n']
    for i, (uid, info) in enumerate(s[:10], 1):
        lines.append(f"{rank_icon(i)} {info.get('name','?')} — {info['score']} 分")
    return '\n'.join(lines)

def make_kb(uid):
    btns = [InlineKeyboardButton(f'📦{i+1}', callback_data=f'g_{uid}_{i}') for i in range(6)]
    return InlineKeyboardMarkup([btns[:3], btns[3:]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '🎮 *猜貓遊戲* 😸\n\n'
        '規則：\n'
        '• 6個紙箱中藏一隻貓\n'
        '• 猜中 *+1分*，繼續猜\n'
        '• 猜錯，遊戲結束\n'
        '• 每週一早上8點自動清零\n\n'
        '/play 開始 | /rank 排行榜 | /myscore 我的分數',
        parse_mode='Markdown')

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    data['active_games'][uid] = {'cat_pos': random.randint(0,5), 'round': 1}
    save_data(data)
    score = data['scores'].get(uid, {}).get('score', 0)
    await update.message.reply_text(
        f'🎮 第1輪開始！目前分數：{score}分\n\n選一個紙箱：',
        reply_markup=make_kb(uid))

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, tuid, chosen = q.data.split('_')
    uid = str(q.from_user.id)
    if uid != tuid:
        await q.answer('這不是你的遊戲！', show_alert=True)
        return
    data = load_data()
    if uid not in data['active_games']:
        await q.edit_message_text('遊戲已結束，/play 重新開始')
        return
    game = data['active_games'][uid]
    cat, rnd, chosen = game['cat_pos'], game['round'], int(chosen)
    rev = ['😸' if i==cat else '❌' if i==chosen else '📦' for i in range(6)]
    if chosen == cat:
        if uid not in data['scores']:
            data['scores'][uid] = {'score':0,'attempts':0,'name':q.from_user.full_name}
        data['scores'][uid]['score'] += 1
        data['scores'][uid]['attempts'] += rnd
        data['scores'][uid]['name'] = q.from_user.full_name
        ns = data['scores'][uid]['score']
        data['active_games'][uid] = {'cat_pos': random.randint(0,5), 'round': rnd+1}
        save_data(data)
        await q.edit_message_text(
            f'✅ 猜中！{"  ".join(rev)}\n+1分！總分：*{ns}分*\n\n繼續第{rnd+1}輪 或 /stop 停止',
            reply_markup=make_kb(uid), parse_mode='Markdown')
    else:
        del data['active_games'][uid]
        save_data(data)
        score = data['scores'].get(uid,{}).get('score',0)
        await q.edit_message_text(
            f'❌ 猜錯！{"  ".join(rev)}\n貓在{cat+1}號箱！\n本週總分：*{score}分*\n\n/play 再挑戰',
            parse_mode='Markdown')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    data['active_games'].pop(uid, None)
    save_data(data)
    score = data['scores'].get(uid,{}).get('score',0)
    await update.message.reply_text(f'遊戲停止，本週分數：{score}分')

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(leaderboard_text(load_data()['scores']))

async def myscore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    info = data['scores'].get(uid)
    if info:
        s = sorted(data['scores'].items(), key=lambda x: (-x[1]['score'], x[1]['attempts']))
        rn = next((i+1 for i,(k,_) in enumerate(s) if k==uid), None)
        await update.message.reply_text(f'📊 本週成績\n名次：{rank_icon(rn)}\n分數：{info["score"]}分')
    else:
        await update.message.reply_text('還沒有分數，/play 開始吧！')

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text('❌ 沒有權限')
        return
    data = {'scores':{}, 'active_games':{}}
    save_data(data)
    await update.message.reply_text('✅ 排行榜已清零')

async def weekly_reset(context: ContextTypes.DEFAULT_TYPE):
    save_data({'scores':{}, 'active_games':{}})
    if GROUP_ID:
        try:
            await context.bot.send_message(GROUP_ID, '🔄 新的一週！排行榜清零，快來 /play 🎮')
        except Exception as e:
            logger.error(e)

def main():
    app = Application.builder().token(TOKEN).build()
    for cmd, fn in [('start',start),('play',play),('rank',rank),('myscore',myscore),('stop',stop),('reset',reset_cmd)]:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(CallbackQueryHandler(btn, pattern=r'^g_'))
    app.job_queue.run_weekly(
        weekly_reset,
        time(RESET_HOUR, RESET_MINUTE, tzinfo=TZ),
        days=(0,)
    )
    app.run_polling()

if __name__ == '__main__':
    main()
