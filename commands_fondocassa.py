import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_staff, COMPANY_ROLES

COMPANY_EMOJI = {
    "Forze dell'Ordine": "🚔",
    "Sheriff":           "⭐",
    "FBI":               "🕵️",
    "Dottore":           "🏥",
    "Armeria":           "🔫",
    "Concessionario":    "🚗",
    "Bar":               "🍻",
    "Market":            "🛒",
    "Contrabbando":      "🚫",
    "Meccanico":         "🔧",
    "Pegasus":           "✈️",
    "Agenzia Imm.":      "🏠",
    "Banca":             "🏦",
    "Notariato":         "📝",
    "County Donuts":     "🍩",
    "County Impound":    "🚛",
}

_CHOICES = [
    app_commands.Choice(name="🚔 Forze dell'Ordine", value="Forze dell'Ordine"),
    app_commands.Choice(name="⭐ Sheriff",            value="Sheriff"),
    app_commands.Choice(name="🕵️ FBI",               value="FBI"),
    app_commands.Choice(name="🏥 Dottore",            value="Dottore"),
    app_commands.Choice(name="🔫 Armeria",            value="Armeria"),
    app_commands.Choice(name="🚗 Concessionario",     value="Concessionario"),
    app_commands.Choice(name="🍻 Bar",                value="Bar"),
    app_commands.Choice(name="🛒 Market",             value="Market"),
    app_commands.Choice(name="🚫 Contrabbando",       value="Contrabbando"),
    app_commands.Choice(name="🔧 Meccanico",          value="Meccanico"),
    app_commands.Choice(name="✈️ Pegasus",            value="Pegasus"),
    app_commands.Choice(name="🏠 Agenzia Imm.",       value="Agenzia Imm."),
    app_commands.Choice(name="🏦 Banca",              value="Banca"),
    app_commands.Choice(name="📝 Notariato",          value="Notariato"),
    app_commands.Choice(name="🍩 County Donuts",      value="County Donuts"),
    app_commands.Choice(name="🚛 County Impound",     value="County Impound"),
]


def _get_user_companies(member) -> list:
    result = []
    for company, role_id in COMPANY_ROLES.items():
        if isinstance(role_id, list):
            if any(r.id in role_id for r in member.roles):
                result.append(company)
        elif any(r.id == role_id for r in member.roles):
            result.append(company)
    return result


def setup_fondocassa_commands(bot):

    # ── /fondocassa ───────────────────────────────────────────────────────────
    @bot.tree.command(name="fondocassa", description="Visualizza il fondo cassa della tua azienda")
    @app_commands.describe(azienda="Seleziona la tua azienda")
    @app_commands.choices(azienda=_CHOICES)
    async def fondocassa(interaction: discord.Interaction, azienda: str):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if azienda not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte dell'azienda **{azienda}**.", ephemeral=True); return

        amount = await database.get_fondocassa(azienda)
        emoji  = COMPANY_EMOJI.get(azienda, "🏢")
        embed  = discord.Embed(
            title=f"💶 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {azienda}",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name=f"{emoji} Saldo attuale", value=f"**${amount:,}**", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Fondo Cassa")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /deposita-fondocassa ──────────────────────────────────────────────────
    @bot.tree.command(name="deposita-fondocassa", description="Deposita contanti nel fondo cassa della tua azienda")
    @app_commands.describe(azienda="L'azienda", importo="Importo da depositare")
    @app_commands.choices(azienda=_CHOICES)
    async def deposita_fondocassa(interaction: discord.Interaction, azienda: str, importo: int):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if azienda not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte dell'azienda **{azienda}**.", ephemeral=True); return

        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return

        user = await database.get_user(str(interaction.user.id))
        if user["cash"] < importo:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibili: **${user['cash']:,}**", ephemeral=True); return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - importo)
        current = await database.get_fondocassa(azienda)
        await database.update_fondocassa(azienda, current + importo)

        emoji = COMPANY_EMOJI.get(azienda, "🏢")
        embed = discord.Embed(
            title=f"💰 𝐃𝐞𝐩𝐨𝐬𝐢𝐭𝐨 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {azienda}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{emoji} Azienda",   value=azienda,                 inline=True)
        embed.add_field(name="💵 Depositato",       value=f"${importo:,}",         inline=True)
        embed.add_field(name="💼 Nuovo saldo FC",   value=f"${current+importo:,}", inline=True)
        embed.add_field(name="👤 Da",               value=interaction.user.mention, inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Fondo Cassa")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /preleva-fondocassa ───────────────────────────────────────────────────
    @bot.tree.command(name="preleva-fondocassa", description="Preleva dal fondo cassa della tua azienda")
    @app_commands.describe(azienda="L'azienda", importo="Importo da prelevare", motivazione="Motivazione (opzionale)")
    @app_commands.choices(azienda=_CHOICES)
    async def preleva_fondocassa(interaction: discord.Interaction, azienda: str, importo: int, motivazione: str = ""):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if azienda not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte dell'azienda **{azienda}**.", ephemeral=True); return

        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return

        current = await database.get_fondocassa(azienda)
        if current < importo:
            await interaction.response.send_message(
                f"❌ Fondi insufficienti. Disponibili: **${current:,}**", ephemeral=True); return

        await database.update_fondocassa(azienda, current - importo)
        user = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(interaction.user.id), cash=user["cash"] + importo)

        emoji = COMPANY_EMOJI.get(azienda, "🏢")
        embed = discord.Embed(
            title=f"💸 𝐏𝐫𝐞𝐥𝐢𝐞𝐯𝐨 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {azienda}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{emoji} Azienda",    value=azienda,                 inline=True)
        embed.add_field(name="💵 Prelevato",         value=f"${importo:,}",         inline=True)
        embed.add_field(name="💼 Saldo FC rimasto",  value=f"${current-importo:,}", inline=True)
        embed.add_field(name="👤 Da",                value=interaction.user.mention, inline=False)
        if motivazione:
            embed.add_field(name="📋 Motivazione",   value=motivazione,              inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Fondo Cassa")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /saldo-fondocassa ─────────────────────────────────────────────────────
    @bot.tree.command(name="saldo-fondocassa", description="[Staff] Visualizza il saldo di tutti i fondi cassa")
    async def saldo_fondocassa(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Solo lo Staff può vedere tutti i fondi cassa.", ephemeral=True); return
        embed = discord.Embed(
            title="💼 𝐒𝐚𝐥𝐝𝐨 𝐅𝐨𝐧𝐝𝐢 𝐂𝐚𝐬𝐬𝐚 — 𝐓𝐮𝐭𝐭𝐞 𝐥𝐞 𝐀𝐳𝐢𝐞𝐧𝐝𝐞",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        totale = 0
        for azienda, emoji in COMPANY_EMOJI.items():
            amount = await database.get_fondocassa(azienda)
            totale += amount
            embed.add_field(name=f"{emoji} {azienda}", value=f"**${amount:,}**", inline=True)
        embed.add_field(name="💰 Totale Generale", value=f"**${totale:,}**", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Fondo Cassa")
        await interaction.response.send_message(embed=embed, ephemeral=True)
