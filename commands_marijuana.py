import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime
import asyncio

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
SMANTELLATORE_ROLE_ID = 1528868464851157013

# Limite giornaliero di raccolta (grammi/unità)
DAILY_LIMIT = 300

# ══════════════════════════════════════════════════════════════════════════
#  CONFIGURAZIONE DROGHE
#  ⚠️ role_id = 0 significa che manca l'ID del ruolo Discord: mandamelo e lo
#     inserisco. Finché resta 0 quella droga sarà bloccata per tutti.
# ══════════════════════════════════════════════════════════════════════════
DROGHE_CONFIG = {
    "marijuana": {
        "label":        "🌿 Marijuana",
        "role_id":      1525776513205669958,
        "item_richiesto": "✂️ | Forbici Raccolta Marijuana",
        "item_prodotto":  "🌿 | Marijuana",
        "colore":       0x2ecc71,
    },
    "cocaina": {
        "label":        "🥥 Cocaina",
        "role_id":      1525777231312322620,
        "item_richiesto": "⛏️ | Falce Raccolta Cocaina",
        "item_prodotto":  "❄️ | Cocaina Grezza",
        "colore":       0xBEBEBE,
    },
    "tabacco": {
        "label":        "🍃 Tabacco",
        "role_id":      1525776375108337684,  
        "item_richiesto": "✂️ | Cesoie Raccolta Tabacco",
        "item_prodotto":  "🍃 | Foglie di Tabacco",
        "colore":       0x8B5A2B,
    },
    "hashish": {
        "label":        "🍫 Hashish",
        "role_id":      1525776690360356954,  
        "item_richiesto": "🔍 | Setaccio per Estrazione Hashish",
        "item_prodotto":  "🍫 | Hashish",
        "colore":       0x6B3E1F,
    },
    "peyote": {
        "label":        "🌱 Peyote",
        "role_id":      1525776851342200943,  
        "item_richiesto": "🔪 | Coltellino Tascabile per Peyote",
        "item_prodotto":  "🌱 | Peyote",
        "colore":       0x4CAF50,
    },
    "lsd": {
        "label":        "⚪ LSD",
        "role_id":      1525777098424451162,  
        "item_richiesto": "🧪 | Contagocce Chimico per LSD",
        "item_prodotto":  "⚪ | LSD",
        "colore":       0xF5F5F5,
    },
    "ecstasy": {
        "label":        "💊 Ecstasy",
        "role_id":      1525777174613856277,  
        "item_richiesto": "⚙️ | Pressa Manuale per Ecstasy",
        "item_prodotto":  "💊 | Ecstasy",
        "colore":       0xFFC107,
    },
    "crack": {
        "label":        "❄️ Crack",
        "role_id":      1525777301059534940, 
        "item_richiesto": "🥄 | Cucchiaio da Cottura per Crack",
        "item_prodotto":  "❄️ | Crack",
        "colore":       0x87CEEB,
    },
    "metanfetamina": {
        "label":        "🧪 Metanfetamina",
        "role_id":      1525777352053755914,
        "item_richiesto": "🧪 | Kit Chimico per Metanfetamina",
        "item_prodotto":  "🧪 | Metanfetamina",
        "colore":       0x00E5FF,
    },
    "eroina": {
        "label":        "💉 Eroina",
        "role_id":      1525777386279272518, 
        "item_richiesto": "🖋️ | Incisore per Capsule di Oppio",
        "item_prodotto":  "💉 | Eroina",
        "colore":       0x5C4033,
    },
}

_DROGA_CHOICES = [
    app_commands.Choice(name=cfg["label"], value=key)
    for key, cfg in DROGHE_CONFIG.items()
]


def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)


async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass


async def init_marijuana_db():
    """Inizializza la tabella unica per la raccolta di tutte le droghe"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS drug_collection (
                user_id TEXT NOT NULL,
                drug_type TEXT NOT NULL,
                collected_today INTEGER DEFAULT 0,
                last_collection_date TEXT,
                PRIMARY KEY (user_id, drug_type)
            )
        """)
        await db.commit()


async def get_today_collection(user_id: str, drug_type: str) -> int:
    """Ottieni il numero di raccolte odierne per un utente su una specifica droga"""
    today = datetime.now().date().isoformat()

    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT collected_today, last_collection_date FROM drug_collection WHERE user_id = ? AND drug_type = ?",
            (user_id, drug_type)
        ) as cursor:
            result = await cursor.fetchone()

        if not result:
            await db.execute(
                "INSERT INTO drug_collection (user_id, drug_type, collected_today, last_collection_date) VALUES (?, ?, ?, ?)",
                (user_id, drug_type, 0, today)
            )
            await db.commit()
            return 0

        collected, last_date = result

        if last_date != today:
            await db.execute(
                "UPDATE drug_collection SET collected_today = 0, last_collection_date = ? WHERE user_id = ? AND drug_type = ?",
                (today, user_id, drug_type)
            )
            await db.commit()
            return 0

        return collected


async def increment_collection(user_id: str, drug_type: str):
    """Incrementa il contatore di raccolta giornaliera per una droga"""
    today = datetime.now().date().isoformat()

    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE drug_collection SET collected_today = collected_today + 1, last_collection_date = ? WHERE user_id = ? AND drug_type = ?",
            (today, user_id, drug_type)
        )
        await db.commit()


async def add_item_to_inventory(user_id: str, item_name: str):
    """Aggiungi 1 item all'inventario dell'utente"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            new_quantity = result[0] + 1
            await db.execute(
                "UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?",
                (new_quantity, user_id, item_name)
            )
        else:
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)",
                (user_id, item_name, 1)
            )

        await db.commit()


async def has_item_in_inventory(user_id: str, item_name: str) -> bool:
    """Controlla se l'utente ha un item nell'inventario"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        ) as cursor:
            result = await cursor.fetchone()
            return result is not None and result[0] > 0


class CollectDrugButton(discord.ui.Button):
    def __init__(self, drug_key: str):
        cfg = DROGHE_CONFIG[drug_key]
        super().__init__(
            style=discord.ButtonStyle.success,
            label=f"{cfg['label'].split(' ', 1)[0]} Raccogli",
            custom_id=f"collect_{drug_key}"
        )
        self.drug_key = drug_key

    async def callback(self, interaction: discord.Interaction):
        cfg = DROGHE_CONFIG[self.drug_key]
        user_id = str(interaction.user.id)

        if cfg["role_id"] == 0:
            await interaction.response.send_message(
                "❌ Questa droga non è ancora configurata (manca l'ID ruolo). Contatta lo Staff.",
                ephemeral=True
            )
            return

        if not has_role(interaction, cfg["role_id"]):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo necessario per raccogliere {cfg['label']}!",
                ephemeral=True
            )
            return

        if not await has_item_in_inventory(user_id, cfg["item_richiesto"]):
            await interaction.response.send_message(
                f"❌ Ti serve **{cfg['item_richiesto']}** per raccogliere",
                ephemeral=True
            )
            return

        collected_today = await get_today_collection(user_id, self.drug_key)

        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere ancora.",
                ephemeral=True
            )
            return

        for item in self.view.children:
            item.disabled = True

        processing_embed = discord.Embed(
            title=f"{cfg['label']} — Raccolta",
            description="⏳ Raccolta in corso... Attendi 10 secondi.",
            color=cfg["colore"]
        )
        processing_embed.set_footer(text="Non chiudere questo messaggio")

        await interaction.response.edit_message(embed=processing_embed, view=self.view)

        await asyncio.sleep(10)

        await increment_collection(user_id, self.drug_key)
        await add_item_to_inventory(user_id, cfg["item_prodotto"])

        new_total = collected_today + 1

        success_embed = discord.Embed(
            title="✅ Raccolta completata",
            description=f"Hai raccolto 1 unità di {cfg['label']}, in totale oggi ne hai raccolti **{new_total}/{DAILY_LIMIT}**.\n\nL'item è stato aggiunto al tuo inventario.",
            color=cfg["colore"]
        )
        success_embed.set_footer(text="Usa /inventario per vedere il tuo inventario")

        await interaction.edit_original_response(embed=success_embed, view=self.view)


class CollectDrugView(discord.ui.View):
    def __init__(self, bot, drug_key: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.add_item(CollectDrugButton(drug_key))


def setup_marijuana_commands(bot: commands.Bot):

    # ── /raccolta ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="raccolta", description="Raccogli una sostanza (in base al tuo ruolo)")
    @app_commands.describe(droga="La sostanza da raccogliere")
    @app_commands.choices(droga=_DROGA_CHOICES)
    async def raccolta(interaction: discord.Interaction, droga: str):
        cfg = DROGHE_CONFIG[droga]

        if cfg["role_id"] == 0:
            await interaction.response.send_message(
                "❌ Questa droga non è ancora configurata (manca l'ID ruolo). Contatta lo Staff.",
                ephemeral=True
            )
            return

        if not has_role(interaction, cfg["role_id"]):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo necessario per raccogliere {cfg['label']}!",
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)

        if not await has_item_in_inventory(user_id, cfg["item_richiesto"]):
            await interaction.response.send_message(
                f"❌ Ti serve **{cfg['item_richiesto']}** per raccogliere",
                ephemeral=True
            )
            return

        collected_today = await get_today_collection(user_id, droga)

        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere ancora.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{cfg['label']} — Raccolta",
            description=f"Premi il pulsante sottostante per raccogliere 1 unità di {cfg['label']}.",
            color=cfg["colore"]
        )
        embed.add_field(
            name="📊 Progresso giornaliero",
            value=f"**{collected_today}/{DAILY_LIMIT}** raccolti oggi",
            inline=False
        )
        embed.set_footer(text=f"Limite giornaliero: {DAILY_LIMIT}")

        view = CollectDrugView(bot, droga)
        await interaction.response.send_message(embed=embed, view=view)

    # ── /smantellaauto ────────────────────────────────────────────────────────
    @bot.tree.command(name="smantellaauto", description="[SMANTELLATORE] Smantella un veicolo")
    @app_commands.describe(utente="L'utente che sta smantellando il veicolo")
    async def smantellaauto(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, SMANTELLATORE_ROLE_ID):
            await interaction.response.send_message(
                "❌ Devi avere il ruolo per smantellare le auto che ti darà il cartello!",
                ephemeral=True
            )
            return

        await interaction.response.send_message("⏳ Smantellamento avviato, attendi 15 secondi...", ephemeral=True)

        embed_in_progress = discord.Embed(
            title="🔧 Smantellamento in corso...",
            description=f"**{interaction.user.name}** Sta smantellando un veicolo... 🔧",
            color=discord.Color.orange()
        )
        embed_in_progress.add_field(
            name="⏳ Tempo rimanente",
            value="Attendi **15 secondi** per completare l'operazione.",
            inline=False
        )
        embed_in_progress.set_footer(text=f"Oggi alle {datetime.now().strftime('%H:%M')}")

        message = await interaction.channel.send(embed=embed_in_progress)

        await asyncio.sleep(15)

        embed_completed = discord.Embed(
            title="✅ Smantellamento completato!",
            description=f"{utente.mention} ha terminato lo smantellamento del veicolo 🚗💥",
            color=discord.Color.green()
        )
        embed_completed.add_field(
            name="📦 Hai ottenuto i seguenti componenti che sono già stati aggiunti al tuo inventario 🎒:",
            value=(
                "• <:paraurti:1459842286052446416> **2x Paraurti**\n"
                "• <:cerchione:1459842536112918662> **4x Cerchioni**\n"
                "• 📻 **1x Autoradio**"
            ),
            inline=False
        )
        embed_completed.add_field(
            name="💰 Valore totale",
            value="Puoi rivendere questi pezzi al cartello",
            inline=False
        )
        embed_completed.set_footer(text=f"Oggi alle {datetime.now().strftime('%H:%M')}")

        await message.edit(embed=embed_completed)

        await add_item_to_inventory(str(utente.id), "<:paraurti:1459842286052446416> | Paraurti")
        await add_item_to_inventory(str(utente.id), "<:paraurti:1459842286052446416> | Paraurti")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "📻 | Autoradio")

        # LOG


async def setup_marijuana_database():
    await init_marijuana_db()
