import discord
from discord import app_commands
import database
import random
import asyncio
import aiosqlite
from datetime import datetime, timezone, timedelta

# Timezone Italia (UTC+1 inverno, UTC+2 estate — gestione automatica)
try:
    from zoneinfo import ZoneInfo
    TZ_ITALIA = ZoneInfo("Europe/Rome")
except ImportError:
    TZ_ITALIA = None

def _ora_italia(dt: datetime) -> str:
    """Converte un datetime UTC in orario italiano formattato."""
    if TZ_ITALIA:
        return dt.astimezone(TZ_ITALIA).strftime("%H:%M")
    month = dt.month
    if 4 <= month <= 9:
        offset = 2
    elif month == 3:
        last_sun = max(d for d in range(25, 32) if datetime(dt.year, 3, d).weekday() == 6)
        offset = 2 if dt.day >= last_sun else 1
    elif month == 10:
        last_sun = max(d for d in range(25, 32) if datetime(dt.year, 10, d).weekday() == 6)
        offset = 1 if dt.day >= last_sun else 2
    else:
        offset = 1
    return (dt + timedelta(hours=offset)).strftime("%H:%M")
import math
from constants import (
    LOG_CHANNEL_ID, DATABASE_NAME, STAFF_ROLES, STAFF_ROLE_ID,
    FORZEDELLORDINE_ROLE_ID, DOTTORE_ROLE_ID, ARMERIA_ROLE_ID,
    BAR_ROLE_ID, MARKET_ROLE_ID, CONTRABBANDO_DOC_ROLE_ID, STATO_ROLE_ID
)

# Canale dove va la notifica stipendio per lo staff
STIPENDIO_CHANNEL_ID = 1422986030650228766

# ── Zaino: va acquistato con /compra-zaino prima di poter essere usato ────────
ZAINO_ITEM_NAME = "🎒 | Zaino"

async def _has_zaino(uid: str) -> bool:
    return await database.get_item_quantity(uid, ZAINO_ITEM_NAME) >= 1

async def _blocca_senza_zaino(interaction: discord.Interaction) -> bool:
    """Ritorna True (e risponde con errore) se l'utente non ha lo zaino."""
    if not await _has_zaino(str(interaction.user.id)):
        await interaction.response.send_message(
            "❌ Non hai uno **zaino**! Comprane uno con `/compra-zaino` prima di usare questo comando.",
            ephemeral=True
        )
        return True
    return False

# Turni attivi: ora persistenti nel DB (tabella turni_attivi)
_turni_cache: dict = {}  # user_id → discord.Role object (non serializzabile)

# ── Cibi (Listino stile anni '90 — Los Santos) ─────────────────────────────────
FOOD_ITEMS = {
    "🍔 • Burger doppio":                18,
    "🌭 • Hot dog di strada":            12,
    "🌮 • Taco messicano":               11,
    "🍕 • Trancio di pizza":             14,
    "🥪 • Panino al pastrami":           15,
    "🥯 • Bagel con salmone":            17,
    "🌯 • Burrito":                      20,
    "🍗 • Ali di pollo fritte":          22,
    "🍟 • Patatine fritte":               9,
    "🧀 • Nachos con formaggio":         13,
    "🍩 • Ciambella glassata":            8,
    "🍪 • Biscotti":                     10,
    "🍫 • Barretta di cioccolato":        6,
    "🍿 • Popcorn":                       7,
    "🍎 • Frutta fresca":                 8,
    "🥫 • Cibo in scatola":               9,
}

DRINK_ITEMS = {
    "🥤 • Cola ghiacciata":       12,
    "☕ • Caffè americano":        6,
    "🧃 • Succo d'arancia":       10,
    "🥛 • Frappè":                14,
    "💧 • Acqua minerale":        32,
    "🍺 • Birra":                  4,
    "🥃 • Whisky":                 8,
    "🍹 • Rum":                   10,
    "🍸 • Vodka":                  9,
}

ALCOHOLIC = {
    "🍺 • Birra",
    "🥃 • Whisky",
    "🍹 • Rum",
    "🍸 • Vodka",
}

# ── Helper ────────────────────────────────────────────────────────────────────
def _bar(v: int) -> str:
    f = round(v / 10)
    return "█" * f + "░" * (10 - f) + f"  **{v}%**"

def _color(h: int, t: int) -> discord.Color:
    if h < 20 or t < 20: return discord.Color.red()
    if h < 50 or t < 50: return discord.Color.orange()
    return discord.Color(0x1E90FF)


def _fuzzy(query: str, candidates: list) -> list:
    q = query.lower().strip()
    if not q: return candidates
    words = q.split()
    r = [c for c in candidates if all(w in c.lower() for w in words)]
    return r or [c for c in candidates if any(w in c.lower() for w in words)]


def setup_rp_commands(bot):

    # ── /me ──────────────────────────────────────────────────────────────────
    @bot.tree.command(name="me", description="Esegui un'azione roleplay a Los Santos")
    @app_commands.describe(azione="Descrivi cosa fa il tuo personaggio")
    async def me(interaction: discord.Interaction, azione: str):
        uid  = str(interaction.user.id)
        user = await database.get_user(uid)

        if user["hunger"] <= 0 and user["thirst"] <= 0:
            await interaction.response.send_message(
                "❌ Non puoi eseguire alcuna azione in quanto sei troppo disidratato e affamato.",
                ephemeral=True
            )
            return

        h_drop = random.randint(1, 3)
        t_drop = random.randint(1, 5)
        new_h  = max(0, user["hunger"] - h_drop)
        new_t  = max(0, user["thirst"] - t_drop)
        await database.update_hunger_thirst(uid, hunger=new_h, thirst=new_t)
        embed = discord.Embed(
            description=f"*{interaction.user.mention} : {azione}*",
            color=_color(new_h, new_t),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🍔 Fame", value=_bar(new_h), inline=True)
        embed.add_field(name="💦 Sete", value=_bar(new_t), inline=True)
        warns = []
        if new_h < 20: warns.append("⚠️ **Sei affamato!** Mangia qualcosa.")
        if new_t < 20: warns.append("⚠️ **Sei assetato!** Bevi qualcosa.")
        if warns:
            embed.add_field(name="​", value="​", inline=False)
            embed.add_field(name="⚡ Avviso", value="\n".join(warns), inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Azione RP")
        await interaction.response.send_message(embed=embed)

    # ── /mangia ──────────────────────────────────────────────────────────────
    async def _food_ac(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, list(FOOD_ITEMS.keys()))[:25]]

    @bot.tree.command(name="mangia", description="Mangia un cibo dallo zaino per ripristinare la fame")
    @app_commands.describe(cibo="Il cibo da mangiare")
    @app_commands.autocomplete(cibo=_food_ac)
    async def mangia(interaction: discord.Interaction, cibo: str):
        if await _blocca_senza_zaino(interaction):
            return
        if cibo not in FOOD_ITEMS:
            m = _fuzzy(cibo, list(FOOD_ITEMS.keys()))
            cibo = m[0] if m else cibo
        if cibo not in FOOD_ITEMS:
            await interaction.response.send_message("❌ Cibo non riconosciuto.", ephemeral=True); return
        uid = str(interaction.user.id)
        if await database.get_item_quantity(uid, cibo) < 1:
            await interaction.response.send_message(f"❌ Non hai **{cibo}** nello zaino!", ephemeral=True); return
        user  = await database.get_user(uid)
        rip   = FOOD_ITEMS[cibo]
        old_h = user["hunger"]
        new_h = min(100, old_h + rip)
        await database.update_hunger_thirst(uid, hunger=new_h)
        await database.remove_item(uid, cibo, 1)

        # ── Animazione progressiva con più embed ─────────────────────────────
        FRASI_MANGIA = [
            (0.10, "🍴 **{u}** dà il primo morso...",                  discord.Color(0x1E90FF)),
            (0.25, "😋 **{u}** mastica con soddisfazione.",            discord.Color(0x4682B4)),
            (0.45, "🤤 **{u}** sente già le forze tornare...",         discord.Color(0x5F9EA0)),
            (0.65, "💪 **{u}** si sente decisamente meglio!",          discord.Color(0x00BFFF)),
            (0.85, "✨ **{u}** ha quasi finito il pasto.",             discord.Color(0x87CEFA)),
            (1.00, "✅ **{u}** ha terminato il pasto con gusto!",     discord.Color(0x228B22)),
        ]

        passi = max(2, min(6, rip // 5 + 1))
        step  = rip / passi
        u     = interaction.user.display_name

        await interaction.response.defer()

        msg = None
        for idx in range(passi):
            progresso   = (idx + 1) / passi
            fame_attuale = min(100, old_h + round(step * (idx + 1)))

            frase_txt, colore = FRASI_MANGIA[0][1], FRASI_MANGIA[0][2]
            for soglia, testo, col in FRASI_MANGIA:
                if progresso <= soglia:
                    frase_txt, colore = testo, col
                    break

            embed = discord.Embed(
                description=frase_txt.format(u=u),
                color=colore,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=u, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="🥘 Cibo",     value=cibo,                                        inline=True)
            embed.add_field(name="🍔 Fame",     value=f"{_bar(old_h)}  →  {_bar(fame_attuale)}",  inline=False)
            embed.add_field(name="➕ Recupero", value=f"+{round(step*(idx+1))}%",                  inline=True)
            embed.set_footer(text=f"🏙️ West Coast RP '93 — Pasto in corso... ({idx+1}/{passi})")

            if msg is None:
                msg = await interaction.followup.send(embed=embed)
            else:
                await msg.edit(embed=embed)

            if idx < passi - 1:
                await asyncio.sleep(1.2)

        embed_finale = discord.Embed(
            title="🍖 𝐏𝐚𝐬𝐭𝐨 𝐜𝐨𝐧𝐬𝐮𝐦𝐚𝐭𝐨",
            color=discord.Color(0x228B22),
            timestamp=discord.utils.utcnow()
        )
        embed_finale.set_author(name=u, icon_url=interaction.user.display_avatar.url)
        embed_finale.add_field(name="🥘 Cibo",     value=cibo,                               inline=False)
        embed_finale.add_field(name="🍔 Fame",     value=f"{_bar(old_h)}  →  {_bar(new_h)}", inline=False)
        embed_finale.add_field(name="➕ Recupero", value=f"+{rip}%",                          inline=False)
        embed_finale.set_footer(text="🏙️ West Coast RP '93 — Zaino")
        await msg.edit(embed=embed_finale)

    # ── /bevi ────────────────────────────────────────────────────────────────
    async def _drink_ac(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, list(DRINK_ITEMS.keys()))[:25]]

    @bot.tree.command(name="bevi", description="Bevi qualcosa dallo zaino per ripristinare la sete")
    @app_commands.describe(bevanda="La bevanda da bere")
    @app_commands.autocomplete(bevanda=_drink_ac)
    async def bevi(interaction: discord.Interaction, bevanda: str):
        if await _blocca_senza_zaino(interaction):
            return
        if bevanda not in DRINK_ITEMS:
            m = _fuzzy(bevanda, list(DRINK_ITEMS.keys()))
            bevanda = m[0] if m else bevanda
        if bevanda not in DRINK_ITEMS:
            await interaction.response.send_message("❌ Bevanda non riconosciuta.", ephemeral=True); return
        uid = str(interaction.user.id)
        if await database.get_item_quantity(uid, bevanda) < 1:
            await interaction.response.send_message(f"❌ Non hai **{bevanda}** nello zaino!", ephemeral=True); return
        user  = await database.get_user(uid)
        rip   = DRINK_ITEMS[bevanda]
        old_t = user["thirst"]
        new_t = min(100, old_t + rip)
        is_alc = bevanda in ALCOHOLIC
        await database.update_hunger_thirst(uid, thirst=new_t)
        await database.remove_item(uid, bevanda, 1)
        if is_alc:
            new_h = max(0, user["hunger"] - 5)
            await database.update_hunger_thirst(uid, hunger=new_h)

        # ── Animazione progressiva con più embed ─────────────────────────────
        FRASI_BEVI = [
            (0.10, "💧 **{u}** assaggia il primo sorso...",            discord.Color(0x4169E1)),
            (0.25, "😌 **{u}** sente la gola inumidirsi.",            discord.Color(0x1E90FF)),
            (0.45, "💦 **{u}** beve a sorsate regolari.",             discord.Color(0x00BFFF)),
            (0.65, "😤 **{u}** quasi a metà bicchiere...",            discord.Color(0x87CEEB)),
            (0.85, "🥤 **{u}** sta finendo la bevanda.",              discord.Color(0xADD8E6)),
            (1.00, "✅ **{u}** ha svuotato il bicchiere!",            discord.Color(0x228B22)),
        ]
        FRASI_ALC = [
            (0.10, "🍺 **{u}** assaggia il primo sorso...",           discord.Color(0xDAA520)),
            (0.25, "😏 **{u}** sente il bruciore scendere.",         discord.Color(0xB8860B)),
            (0.45, "🥴 **{u}** comincia a sentirsi allegro...",      discord.Color(0xCD853F)),
            (0.65, "😵 **{u}** quasi a metà bicchiere...",           discord.Color(0xA0522D)),
            (0.85, "🍻 **{u}** sta finendo il bicchiere.",           discord.Color(0x8B4513)),
            (1.00, "✅ **{u}** ha vuotato il bicchiere d'un fiato!", discord.Color(0x228B22)),
        ]

        frasi = FRASI_ALC if is_alc else FRASI_BEVI
        passi = max(2, min(6, rip // 5 + 1))
        step  = rip / passi
        u     = interaction.user.display_name

        await interaction.response.defer()

        msg = None
        for idx in range(passi):
            progresso    = (idx + 1) / passi
            sete_attuale = min(100, old_t + round(step * (idx + 1)))

            frase_txt, colore = frasi[0][1], frasi[0][2]
            for soglia, testo, col in frasi:
                if progresso <= soglia:
                    frase_txt, colore = testo, col
                    break

            nota_alc = "\n⚠️ *L'alcol ti ha tolto un po' di appetito...*" if is_alc and idx == passi - 1 else ""

            embed = discord.Embed(
                description=frase_txt.format(u=u),
                color=colore,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=u, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="🥃 Bevanda", value=bevanda,                                                  inline=True)
            embed.add_field(name="💦 Sete",    value=f"{_bar(old_t)}  →  {_bar(sete_attuale)}" + nota_alc,   inline=False)
            embed.add_field(name="➕ Recupero",value=f"+{round(step*(idx+1))}%",                               inline=True)
            embed.set_footer(text=f"🏙️ West Coast RP '93 — Bevanda in corso... ({idx+1}/{passi})")

            if msg is None:
                msg = await interaction.followup.send(embed=embed)
            else:
                await msg.edit(embed=embed)

            if idx < passi - 1:
                await asyncio.sleep(1.2)

        nota_finale = "\n⚠️ *L'alcol ti ha tolto un po' di appetito...*" if is_alc else ""
        embed_finale = discord.Embed(
            title="💧 𝐁𝐞𝐯𝐚𝐧𝐝𝐚 𝐜𝐨𝐧𝐬𝐮𝐦𝐚𝐭𝐚",
            color=discord.Color(0x228B22),
            timestamp=discord.utils.utcnow()
        )
        embed_finale.set_author(name=u, icon_url=interaction.user.display_avatar.url)
        embed_finale.add_field(name="🥃 Bevanda", value=bevanda,                                         inline=False)
        embed_finale.add_field(name="💦 Sete",    value=f"{_bar(old_t)}  →  {_bar(new_t)}" + nota_finale, inline=False)
        embed_finale.add_field(name="➕ Recupero",value=f"+{rip}%",                                       inline=False)
        embed_finale.set_footer(text="🏙️ West Coast RP '93 — Zaino")
        await msg.edit(embed=embed_finale)

    # ── /zaino ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="zaino", description="Visualizza il contenuto del tuo zaino")
    @app_commands.describe(utente="Tag di un altro giocatore (opzionale)")
    async def zaino(interaction: discord.Interaction, utente: discord.Member = None):
        ALLOWED = [STAFF_ROLE_ID, 1404051860121456701, FORZEDELLORDINE_ROLE_ID, STATO_ROLE_ID]
        target = utente or interaction.user

        if not utente and not await _has_zaino(str(interaction.user.id)):
            await interaction.response.send_message(
                "❌ Non hai uno **zaino**! Comprane uno con `/compra-zaino` prima di usare questo comando.",
                ephemeral=True
            )
            return

        if utente and utente.id != interaction.user.id:
            if not isinstance(interaction.user, discord.Member) or \
               not any(r.id in ALLOWED for r in interaction.user.roles):
                await interaction.response.send_message(
                    "❌ Solo Staff e FDO possono vedere lo zaino altrui.", ephemeral=True
                )
                return

        all_items = await database.get_inventory(str(target.id))
        user      = await database.get_user(str(target.id))
        titolo    = f"🎒 Zaino di {target.mention}" if utente else "🎒 Il tuo Zaino"
        B_PER_PAGE = 5
        tot = max(1, -(-len(all_items) // B_PER_PAGE))

        def build_zaino_embed(p: int) -> discord.Embed:
            embed = discord.Embed(title=titolo, color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="🍔 Fame", value=_bar(user["hunger"]), inline=True)
            embed.add_field(name="💦 Sete", value=_bar(user["thirst"]), inline=True)
            page_items = all_items[p * B_PER_PAGE:(p + 1) * B_PER_PAGE]
            if not all_items:
                embed.add_field(name="📦 Contenuto", value="*Zaino vuoto.*", inline=False)
            else:
                desc = "\n".join(f"**{i['item_name']}** — x{i['quantity']}" for i in page_items)
                embed.add_field(name="📦 Contenuto", value=desc, inline=False)
            embed.set_footer(text=f"🏙️ West Coast RP '93 — Zaino | Pagina {p+1}/{tot}")
            return embed

        class ZainoView(discord.ui.View):
            def __init__(self_v, p=0):
                super().__init__(timeout=120)
                self_v.p = p
                self_v._aggiorna()

            def _aggiorna(self_v):
                self_v.prev_btn.disabled = self_v.p == 0
                self_v.next_btn.disabled = self_v.p >= tot - 1

            @discord.ui.button(label="⬅️ Pagina", style=discord.ButtonStyle.primary)
            async def prev_btn(self_v, itr: discord.Interaction, btn):
                self_v.p -= 1
                self_v._aggiorna()
                await itr.response.edit_message(embed=build_zaino_embed(self_v.p), view=self_v)

            @discord.ui.button(label="➡️ Pagina", style=discord.ButtonStyle.primary)
            async def next_btn(self_v, itr: discord.Interaction, btn):
                self_v.p += 1
                self_v._aggiorna()
                await itr.response.edit_message(embed=build_zaino_embed(self_v.p), view=self_v)

        if tot > 1:
            await interaction.response.send_message(embed=build_zaino_embed(0), view=ZainoView(), ephemeral=True)
        else:
            await interaction.response.send_message(embed=build_zaino_embed(0), ephemeral=True)

        if utente and utente.id != interaction.user.id:
            try:
                ch = bot.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log = discord.Embed(title="👁️ 𝐋𝐎𝐆 — 𝐙𝐚𝐢𝐧𝐨 𝐂𝐨𝐧𝐭𝐫𝐨𝐥𝐥𝐚𝐭𝐨", color=discord.Color(0x1E90FF))
                    log.add_field(name="👮 Chi ha guardato", value=interaction.user.mention, inline=True)
                    log.add_field(name="👤 Zaino di",        value=target.mention,           inline=True)
                    await ch.send(embed=log)
            except Exception: pass


    # ── /vendi-zaino ─────────────────────────────────────────────────────────
    @bot.tree.command(name="vendi-zaino", description="Vendi l'intero contenuto del tuo zaino a un altro giocatore")
    @app_commands.describe(acquirente="Il giocatore che compra", prezzo="Prezzo in $ concordato")
    async def vendi_zaino(interaction: discord.Interaction, acquirente: discord.Member, prezzo: int):
        if await _blocca_senza_zaino(interaction):
            return
        if acquirente.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi venderlo a te stesso.", ephemeral=True); return
        if prezzo <= 0:
            await interaction.response.send_message("❌ Il prezzo deve essere positivo.", ephemeral=True); return
        items = await database.get_inventory(str(interaction.user.id))
        if not items:
            await interaction.response.send_message("❌ Il tuo zaino è vuoto!", ephemeral=True); return
        # Lo zaino in sé non si vende, solo il suo contenuto
        items = [i for i in items if i["item_name"] != ZAINO_ITEM_NAME]
        if not items:
            await interaction.response.send_message("❌ Il tuo zaino è vuoto!", ephemeral=True); return
        buyer = await database.get_user(str(acquirente.id))
        if buyer["cash"] < prezzo:
            await interaction.response.send_message(f"❌ {acquirente.display_name} non ha abbastanza contanti.", ephemeral=True); return
        seller = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(acquirente.id),       cash=buyer["cash"] - prezzo)
        await database.update_balance(str(interaction.user.id), cash=seller["cash"] + prezzo)
        for it in items:
            await database.add_item(str(acquirente.id), it["item_name"], it["quantity"])
            await database.remove_item(str(interaction.user.id), it["item_name"], it["quantity"])
        contenuto = "\n".join(f"• {i['item_name']} x{i['quantity']}" for i in items)
        embed = discord.Embed(title="🤝 𝐙𝐚𝐢𝐧𝐨 𝐕𝐞𝐧𝐝𝐮𝐭𝐨", color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
        embed.add_field(name="💰 Prezzo",    value=f"${prezzo:,}",           inline=True)
        embed.add_field(name="👤 Venditore", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 Acquirente",value=acquirente.mention,        inline=True)
        embed.add_field(name="📦 Contenuto", value=contenuto or "—",         inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Scambio")
        await interaction.response.send_message(embed=embed)

    # ── /dai-item ────────────────────────────────────────────────────────────
    async def _dai_item_ac(interaction: discord.Interaction, current: str):
        uid   = str(interaction.user.id)
        items = await database.get_inventory(uid)
        names = [i["item_name"] for i in items]
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, names)[:25]]

    @bot.tree.command(name="dai-item", description="Dai un item dal tuo zaino a un altro giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="L'item da dare", quantita="Quantità")
    @app_commands.autocomplete(item=_dai_item_ac)
    async def dai_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if await _blocca_senza_zaino(interaction):
            return
        if giocatore.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi darti item da solo!", ephemeral=True); return
        if quantita < 1:
            await interaction.response.send_message("❌ Quantità minima: 1.", ephemeral=True); return
        if not await database.remove_item(str(interaction.user.id), item, quantita):
            await interaction.response.send_message(f"❌ Non hai abbastanza **{item}**.", ephemeral=True); return
        await database.add_item(str(giocatore.id), item, quantita)
        try:
            import commands_usura as _cu
            await _cu.applica_calo_passaggio(bot, str(interaction.user.id), item)
        except Exception as e:
            print(f"[dai-item] usura skip: {e}", flush=True)
        embed = discord.Embed(title="🤝 𝐈𝐭𝐞𝐦 𝐂𝐨𝐧𝐬𝐞𝐠𝐧𝐚𝐭𝐨", color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
        embed.add_field(name="📦 Item",     value=item,                     inline=True)
        embed.add_field(name="🔢 Quantità", value=str(quantita),            inline=True)
        embed.add_field(name="👤 Da",       value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 A",        value=giocatore.mention,        inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Scambio")
        await interaction.response.send_message(embed=embed)

    # ── /utilizza-item ───────────────────────────────────────────────────────
    async def _utilizza_item_ac(interaction: discord.Interaction, current: str):
        uid   = str(interaction.user.id)
        items = await database.get_inventory(uid)
        names = [i["item_name"] for i in items]
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, names)[:25]]

    @bot.tree.command(name="utilizza-item", description="Utilizza un item dal tuo zaino")
    @app_commands.describe(item="L'item da utilizzare")
    @app_commands.autocomplete(item=_utilizza_item_ac)
    async def utilizza_item(interaction: discord.Interaction, item: str):
        if await _blocca_senza_zaino(interaction):
            return
        if not await database.remove_item(str(interaction.user.id), item, 1):
            await interaction.response.send_message(f"❌ Non hai **{item}** nello zaino.", ephemeral=True); return
        embed = discord.Embed(
            title="✅ 𝐈𝐭𝐞𝐦 𝐔𝐭𝐢𝐥𝐢𝐳𝐳𝐚𝐭𝐨",
            description=f"*{interaction.user.mention} utilizza **{item}**.*",
            color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🏙️ West Coast RP '93 — Zaino")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    #  /inizio-turno
    # ══════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="inizio-turno", description="Inizia il tuo turno di lavoro")
    @app_commands.describe(
        lavoro="Tag del ruolo lavorativo (@FDO, @Dottore…)",
        stipendio="Il tuo stipendio orario in $"
    )
    async def inizio_turno(interaction: discord.Interaction, lavoro: discord.Role, stipendio: int):
        await interaction.response.defer()
        uid = str(interaction.user.id)

        turno_esistente = await database.get_turno(uid)
        if turno_esistente:
            from datetime import datetime as _dt
            inizio_cached = _dt.fromtimestamp(turno_esistente["inizio_ts"], tz=timezone.utc)
            await interaction.followup.send(
                f"❌ Hai già un turno attivo come **{turno_esistente['role_name']}** iniziato alle "
                f"**{_ora_italia(inizio_cached)}**.\n"
                f"Usa `/fine-turno` prima di iniziarne un altro.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id == lavoro.id for r in interaction.user.roles):
            await interaction.followup.send(
                f"❌ Non hai il ruolo {lavoro.mention} per iniziare questo turno.",
                ephemeral=True
            )
            return

        if stipendio <= 0:
            await interaction.followup.send("❌ Lo stipendio orario deve essere positivo.", ephemeral=True); return

        now = datetime.now(timezone.utc)
        _turni_cache[uid] = lavoro
        await database.save_turno(uid, lavoro.id, lavoro.name, stipendio, now.timestamp())

        embed = discord.Embed(
            title="<a:online:1459627385702973572> 𝐓𝐔𝐑𝐍𝐎 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐎 <a:online:1459627385702973572>",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🧑 Dipendente",    value=interaction.user.mention, inline=False)
        embed.add_field(name="💼 Lavoro",        value=lavoro.mention,           inline=False)
        embed.add_field(name="💵 Stipendio/ora", value=f"${stipendio:,}",        inline=False)
        embed.add_field(name="🕐 Inizio turno",  value=_ora_italia(now), inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Turno di Lavoro")
        await interaction.followup.send(embed=embed, ephemeral=False)

    # ══════════════════════════════════════════════════════════════════════════
    #  /fine-turno
    # ══════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="fine-turno", description="Termina il tuo turno di lavoro")
    @app_commands.describe(lavoro="Tag del ruolo lavorativo con cui hai iniziato il turno")
    async def fine_turno(interaction: discord.Interaction, lavoro: discord.Role):
        await interaction.response.defer()
        uid = str(interaction.user.id)

        turno_db = await database.get_turno(uid)
        if not turno_db:
            await interaction.followup.send(
                "❌ Non hai nessun turno attivo. Usa `/inizio-turno` prima.", ephemeral=True
            )
            return

        if turno_db["role_id"] != lavoro.id:
            await interaction.followup.send(
                f"❌ Il tuo turno attivo è per **{turno_db['role_name']}**, non per {lavoro.mention}.",
                ephemeral=True
            )
            return

        from datetime import datetime as _dt
        now          = datetime.now(timezone.utc)
        inizio       = _dt.fromtimestamp(turno_db["inizio_ts"], tz=timezone.utc)
        durata_s     = (now - inizio).total_seconds()
        ore_esatte    = durata_s / 3600
        ore_fatturate = max(0.5, math.floor(ore_esatte * 2 + 0.5) / 2)

        stipendio_totale = round(turno_db["stipendio"] * ore_fatturate)

        h_display  = int(durata_s // 3600)
        m_display  = int((durata_s % 3600) // 60)
        durata_str = f"{h_display}h {m_display}min" if h_display > 0 else f"{m_display}min"

        await database.delete_turno(uid)
        _turni_cache.pop(uid, None)

        embed_fine = discord.Embed(
            title="<a:offline:1459628872197738641> 𝐓𝐔𝐑𝐍𝐎 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐎 <a:offline:1459628872197738641>",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed_fine.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed_fine.add_field(name="🧑 Dipendente",       value=interaction.user.mention,               inline=False)
        embed_fine.add_field(name="​", value="​", inline=False)
        embed_fine.add_field(name="💼 Lavoro",           value=lavoro.mention,                         inline=False)
        embed_fine.add_field(name="​", value="​", inline=False)
        embed_fine.add_field(name="🕐 Inizio",           value=_ora_italia(inizio),           inline=True)
        embed_fine.add_field(name="🕑 Fine",             value=_ora_italia(now),              inline=True)
        embed_fine.add_field(name="​", value="​", inline=False)
        embed_fine.add_field(name="⏱️ Durata reale",     value=durata_str,                             inline=True)
        embed_fine.add_field(name="📋 Ore fatturate",    value=f"{ore_fatturate}h (arrot. mezz'ora)",  inline=True)
        embed_fine.add_field(name="​", value="​", inline=False)
        embed_fine.add_field(name="💵 Stipendio/ora",    value=f"${turno_db['stipendio']:,}",          inline=True)
        embed_fine.add_field(name="💰 Totale da pagare", value=f"**${stipendio_totale:,}**",           inline=True)
        embed_fine.set_footer(text="🏙️ West Coast RP '93 — Turno di Lavoro")

        await interaction.followup.send(embed=embed_fine)

        embed_staff = discord.Embed(
            title="💼 𝐑𝐈𝐂𝐇𝐈𝐄𝐒𝐓𝐀 𝐏𝐀𝐆𝐀𝐌𝐄𝐍𝐓𝐎 𝐒𝐓𝐈𝐏𝐄𝐍𝐃𝐈𝐎",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed_staff.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed_staff.add_field(name="🧑 Dipendente",       value=interaction.user.mention,               inline=False)
        embed_staff.add_field(name="​", value="​", inline=False)
        embed_staff.add_field(name="💼 Ruolo",            value=lavoro.mention,                         inline=False)
        embed_staff.add_field(name="​", value="​", inline=False)
        embed_staff.add_field(name="🕐 Inizio turno",     value=_ora_italia(inizio),           inline=True)
        embed_staff.add_field(name="🕑 Fine turno",       value=_ora_italia(now),              inline=True)
        embed_staff.add_field(name="​", value="​", inline=False)
        embed_staff.add_field(name="⏱️ Durata",           value=durata_str,                             inline=True)
        embed_staff.add_field(name="📋 Ore fatturate",    value=f"{ore_fatturate}h",                    inline=True)
        embed_staff.add_field(name="​", value="​", inline=False)
        embed_staff.add_field(name="💵 Stipendio/ora",    value=f"${turno_db['stipendio']:,}",          inline=True)
        embed_staff.add_field(name="💰 Da pagare",        value=f"**${stipendio_totale:,}**",           inline=True)
        embed_staff.set_footer(text="🏙️ West Coast RP '93 — Usa /paga-stipendio per pagare")

        try:
            stipendio_ch = bot.get_channel(STIPENDIO_CHANNEL_ID)
            if stipendio_ch:
                await stipendio_ch.send(
                    content=f"<@&{STAFF_ROLE_ID}> Paga lo stipendio!",
                    embed=embed_staff
                )
        except Exception: pass

    # ── /rifugio ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="rifugio", description="Monta o smonta il tuo rifugio di fortuna")
    @app_commands.describe(azione="Monta o smonta", luogo="Dove (opzionale)", foto="Foto del rifugio (opzionale)")
    @app_commands.choices(azione=[
        app_commands.Choice(name="🏚️ Monta rifugio",  value="monta"),
        app_commands.Choice(name="📦 Smonta rifugio",  value="smonta"),
    ])
    async def rifugio(interaction: discord.Interaction, azione: str, luogo: str = "", foto: discord.Attachment = None):
        if azione == "monta":
            title = "🏚️ 𝐑𝐢𝐟𝐮𝐠𝐢𝐨 𝐌𝐨𝐧𝐭𝐚𝐭𝐨"
            desc  = f"*{interaction.user.mention} monta il proprio rifugio di fortuna" + (f" a **{luogo}**.*" if luogo else ".*")
        else:
            title = "📦 𝐑𝐢𝐟𝐮𝐠𝐢𝐨 𝐒𝐦𝐨𝐧𝐭𝐚𝐭𝐨"
            desc  = f"*{interaction.user.mention} smonta il proprio rifugio di fortuna" + (f" da **{luogo}**.*" if luogo else ".*")
        embed = discord.Embed(title=title, description=desc, color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if foto and foto.content_type and foto.content_type.startswith("image/"):
            embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Rifugio")
        await interaction.response.send_message(embed=embed)

    # ── /anonimo ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo nel canale")
    @app_commands.describe(messaggio="Il messaggio anonimo")
    async def anonimo(interaction: discord.Interaction, messaggio: str):
        import re as _re

        role_ids  = _re.findall(r'<@&(\d+)>',  messaggio)
        user_ids  = _re.findall(r'<@!?(\d+)>', messaggio)

        guild = interaction.guild
        role_mentions  = []
        member_mentions = []

        if guild:
            for rid in role_ids:
                role = guild.get_role(int(rid))
                if role:
                    role_mentions.append(role.mention)
            for uid in user_ids:
                member = guild.get_member(int(uid))
                if member:
                    member_mentions.append(member.mention)

        avviso = ""
        if role_mentions and member_mentions:
            avviso = f"📝 In questo messaggio sono stati menzionati i ruoli e i membri: {' '.join(role_mentions)} {' '.join(member_mentions)}"
        elif role_mentions:
            avviso = f"📝 In questo messaggio sono stati menzionati i ruoli: {' '.join(role_mentions)}"
        elif member_mentions:
            avviso = f"📝 In questo messaggio sono stati menzionati i membri: {' '.join(member_mentions)}"

        embed = discord.Embed(description=f"*\"{messaggio}\"*", color=discord.Color(0x2C2C2C), timestamp=discord.utils.utcnow())
        embed.set_author(name="🎭 𝐌𝐞𝐬𝐬𝐚𝐠𝐠𝐢𝐨 𝐀𝐧𝐨𝐧𝐢𝐦𝐨")
        embed.set_footer(text="🏙️ West Coast RP '93 — Anonimo")
        await interaction.response.send_message("✅ Messaggio inviato anonimamente.", ephemeral=True)
        if avviso:
            await interaction.channel.send(content=avviso, embed=embed)
        else:
            await interaction.channel.send(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(
                    title="🎭 LOG — Messaggio Anonimo",
                    color=discord.Color(0x2C2C2C),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="👤 Autore reale",  value=interaction.user.mention,        inline=True)
                log.add_field(name="📢 Canale",        value=interaction.channel.mention,     inline=True)
                log.add_field(name="💬 Messaggio",     value=messaggio[:1024],                inline=False)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /nascondo ────────────────────────────────────────────────────────────
    async def _nascondo_ac(interaction: discord.Interaction, current: str):
        uid   = str(interaction.user.id)
        items = await database.get_inventory(uid)
        names = [i["item_name"] for i in items]
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, names)[:25]]

    @bot.tree.command(name="nascondo", description="Nascondi un oggetto dal tuo zaino in un luogo segreto")
    @app_commands.describe(
        oggetto="L'oggetto da nascondere (dal tuo zaino)",
        luogo="Il luogo segreto",
        quantita="Quantità da nascondere (default 1)",
        foto="Foto del luogo (opzionale)"
    )
    @app_commands.autocomplete(oggetto=_nascondo_ac)
    async def nascondo(interaction: discord.Interaction, oggetto: str, luogo: str,
                       quantita: int = 1, foto: discord.Attachment = None):
        if await _blocca_senza_zaino(interaction):
            return
        uid = str(interaction.user.id)

        if quantita < 1:
            await interaction.response.send_message("❌ Quantità minima: 1.", ephemeral=True)
            return

        qty_in_inventario = await database.get_item_quantity(uid, oggetto)
        if qty_in_inventario < quantita:
            await interaction.response.send_message(
                f"❌ Non hai abbastanza **{oggetto}** nello zaino. (Hai: {qty_in_inventario})",
                ephemeral=True
            )
            return

        await database.remove_item(uid, oggetto, quantita)
        hide_id = await database.hide_item(uid, oggetto, quantita, luogo)

        embed = discord.Embed(
            title="🙈 𝐎𝐠𝐠𝐞𝐭𝐭𝐨 𝐍𝐚𝐬𝐜𝐨𝐬𝐭𝐨",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📦 Oggetto",  value=f"{oggetto} x{quantita}", inline=True)
        embed.add_field(name="🔢 ID Nascondiglio", value=f"#{hide_id}",     inline=True)
        embed.add_field(name="📍 Luogo",    value=luogo,                    inline=False)
        if foto and foto.content_type and foto.content_type.startswith("image/"):
            embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Usa /recupera-oggetto per riprendere l'oggetto")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🙈 LOG — Oggetto Nascosto", color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente",   value=interaction.user.mention,    inline=True)
                log.add_field(name="📦 Oggetto",  value=f"{oggetto} x{quantita}",    inline=True)
                log.add_field(name="📍 Luogo",    value=luogo,                       inline=True)
                log.add_field(name="🔢 ID",       value=f"#{hide_id}",               inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /recupera-oggetto ─────────────────────────────────────────────────────
    async def _recupera_ac(interaction: discord.Interaction, current: str):
        uid   = str(interaction.user.id)
        items = await database.get_hidden_items(uid)
        scelte = []
        for i in items:
            label = f"#{i['id']} — {i['item_name']} x{i['quantity']} ({i['luogo']})"[:100]
            scelte.append(app_commands.Choice(name=label, value=str(i["id"])))
        if current:
            scelte = [s for s in scelte if current.lower() in s.name.lower()]
        return scelte[:25]

    @bot.tree.command(name="recupera-oggetto", description="Recupera un oggetto che hai nascosto")
    @app_commands.describe(oggetto="L'oggetto nascosto da recuperare")
    @app_commands.autocomplete(oggetto=_recupera_ac)
    async def recupera_oggetto(interaction: discord.Interaction, oggetto: str):
        if await _blocca_senza_zaino(interaction):
            return
        uid = str(interaction.user.id)

        try:
            hide_id = int(oggetto)
        except ValueError:
            await interaction.response.send_message("❌ Seleziona un oggetto dalla lista.", ephemeral=True)
            return

        hidden_items = await database.get_hidden_items(uid)
        item = next((i for i in hidden_items if i["id"] == hide_id), None)

        if not item:
            await interaction.response.send_message(
                "❌ Non hai nessun oggetto nascosto con questo ID, o non ti appartiene.", ephemeral=True
            )
            return

        await database.recover_hidden_item(hide_id)
        await database.add_item(uid, item["item_name"], item["quantity"])

        embed = discord.Embed(
            title="✅ 𝐎𝐠𝐠𝐞𝐭𝐭𝐨 𝐑𝐞𝐜𝐮𝐩𝐞𝐫𝐚𝐭𝐨",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📦 Oggetto",  value=f"{item['item_name']} x{item['quantity']}", inline=True)
        embed.add_field(name="📍 Era in",   value=item["luogo"],                               inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Zaino")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="✅ LOG — Oggetto Recuperato", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente",  value=interaction.user.mention,                   inline=True)
                log.add_field(name="📦 Oggetto", value=f"{item['item_name']} x{item['quantity']}",  inline=True)
                log.add_field(name="📍 Era in",  value=item["luogo"],                               inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /lettera ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="lettera", description="Invia una lettera privata a un altro giocatore")
    @app_commands.describe(destinatario="Il giocatore che riceverà la lettera")
    async def lettera(interaction: discord.Interaction, destinatario: discord.Member):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi inviare una lettera a te stesso.", ephemeral=True)
            return
        if destinatario.bot:
            await interaction.response.send_message("❌ Non puoi inviare una lettera a un bot.", ephemeral=True)
            return

        class LetteraModal(discord.ui.Modal, title="✉️ 𝐒𝐜𝐫𝐢𝐯𝐢 𝐥𝐚 𝐭𝐮𝐚 𝐥𝐞𝐭𝐭𝐞𝐫𝐚"):
            contenuto = discord.ui.TextInput(
                label="Contenuto della lettera",
                style=discord.TextStyle.long,
                placeholder="Scrivi qui il contenuto della lettera...",
                required=True,
                max_length=1800
            )
            mittente = discord.ui.TextInput(
                label="Mittente",
                style=discord.TextStyle.short,
                placeholder="Es: Carl Johnson",
                required=True,
                max_length=100
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                COLOR_AVORIO = 0xF5F0DC

                embed_dm = discord.Embed(
                    title="✉️ 𝐇𝐚𝐢 𝐫𝐢𝐜𝐞𝐯𝐮𝐭𝐨 𝐮𝐧𝐚 𝐥𝐞𝐭𝐭𝐞𝐫𝐚",
                    color=COLOR_AVORIO,
                    timestamp=discord.utils.utcnow()
                )
                embed_dm.add_field(name="📤 Mittente",          value=interaction.user.mention,  inline=False)
                embed_dm.add_field(name="📬 Destinatario",      value=destinatario.mention,      inline=False)
                embed_dm.add_field(name="📜 Contenuto lettera", value=self.contenuto.value,      inline=False)
                embed_dm.add_field(name="🖊️ Firma",            value=f"__{self.mittente.value}__", inline=False)
                embed_dm.set_footer(text="🏙️ West Coast RP '93 — Posta di Los Santos")

                inviata = False
                try:
                    await destinatario.send(embed=embed_dm)
                    inviata = True
                except discord.Forbidden:
                    pass

                if inviata:
                    await modal_interaction.response.send_message(
                        f"✅ Lettera consegnata a {destinatario.mention} via DM.", ephemeral=True
                    )
                else:
                    await modal_interaction.response.send_message(
                        f"⚠️ Impossibile consegnare la lettera: {destinatario.mention} ha i DM disabilitati.",
                        ephemeral=True
                    )

                try:
                    ch = bot.get_channel(LOG_CHANNEL_ID)
                    if ch:
                        embed_log = discord.Embed(
                            title="✉️ 𝐋𝐎𝐆 — 𝐋𝐞𝐭𝐭𝐞𝐫𝐚 𝐈𝐧𝐯𝐢𝐚𝐭𝐚",
                            color=COLOR_AVORIO,
                            timestamp=discord.utils.utcnow()
                        )
                        embed_log.add_field(name="📤 Mittente",          value=interaction.user.mention,    inline=False)
                        embed_log.add_field(name="📬 Destinatario",      value=destinatario.mention,        inline=False)
                        embed_log.add_field(name="📜 Contenuto lettera", value=self.contenuto.value,        inline=False)
                        embed_log.add_field(name="🖊️ Firma",            value=f"__{self.mittente.value}__", inline=False)
                        await ch.send(embed=embed_log)
                except Exception:
                    pass

        await interaction.response.send_modal(LetteraModal())
