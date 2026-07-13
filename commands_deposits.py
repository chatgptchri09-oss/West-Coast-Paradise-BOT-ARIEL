import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database
from datetime import datetime, timezone
from constants import (
    LOG_CHANNEL_ID, DATABASE_NAME, has_staff,
    FORZEDELLORDINE_ROLE_ID, SHERIFF_ROLE_ID, FBI_ROLE_ID,
    ARMERIA_ROLE_ID, CONCESSIONARIO_ROLE_ID,
    BAR_ROLE_ID, MARKET_ROLE_ID, DOTTORE_ROLE_ID,
    MECCANICO_ROLE_ID, PEGASUS_ROLE_ID,
)

# ── Ruoli fazioni extra ───────────────────────────────────────────────────────
VAGOS_ROLE_ID     = 1525774939796406292
BALLAS_ROLE_ID    = 1494988697127485513
MARABUNTA_ROLE_ID = 1495036199096811570
LOST_MC_ROLE_ID   = 1496603144551923905
FAMIGLIA_ROLE_ID  = 1501323223411855583

DEPOSITI = {
    "fdo":            {"label": "🚔 Forze dell'Ordine",  "emoji": "🚔", "color": 0x1565C0, "ruoli": [FORZEDELLORDINE_ROLE_ID, SHERIFF_ROLE_ID, FBI_ROLE_ID]},
    "armeria":        {"label": "🔫 Armeria",             "emoji": "🔫", "color": 0xFF3D00, "ruoli": [ARMERIA_ROLE_ID]},
    "concessionario": {"label": "🚗 Concessionario",      "emoji": "🚗", "color": 0xFFD600, "ruoli": [CONCESSIONARIO_ROLE_ID]},
    "bar":            {"label": "🍻 Bar",                 "emoji": "🍻", "color": 0xFF6F00, "ruoli": [BAR_ROLE_ID]},
    "market":         {"label": "🏪 Market",              "emoji": "🏪", "color": 0x00E676, "ruoli": [MARKET_ROLE_ID]},
    "ospedale":       {"label": "🏥 Ospedale",            "emoji": "🏥", "color": 0xF50057, "ruoli": [DOTTORE_ROLE_ID]},
    "meccanico":      {"label": "🔧 Meccanico",           "emoji": "🔧", "color": 0xFF9100, "ruoli": [MECCANICO_ROLE_ID]},
    "pegasus":        {"label": "🚁 Pegasus",             "emoji": "🚁", "color": 0x00B0FF, "ruoli": [PEGASUS_ROLE_ID]},
    "vagos":          {"label": "💛 Vagos",               "emoji": "💛", "color": 0xFFD600, "ruoli": [VAGOS_ROLE_ID]},
    "ballas":         {"label": "💜 Ballas",              "emoji": "💜", "color": 0xAA00FF, "ruoli": [BALLAS_ROLE_ID]},
    "marabunta":      {"label": "💙 Marabunta Grande",    "emoji": "💙", "color": 0x2979FF, "ruoli": [MARABUNTA_ROLE_ID]},
    "lost_mc":        {"label": "🏍️ Lost MC",            "emoji": "🏍️", "color": 0x212121, "ruoli": [LOST_MC_ROLE_ID]},
    "famiglia":       {"label": "🤵 Famiglia",            "emoji": "🤵", "color": 0x37474F, "ruoli": [FAMIGLIA_ROLE_ID]},
}

DEPOSITI_CHOICES = [app_commands.Choice(name=v["label"], value=k) for k, v in DEPOSITI.items()]

def _ha_accesso(interaction: discord.Interaction, dep: str) -> bool:
    if has_staff(interaction): return True
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id in DEPOSITI[dep]["ruoli"] for r in interaction.user.roles)

def _fuzzy(q: str, candidates: list) -> list:
    q = q.lower().strip()
    if not q: return candidates
    words = q.split()
    r = [c for c in candidates if all(w in c.lower() for w in words)]
    return r or [c for c in candidates if any(w in c.lower() for w in words)]

def _ora() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")

def _color(dep: str) -> int:
    return DEPOSITI[dep].get("color", 0x00E676)

# ── DB ────────────────────────────────────────────────────────────────────────
async def _init():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                deposito  TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity  INTEGER DEFAULT 0,
                PRIMARY KEY (deposito, item_name)
            )
        """)
        await db.commit()

async def _get_items(dep: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name, quantity FROM deposits WHERE deposito=? AND quantity>0 ORDER BY item_name", (dep,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def _get_qty(dep: str, item: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM deposits WHERE deposito=? AND item_name=?", (dep, item)
        ) as c:
            r = await c.fetchone()
            return r[0] if r else 0

async def _add(dep: str, item: str, qty: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO deposits (deposito, item_name, quantity) VALUES (?,?,?)
            ON CONFLICT(deposito, item_name) DO UPDATE SET quantity=quantity+excluded.quantity
        """, (dep, item, qty))
        await db.commit()

async def _remove(dep: str, item: str, qty: int) -> bool:
    cur = await _get_qty(dep, item)
    if cur < qty: return False
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE deposits SET quantity=quantity-? WHERE deposito=? AND item_name=?", (qty, dep, item)
        )
        await db.commit()
    return True

# ── EMBED BUILDER ─────────────────────────────────────────────────────────────
def _embed_lista_preleva(dep: str, items: list, pagina: int, tot: int, per_pag: int) -> discord.Embed:
    info = DEPOSITI[dep]
    s, e = pagina * per_pag, min((pagina + 1) * per_pag, len(items))
    embed = discord.Embed(
        title=f"{info['emoji']}  MAGAZZINO — RITIRO MATERIALE",
        color=_color(dep), timestamp=discord.utils.utcnow()
    )
    embed.description = (
        f"**Struttura:** `{info['label']}`\n"
        f"**Inventario disponibile:** `{len(items)} tipi di oggetti`\n"
        f"**Pagina:** `{pagina+1} / {tot}`  •  `{s+1}–{e}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Seleziona un oggetto dal menu per ritirarlo."
    )
    chunk = items[s:e]
    if chunk:
        righe = "\n".join(f"`{i['item_name']}`  ×{i['quantity']}" for i in chunk[:10])
        embed.add_field(name="📋 Contenuto Magazzino", value=righe, inline=False)
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed

def _embed_lista_deposita(dep: str, items: list, pagina: int, tot: int, per_pag: int) -> discord.Embed:
    info = DEPOSITI[dep]
    s, e = pagina * per_pag, min((pagina + 1) * per_pag, len(items))
    embed = discord.Embed(
        title=f"{info['emoji']}  MAGAZZINO — DEPOSITO MATERIALE",
        color=_color(dep), timestamp=discord.utils.utcnow()
    )
    embed.description = (
        f"**Struttura:** `{info['label']}`\n"
        f"**Nel tuo inventario:** `{len(items)} oggetti`\n"
        f"**Pagina:** `{pagina+1} / {tot}`  •  `{s+1}–{e}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Seleziona un oggetto dal tuo inventario per depositarlo."
    )
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed

def _embed_qty_preleva(dep: str, item: str, qty_dep: int) -> discord.Embed:
    embed = discord.Embed(
        title="🔢  RITIRO — SCEGLI QUANTITÀ",
        color=_color(dep), timestamp=discord.utils.utcnow()
    )
    embed.description = (
        f"**Oggetto:** `{item}`\n"
        f"**Disponibile in magazzino:** `×{qty_dep}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Usa il menu per scegliere la quantità\n"
        f"oppure inserisci un numero personalizzato."
    )
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed

def _embed_qty_deposita(dep: str, item: str, qty_inv: int) -> discord.Embed:
    embed = discord.Embed(
        title="🔢  DEPOSITO — SCEGLI QUANTITÀ",
        color=_color(dep), timestamp=discord.utils.utcnow()
    )
    embed.description = (
        f"**Oggetto:** `{item}`\n"
        f"**Nel tuo inventario:** `×{qty_inv}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Usa il menu per scegliere la quantità\n"
        f"oppure inserisci un numero personalizzato."
    )
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed

def _embed_conferma(dep: str, item: str, qty: int, qty_dopo: int, tipo: str) -> discord.Embed:
    if tipo == "preleva":
        titolo = "⚠️  CONFERMA RITIRO"
        riga   = f"**Rimanente in magazzino dopo:** `×{qty_dopo}`"
    else:
        titolo = "⚠️  CONFERMA DEPOSITO"
        riga   = f"**Rimanente nel tuo inventario:** `×{qty_dopo}`"
    embed = discord.Embed(title=titolo, color=discord.Color(0xFF9100), timestamp=discord.utils.utcnow())
    embed.description = (
        f"**Struttura:** `{DEPOSITI[dep]['label']}`\n"
        f"**Oggetto:** `{item}`\n"
        f"**Quantità:** `×{qty}`\n"
        f"{riga}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Conferma o annulla l'operazione."
    )
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed

def _embed_pub_preleva(dep: str, item: str, qty: int, member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="✅  RITIRO COMPLETATO",
        color=discord.Color(0x00E676), timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Operatore",   value=member.mention,             inline=True)
    embed.add_field(name="🏢 Struttura",   value=f"`{DEPOSITI[dep]['label']}`", inline=True)
    embed.add_field(name="\u200b",         value="\u200b",                   inline=False)
    embed.add_field(name="📦 Oggetto",     value=f"`{item}`",                inline=True)
    embed.add_field(name="🔢 Quantità",    value=f"`×{qty}`",                inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed

def _embed_pub_deposita(dep: str, item: str, qty: int, member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="✅  DEPOSITO COMPLETATO",
        color=discord.Color(0x00B0FF), timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Operatore",  value=member.mention,              inline=True)
    embed.add_field(name="🏢 Struttura",  value=f"`{DEPOSITI[dep]['label']}`", inline=True)
    embed.add_field(name="\u200b",        value="\u200b",                    inline=False)
    embed.add_field(name="📦 Oggetto",    value=f"`{item}`",                 inline=True)
    embed.add_field(name="🔢 Quantità",   value=f"`×{qty}`",                 inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
    return embed


# ═════════════════════════════════════════════════════════════════════════════
#  MODAL QUANTITÀ PERSONALIZZATA
# ═════════════════════════════════════════════════════════════════════════════
class QtyModalPreleva(discord.ui.Modal, title="Inserisci quantità da ritirare"):
    q = discord.ui.TextInput(label="Quantità", placeholder="Es: 5", required=True, max_length=6)

    def __init__(self, bot, member, dep, item, qty_dep):
        super().__init__()
        self.bot = bot; self.member = member; self.dep = dep
        self.item = item; self.qty_dep = qty_dep
        self.q.label = f"Quanti '{item[:35]}' vuoi ritirare? (max {qty_dep})"

    async def on_submit(self, interaction: discord.Interaction):
        try: qty = int(self.q.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Inserisci un numero valido.", ephemeral=True); return
        if qty <= 0 or qty > self.qty_dep:
            await interaction.response.send_message(f"❌ Valore non valido. Max: `{self.qty_dep}`", ephemeral=True); return
        view = ConfermaView(self.bot, self.member, self.dep, self.item, qty, "preleva")
        await interaction.response.send_message(
            embed=_embed_conferma(self.dep, self.item, qty, self.qty_dep - qty, "preleva"),
            view=view, ephemeral=True
        )


class QtyModalDeposita(discord.ui.Modal, title="Inserisci quantità da depositare"):
    q = discord.ui.TextInput(label="Quantità", placeholder="Es: 5", required=True, max_length=6)

    def __init__(self, bot, member, dep, item, qty_inv):
        super().__init__()
        self.bot = bot; self.member = member; self.dep = dep
        self.item = item; self.qty_inv = qty_inv
        self.q.label = f"Quanti '{item[:35]}' vuoi depositare? (max {qty_inv})"

    async def on_submit(self, interaction: discord.Interaction):
        try: qty = int(self.q.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Inserisci un numero valido.", ephemeral=True); return
        if qty <= 0 or qty > self.qty_inv:
            await interaction.response.send_message(f"❌ Valore non valido. Max: `{self.qty_inv}`", ephemeral=True); return
        view = ConfermaView(self.bot, self.member, self.dep, self.item, qty, "deposita")
        await interaction.response.send_message(
            embed=_embed_conferma(self.dep, self.item, qty, self.qty_inv - qty, "deposita"),
            view=view, ephemeral=True
        )


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW CONFERMA
# ═════════════════════════════════════════════════════════════════════════════
class ConfermaView(discord.ui.View):
    def __init__(self, bot, member, dep, item, qty, tipo):
        super().__init__(timeout=60)
        self.bot = bot; self.member = member; self.dep = dep
        self.item = item; self.qty = qty; self.tipo = tipo

    @discord.ui.button(label="✅ Conferma", style=discord.ButtonStyle.success)
    async def conferma(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
        if self.tipo == "preleva":
            ok = await _remove(self.dep, self.item, self.qty)
            if not ok:
                await interaction.response.edit_message(
                    content="❌ Quantità non più disponibile in magazzino.", embed=None, view=None); return
            await database.add_item(str(self.member.id), self.item, self.qty)
            pub = _embed_pub_preleva(self.dep, self.item, self.qty, self.member)
        else:
            ok = await database.remove_item(str(self.member.id), self.item, self.qty)
            if not ok:
                await interaction.response.edit_message(
                    content="❌ Non hai abbastanza oggetti nell'inventario.", embed=None, view=None); return
            await _add(self.dep, self.item, self.qty)
            pub = _embed_pub_deposita(self.dep, self.item, self.qty, self.member)

        await interaction.response.edit_message(content="", embed=pub, view=None)
        await interaction.channel.send(embed=pub)

        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                titolo = "📤 LOG — Ritiro Magazzino" if self.tipo == "preleva" else "📥 LOG — Deposito Magazzino"
                log = discord.Embed(title=titolo,
                    color=discord.Color(0x00E676) if self.tipo == "preleva" else discord.Color(0x00B0FF),
                    timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Operatore", value=self.member.mention, inline=True)
                log.add_field(name="🏢 Struttura", value=DEPOSITI[self.dep]["label"], inline=True)
                log.add_field(name="📦 Oggetto", value=f"`{self.item} ×{self.qty}`", inline=True)
                log.set_footer(text=f"🏙️ West Coast RP '93 — {_ora()}")
                await ch.send(embed=log)
        except Exception: pass

    @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.danger)
    async def annulla(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
        await interaction.response.edit_message(content="❌ Operazione annullata.", embed=None, view=None)


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW LISTA PRELIEVO
# ═════════════════════════════════════════════════════════════════════════════
class PrelievoListaView(discord.ui.View):
    PER_PAG = 25
    def __init__(self, bot, member, dep, items, pagina=0):
        super().__init__(timeout=300)
        self.bot = bot; self.member = member; self.dep = dep
        self.items = items; self.pagina = pagina
        self.tot = max(1, -(-len(items) // self.PER_PAG))
        self._build()

    def _build(self):
        self.clear_items()
        s = self.pagina * self.PER_PAG
        chunk = self.items[s:s + self.PER_PAG]
        opts = [discord.SelectOption(label=i["item_name"][:80], description=f"×{i['quantity']} disponibili", value=i["item_name"])
                for i in chunk] or [discord.SelectOption(label="Magazzino vuoto", value="__vuoto__")]
        sel = discord.ui.Select(placeholder="▼  Seleziona oggetto da ritirare...", options=opts)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.member.id:
                await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
            v = interaction.data["values"][0]
            if v == "__vuoto__":
                await interaction.response.send_message("❌ Magazzino vuoto.", ephemeral=True); return
            qty_dep = await _get_qty(self.dep, v)
            view2 = PrelievoQtyView(self.bot, self.member, self.dep, v, qty_dep, self)
            await interaction.response.edit_message(embed=_embed_qty_preleva(self.dep, v, qty_dep), view=view2)

        sel.callback = _cb
        self.add_item(sel)

        bp = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self.pagina == 0, row=1)
        bn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=self.pagina >= self.tot - 1, row=1)
        bc = discord.ui.Button(label="✖ Chiudi", style=discord.ButtonStyle.danger, row=1)

        async def _prev(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            self.pagina -= 1; self._build()
            await i.response.edit_message(embed=_embed_lista_preleva(self.dep, self.items, self.pagina, self.tot, self.PER_PAG), view=self)
        async def _next(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            self.pagina += 1; self._build()
            await i.response.edit_message(embed=_embed_lista_preleva(self.dep, self.items, self.pagina, self.tot, self.PER_PAG), view=self)
        async def _close(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            await i.response.edit_message(content="✅ Pannello chiuso.", embed=None, view=None)

        bp.callback = _prev; bn.callback = _next; bc.callback = _close
        self.add_item(bp); self.add_item(bn); self.add_item(bc)


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW QTY PRELIEVO
# ═════════════════════════════════════════════════════════════════════════════
class PrelievoQtyView(discord.ui.View):
    def __init__(self, bot, member, dep, item, qty_dep, parent):
        super().__init__(timeout=300)
        self.bot = bot; self.member = member; self.dep = dep
        self.item = item; self.qty_dep = qty_dep; self.parent = parent
        self._build()

    def _build(self):
        self.clear_items()
        max_q = min(self.qty_dep, 25)
        opts = [discord.SelectOption(label=f"×{i}", value=str(i)) for i in range(1, max_q + 1)] \
               or [discord.SelectOption(label="0", value="0")]
        sel = discord.ui.Select(placeholder=f"▼  Quantità (1–{max_q})...", options=opts)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.member.id: await interaction.response.send_message("❌", ephemeral=True); return
            qty = int(interaction.data["values"][0])
            view_c = ConfermaView(self.bot, self.member, self.dep, self.item, qty, "preleva")
            await interaction.response.edit_message(embed=_embed_conferma(self.dep, self.item, qty, self.qty_dep - qty, "preleva"), view=view_c)

        sel.callback = _cb
        self.add_item(sel)
        bc = discord.ui.Button(label="🔢 Numero personalizzato", style=discord.ButtonStyle.primary, row=1)
        bb = discord.ui.Button(label="◀ Indietro", style=discord.ButtonStyle.secondary, row=1)

        async def _custom(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            await i.response.send_modal(QtyModalPreleva(self.bot, self.member, self.dep, self.item, self.qty_dep))
        async def _back(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            self.parent._build()
            await i.response.edit_message(embed=_embed_lista_preleva(self.dep, self.parent.items, self.parent.pagina, self.parent.tot, self.parent.PER_PAG), view=self.parent)

        bc.callback = _custom; bb.callback = _back
        self.add_item(bc); self.add_item(bb)


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW LISTA DEPOSITO
# ═════════════════════════════════════════════════════════════════════════════
class DepositaListaView(discord.ui.View):
    PER_PAG = 25
    def __init__(self, bot, member, dep, items, pagina=0):
        super().__init__(timeout=300)
        self.bot = bot; self.member = member; self.dep = dep
        self.items = items; self.pagina = pagina
        self.tot = max(1, -(-len(items) // self.PER_PAG))
        self._build()

    def _build(self):
        self.clear_items()
        s = self.pagina * self.PER_PAG
        chunk = self.items[s:s + self.PER_PAG]
        opts = [discord.SelectOption(label=i["item_name"][:80], description=f"×{i['quantity']} in inventario", value=i["item_name"])
                for i in chunk] or [discord.SelectOption(label="Inventario vuoto", value="__vuoto__")]
        sel = discord.ui.Select(placeholder="▼  Seleziona oggetto da depositare...", options=opts)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.member.id: await interaction.response.send_message("❌", ephemeral=True); return
            v = interaction.data["values"][0]
            if v == "__vuoto__": await interaction.response.send_message("❌ Inventario vuoto.", ephemeral=True); return
            qty_inv = await database.get_item_quantity(str(self.member.id), v)
            view2 = DepositaQtyView(self.bot, self.member, self.dep, v, qty_inv, self)
            await interaction.response.edit_message(embed=_embed_qty_deposita(self.dep, v, qty_inv), view=view2)

        sel.callback = _cb
        self.add_item(sel)
        bp = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self.pagina == 0, row=1)
        bn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=self.pagina >= self.tot - 1, row=1)

        async def _prev(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            self.pagina -= 1; self._build()
            await i.response.edit_message(embed=_embed_lista_deposita(self.dep, self.items, self.pagina, self.tot, self.PER_PAG), view=self)
        async def _next(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            self.pagina += 1; self._build()
            await i.response.edit_message(embed=_embed_lista_deposita(self.dep, self.items, self.pagina, self.tot, self.PER_PAG), view=self)

        bp.callback = _prev; bn.callback = _next
        self.add_item(bp); self.add_item(bn)


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW QTY DEPOSITO
# ═════════════════════════════════════════════════════════════════════════════
class DepositaQtyView(discord.ui.View):
    def __init__(self, bot, member, dep, item, qty_inv, parent):
        super().__init__(timeout=300)
        self.bot = bot; self.member = member; self.dep = dep
        self.item = item; self.qty_inv = qty_inv; self.parent = parent
        self._build()

    def _build(self):
        self.clear_items()
        max_q = min(self.qty_inv, 25)
        opts = [discord.SelectOption(label=f"×{i}", value=str(i)) for i in range(1, max_q + 1)] \
               or [discord.SelectOption(label="0", value="0")]
        sel = discord.ui.Select(placeholder=f"▼  Quantità (1–{max_q})...", options=opts)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.member.id: await interaction.response.send_message("❌", ephemeral=True); return
            qty = int(interaction.data["values"][0])
            view_c = ConfermaView(self.bot, self.member, self.dep, self.item, qty, "deposita")
            await interaction.response.edit_message(embed=_embed_conferma(self.dep, self.item, qty, self.qty_inv - qty, "deposita"), view=view_c)

        sel.callback = _cb
        self.add_item(sel)
        bc = discord.ui.Button(label="🔢 Numero personalizzato", style=discord.ButtonStyle.primary, row=1)
        bb = discord.ui.Button(label="◀ Indietro", style=discord.ButtonStyle.secondary, row=1)

        async def _custom(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            await i.response.send_modal(QtyModalDeposita(self.bot, self.member, self.dep, self.item, self.qty_inv))
        async def _back(i):
            if i.user.id != self.member.id: await i.response.send_message("❌", ephemeral=True); return
            inv = await database.get_inventory(str(self.member.id))
            self.parent.items = inv; self.parent.tot = max(1, -(-len(inv) // self.parent.PER_PAG))
            self.parent._build()
            await i.response.edit_message(embed=_embed_lista_deposita(self.dep, inv, self.parent.pagina, self.parent.tot, self.parent.PER_PAG), view=self.parent)

        bc.callback = _custom; bb.callback = _back
        self.add_item(bc); self.add_item(bb)


# ═════════════════════════════════════════════════════════════════════════════
#  SETUP
# ═════════════════════════════════════════════════════════════════════════════
def setup_deposits_commands(bot: commands.Bot):

    @bot.tree.command(name="depgenerici", description="Ritira oggetti da un magazzino fazione")
    @app_commands.describe(deposito="Seleziona il magazzino")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    async def depgenerici(interaction: discord.Interaction, deposito: str):
        await _init()
        if not _ha_accesso(interaction, deposito):
            await interaction.response.send_message(f"❌ Accesso negato al magazzino **{DEPOSITI[deposito]['label']}**.", ephemeral=True); return
        items = await _get_items(deposito)
        if not items:
            await interaction.response.send_message(f"⚠️ Il magazzino **{DEPOSITI[deposito]['label']}** è vuoto.", ephemeral=True); return
        view = PrelievoListaView(bot, interaction.user, deposito, items)
        await interaction.response.send_message(embed=_embed_lista_preleva(deposito, items, 0, view.tot, view.PER_PAG), view=view, ephemeral=True)

    @bot.tree.command(name="mettidepfazione", description="Deposita oggetti in un magazzino fazione")
    @app_commands.describe(deposito="Seleziona il magazzino")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    async def mettidepfazione(interaction: discord.Interaction, deposito: str):
        await _init()
        if not _ha_accesso(interaction, deposito):
            await interaction.response.send_message(f"❌ Accesso negato al magazzino **{DEPOSITI[deposito]['label']}**.", ephemeral=True); return
        inv = await database.get_inventory(str(interaction.user.id))
        if not inv:
            await interaction.response.send_message("⚠️ Il tuo inventario è vuoto.", ephemeral=True); return
        view = DepositaListaView(bot, interaction.user, deposito, inv)
        await interaction.response.send_message(embed=_embed_lista_deposita(deposito, inv, 0, view.tot, view.PER_PAG), view=view, ephemeral=True)

    async def _ac_give(interaction: discord.Interaction, current: str):
        dep = next((o["value"] for o in interaction.data.get("options", []) if o["name"] == "deposito"), None)
        if not dep: return []
        items = await _get_items(dep)
        nomi = [i["item_name"] for i in items]
        return [app_commands.Choice(name=m[:100], value=m) for m in (_fuzzy(current, nomi) if current else nomi)[:25]]

    @bot.tree.command(name="give-item-deposito", description="[Staff] Aggiungi oggetto in un magazzino fazione")
    @app_commands.describe(deposito="Il magazzino", nome="Nome oggetto", quantita="Quantità")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    @app_commands.autocomplete(nome=_ac_give)
    async def give_item_deposito(interaction: discord.Interaction, deposito: str, nome: str, quantita: int):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Solo lo Staff.", ephemeral=True); return
        if quantita <= 0:
            await interaction.response.send_message("❌ Quantità non valida.", ephemeral=True); return
        await _init()
        await _add(deposito, nome, quantita)
        embed = discord.Embed(title="📦  OGGETTO AGGIUNTO AL MAGAZZINO", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="🏢 Struttura", value=DEPOSITI[deposito]["label"], inline=True)
        embed.add_field(name="📦 Oggetto",   value=f"`{nome}`",                 inline=True)
        embed.add_field(name="🔢 Quantità",  value=f"`×{quantita}`",            inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention,    inline=True)
        embed.set_footer(text=f"🏙️ West Coast RP '93 — Depositi  •  {_ora()}")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
