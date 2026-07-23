import discord
from discord import app_commands
from datetime import datetime, timezone
import database
from constants import LOG_CHANNEL_ID

def _criminali_attivi() -> bool:
    try:
        import commands_invoice as _ci
        return _ci._azioni_criminali_attive
    except Exception:
        return True

_MSG_OFFLINE = "❌ Le **azioni criminali** sono attualmente **offline**.\nAttendi che lo Staff le riattivi."

# ⚠️ Manca l'ID del ruolo "Distilleria" nel server: mandamelo e lo inserisco qui.
DISTILL_ROLE_ID = 0

# ── Emoji animate ─────────────────────────────────────────────────────────────
EMOJI_FUOCO       = "<a:fuoco:1529036911870742649>"
EMOJI_CONFERMA    = "<a:conferma:1525966173798142063>"
EMOJI_CARICAMENTO = "<a:caricamento:1525976204128157796>"

# ── Ruoli droghe (dal ruoli server) ───────────────────────────────────────────
DROGA_CONFIG = {
    "🍃 Tabacco":       1525776375108337684,
    "🌿 Marijuana":     1525776513205669958,
    "🍫 Hashish":       1525776690360356954,
    "💉 Eroina":        1525777386279272518,
    "🌱 Peyote":        1525776851342200943,
    "⚪️ LSD":           1525777098424451162,
    "💊 Ecstasy":       1525777174613856277,
    "🥥 Cocaina":       1525777231312322620,
    "❄️ Crack":         1525777301059534940,
    "🧪 Metanfetamina": 1525777352053755914,
}

FALSARIO_ROLE_ID = 1525815621126979624  # Ruolo per creazione armi
ITEM_FORBICI     = "✂️ • Forbici per raccolta"

# Sessioni attive in memoria
_raccolte_attive:          dict = {}
_vendite_attive:           dict = {}
_creazioni_attive:         dict = {}
_distillazioni_attive:     dict = {}
_vendite_moonshine_attive: dict = {}
_creazioni_armi_attive:    dict = {}


def _durata_str(secondi: float) -> str:
    h = int(secondi // 3600)
    m = int((secondi % 3600) // 60)
    s = int(secondi % 60)
    if h > 0:   return f"{h}h {m}min {s}s"
    elif m > 0: return f"{m}min {s}s"
    return f"{s}s"

def _barra(secondi: float, max_s: int = 3600, lunghezza: int = 12) -> str:
    riempita = min(int((secondi / max_s) * lunghezza), lunghezza)
    return "█" * riempita + "░" * (lunghezza - riempita)


ARMI_CHOICES = [
    app_commands.Choice(name="🔫 Pistola",           value="🔫 Pistola"),
    app_commands.Choice(name="🔫 Fucile a Pompa",    value="🔫 Fucile a Pompa"),
    app_commands.Choice(name="🔫 Fucile d'Assalto",  value="🔫 Fucile d'Assalto"),
    app_commands.Choice(name="🗡️ Coltello",          value="🗡️ Coltello"),
    app_commands.Choice(name="💣 Esplosivo",          value="💣 Esplosivo"),
]

DROGA_CHOICES = [
    app_commands.Choice(name="🍃 Tabacco",       value="🍃 Tabacco"),
    app_commands.Choice(name="🌿 Marijuana",     value="🌿 Marijuana"),
    app_commands.Choice(name="🥥 Cocaina",       value="🥥 Cocaina"),
    app_commands.Choice(name="💉 Eroina",        value="💉 Eroina"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  GRUPPO /nero — 12 comandi accorpati in 1 solo comando registrato
#  su Discord (i sottocomandi NON contano verso il limite di 100 comandi)
# ══════════════════════════════════════════════════════════════════════════════
nero_group = app_commands.Group(
    name="nero",
    description="Mercato Nero: raccolta, vendita, produzione illegale"
)
raccolta_group   = app_commands.Group(name="raccolta",           description="Raccolta droga",              parent=nero_group)
vendita_group    = app_commands.Group(name="vendita",            description="Vendita droga",                parent=nero_group)
alcool_group     = app_commands.Group(name="alcool",             description="Creazione alcol clandestino",  parent=nero_group)
distill_group    = app_commands.Group(name="distillazione",      description="Distillazione",                parent=nero_group)
moonshine_group  = app_commands.Group(name="vendita-alcool",     description="Vendita alcol clandestino",    parent=nero_group)
armi_group       = app_commands.Group(name="armi",               description="Costruzione armi [Armeria]",   parent=nero_group)


def setup_theft_commands(bot):

    # ══════════════════════════════════════════════════════════════════════════
    #  /nero raccolta inizia | fine
    # ══════════════════════════════════════════════════════════════════════════

    @raccolta_group.command(name="inizia", description="Inizia una sessione di raccolta droga")
    @app_commands.describe(droga="Tipo di droga da raccogliere", foto="Foto della sessione (OBBLIGATORIA)")
    @app_commands.choices(droga=DROGA_CHOICES)
    async def raccolta_inizia(interaction: discord.Interaction, droga: str, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if uid in _raccolte_attive:
            r = _raccolte_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una raccolta di **{r['droga']}** in corso! Usa `/nero raccolta fine` prima.", ephemeral=True); return
        ruolo_id = DROGA_CONFIG.get(droga)
        if not ruolo_id or not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per raccogliere **{droga}**.", ephemeral=True); return
        if await database.get_item_quantity(uid, ITEM_FORBICI) < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{ITEM_FORBICI}** nello zaino!", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _raccolte_attive[uid] = {"droga": droga, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_CARICAMENTO} 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_CARICAMENTO}",
            description=(
                "*Le mani si sporcano, la raccolta ha inizio...*\n"
                "*Muoviti in silenzio, le FDO potrebbero essere vicine.*\n\u200b"
            ),
            color=discord.Color(0x2E8B57),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧍 Raccoglitore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🌿 Tipo Droga",   value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Sessione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;32m● RACCOLTA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Raccolta | Usa /nero raccolta fine per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @raccolta_group.command(name="fine", description="Termina la sessione di raccolta droga")
    @app_commands.describe(droga="Tipo di droga che stavi raccogliendo")
    @app_commands.choices(droga=DROGA_CHOICES)
    async def raccolta_fine(interaction: discord.Interaction, droga: str):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _raccolte_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna raccolta attiva. Usa `/nero raccolta inizia` prima.", ephemeral=True); return
        sessione = _raccolte_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua raccolta attiva è di **{sessione['droga']}**, non di **{droga}**.", ephemeral=True); return
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _raccolte_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description="*Lo zaino è pieno. Ora sparisci prima che qualcuno ti veda.*\n\u200b",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧍 Raccoglitore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🌿 Droga",        value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata Totale", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso",     value=f"```\n  [{_barra(durata_s)}]\n```",    inline=True)
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Raccolta Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  /nero vendita inizia | fine
    # ══════════════════════════════════════════════════════════════════════════

    @vendita_group.command(name="inizia", description="Inizia una sessione di vendita droga")
    @app_commands.describe(droga="Tipo di droga da vendere", foto="Foto della sessione (OBBLIGATORIA)")
    @app_commands.choices(droga=DROGA_CHOICES)
    async def vendita_inizia(interaction: discord.Interaction, droga: str, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if uid in _vendite_attive:
            v = _vendite_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una vendita di **{v['droga']}** in corso! Usa `/nero vendita fine` prima.", ephemeral=True); return
        ruolo_id = DROGA_CONFIG.get(droga)
        if not ruolo_id or not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per vendere **{droga}**.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _vendite_attive[uid] = {"droga": droga, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_CARICAMENTO} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_CARICAMENTO}",
            description=(
                "*La merce cambia mani nell'ombra. L'affare ha inizio...*\n"
                "*Occhi aperti, la legge potrebbe essere in agguato.*\n\u200b"
            ),
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧍 Venditore",  value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🌿 Tipo Droga", value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Sessione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;33m● VENDITA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Vendita | Usa /nero vendita fine per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @vendita_group.command(name="fine", description="Termina la sessione di vendita droga")
    @app_commands.describe(droga="Tipo di droga che stavi vendendo")
    @app_commands.choices(droga=DROGA_CHOICES)
    async def vendita_fine(interaction: discord.Interaction, droga: str):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _vendite_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna vendita attiva. Usa `/nero vendita inizia` prima.", ephemeral=True); return
        sessione = _vendite_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua vendita attiva è di **{sessione['droga']}**, non di **{droga}**.", ephemeral=True); return
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _vendite_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description="*I soldi sono nelle tasche. L'affare è concluso.*\n\u200b",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧍 Venditore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🌿 Droga",     value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Vendita Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  /nero alcool inizia | fine
    # ══════════════════════════════════════════════════════════════════════════

    @alcool_group.command(name="inizia", description="[Distilleria] Inizia la creazione di una partita di alcol clandestino")
    @app_commands.describe(foto="Foto della sessione (OBBLIGATORIA)")
    async def alcool_inizia(interaction: discord.Interaction, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        alcool = "🥃 Alcol Clandestino"
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True); return
        if uid in _creazioni_attive:
            await interaction.response.send_message(
                f"❌ Hai già una creazione di **{_creazioni_attive[uid]['alcool']}** in corso!\nUsa `/nero alcool fine` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _creazioni_attive[uid] = {"alcool": alcool, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_FUOCO} 𝐂𝐑𝐄𝐀𝐙𝐈𝐎𝐍𝐄 𝐀𝐋𝐂𝐎𝐎𝐋 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_FUOCO}",
            description=(
                "*L'alambicco improvvisato ribolle in garage...*\n"
                "*Il profumo dell'alcol clandestino riempie la stanza.*\n\u200b"
            ),
            color=discord.Color(0xC8860A),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧑‍🏭 Distillatore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🥃 Prodotto",      value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Produzione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;33m● PRODUZIONE IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Distilleria | /nero alcool fine per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @alcool_group.command(name="fine", description="[Distilleria] Termina la creazione di una partita di alcol clandestino")
    async def alcool_fine(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _creazioni_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna creazione in corso. Usa `/nero alcool inizia` prima.", ephemeral=True); return
        sessione = _creazioni_attive[uid]
        alcool   = sessione["alcool"]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _creazioni_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐂𝐑𝐄𝐀𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description="*La partita è pronta. L'odore si diffonde per il garage.*\n\u200b",
            color=discord.Color(0x27AE60),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧑‍🏭 Distillatore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🥃 Prodotto",      value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;32m★ PARTITA PRONTA PER LA CONSEGNA ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Distilleria | Produzione Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  /nero distillazione inizia | fine
    # ══════════════════════════════════════════════════════════════════════════

    @distill_group.command(name="inizia", description="[Distilleria] Inizia una sessione di distillazione")
    @app_commands.describe(foto="Foto della sessione (OBBLIGATORIA)")
    async def distillazione_inizia(interaction: discord.Interaction, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        alcool = "🥃 Alcol Clandestino"
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True); return
        if uid in _distillazioni_attive:
            await interaction.response.send_message(
                f"❌ Hai già una distillazione in corso!\nUsa `/nero distillazione fine` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _distillazioni_attive[uid] = {"alcool": alcool, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_FUOCO} 𝐃𝐈𝐒𝐓𝐈𝐋𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_FUOCO}",
            description=(
                "*Il fuoco arde sotto l'alambicco. Il liquido scorre lentamente...*\n"
                "*Ogni goccia è preziosa. Non sprecare nulla.*\n\u200b"
            ),
            color=discord.Color(0xE74C3C),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧑‍🏭 Distillatore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🔬 Distillato",    value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Distillazione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;31m🔥 DISTILLAZIONE IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Distilleria | /nero distillazione fine per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @distill_group.command(name="fine", description="[Distilleria] Termina la sessione di distillazione")
    async def distillazione_fine(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _distillazioni_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna distillazione in corso. Usa `/nero distillazione inizia` prima.", ephemeral=True); return
        sessione = _distillazioni_attive[uid]
        alcool   = sessione["alcool"]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _distillazioni_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐃𝐈𝐒𝐓𝐈𝐋𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description="*L'alambicco si raffredda. Il distillato è pronto per essere imbottigliato.*\n\u200b",
            color=discord.Color(0x8E44AD),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧑‍🏭 Distillatore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🔬 Distillato",    value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;35m★ DISTILLATO PRONTO PER L'IMBOTTIGLIAMENTO ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Distilleria | Distillazione Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  /nero vendita-alcool inizia | fine
    # ══════════════════════════════════════════════════════════════════════════

    @moonshine_group.command(name="inizia", description="[Distilleria] Inizia una sessione di vendita alcol clandestino")
    @app_commands.describe(foto="Foto della sessione (OBBLIGATORIA)")
    async def moonshine_inizia(interaction: discord.Interaction, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True); return
        if uid in _vendite_moonshine_attive:
            await interaction.response.send_message(
                "❌ Hai già una vendita di **🥃 Alcol Clandestino** in corso!\nUsa `/nero vendita-alcool fine` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _vendite_moonshine_attive[uid] = {"inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_CARICAMENTO} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐀𝐋𝐂𝐎𝐋 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_CARICAMENTO}",
            description=(
                "*Il contrabbandiere carica le casse sul furgone...*\n"
                "*La notte è il momento migliore per i traffici oscuri.*\n\u200b"
            ),
            color=discord.Color(0x4B0082),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧑‍🏭 Distillatore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🥃 Prodotto",      value="**🥃 Alcol Clandestino**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Vendita",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;34m● CONSEGNA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Distilleria | /nero vendita-alcool fine per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @moonshine_group.command(name="fine", description="[Distilleria] Termina la sessione di vendita alcol clandestino")
    async def moonshine_fine(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _vendite_moonshine_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna vendita di alcol in corso. Usa `/nero vendita-alcool inizia` prima.", ephemeral=True); return
        sessione = _vendite_moonshine_attive[uid]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _vendite_moonshine_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐀𝐋𝐂𝐎𝐋 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description="*Le casse sono state consegnate. I soldi scorrono nelle tasche...*\n\u200b",
            color=discord.Color(0x9B59B6),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🧑‍🏭 Distillatore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🥃 Prodotto",      value="**🥃 Alcol Clandestino**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;32m★ CONSEGNA COMPLETATA CON SUCCESSO ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Distilleria | Vendita Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  /nero armi inizia | fine
    # ══════════════════════════════════════════════════════════════════════════

    @armi_group.command(name="inizia", description="[Armeria] Inizia una sessione di costruzione armi")
    @app_commands.describe(arma="Tipo di arma da costruire", foto="Foto della sessione di lavoro (OBBLIGATORIA)")
    @app_commands.choices(arma=ARMI_CHOICES)
    async def armi_inizia(interaction: discord.Interaction, arma: str, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == FALSARIO_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Non hai i permessi per costruire armi.", ephemeral=True); return
        if uid in _creazioni_armi_attive:
            await interaction.response.send_message(
                f"❌ Hai già una costruzione di **{_creazioni_armi_attive[uid]['arma']}** in corso!\n"
                f"Usa `/nero armi fine` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _creazioni_armi_attive[uid] = {"arma": arma, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_FUOCO} 𝐂𝐎𝐒𝐓𝐑𝐔𝐙𝐈𝐎𝐍𝐄 𝐀𝐑𝐌𝐈 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_FUOCO}",
            description=(
                "```\n"
                "  ██╗      █████╗ ██████╗  ██████╗ \n"
                "  ██║     ██╔══██╗██╔══██╗██╔═══██╗\n"
                "  ██║     ███████║██████╔╝██║   ██║\n"
                "  ██║     ██╔══██║██╔══██╗██║   ██║\n"
                "  ███████╗██║  ██║██████╔╝╚██████╔╝\n"
                "  ╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ \n"
                "```\n"
                "*Il banco da lavoro è pronto. Gli attrezzi sono affilati...*\n"
                "*Un'altra arma sta per prendere forma nell'ombra.*\n\u200b"
            ),
            color=discord.Color(0xFF4500),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🔨 Armiere",            value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🔫 Arma in Costruzione", value=f"**{arma}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Costruzione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;31m🔥 COSTRUZIONE IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(
            text="🏙️ West Coast RP '93 — Armeria | Usa /nero armi fine per completare",
            icon_url=member.display_avatar.url
        )
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @armi_group.command(name="fine", description="[Armeria] Termina la sessione di costruzione armi")
    async def armi_fine(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _creazioni_armi_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna costruzione in corso.\nUsa `/nero armi inizia` prima.", ephemeral=True); return
        sessione = _creazioni_armi_attive[uid]
        arma     = sessione["arma"]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _creazioni_armi_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐂𝐎𝐒𝐓𝐑𝐔𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*Il lavoro è finito. L'arma è pronta.*\n"
                "*Una creazione degna di Los Santos è nata dalle mani dell'armiere.*\n\u200b"
            ),
            color=discord.Color(0xFFD700),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🔨 Armiere",         value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🔫 Arma Costruita",  value=f"**{arma}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata Costruzione", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso",           value=f"```\n  [{_barra(durata_s)}]\n```",    inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;33m★ ARMA CONSEGNATA CON SUCCESSO ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(
            text="🏙️ West Coast RP '93 | Costruzione Completata",
            icon_url=interaction.user.display_avatar.url
        )
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── Registra il gruppo (1 solo comando verso il limite di 100) ─────────────
    bot.tree.add_command(nero_group)
