import discord
from discord import app_commands
from constants import LOG_CHANNEL_ID

def _criminali_attivi() -> bool:
    try:
        import commands_invoice as _ci
        return _ci._azioni_criminali_attive
    except Exception:
        return True

# Ruoli da menzionare sopra l'embed
FDO_PING       = 1404051916140449885
CRIMINALI_PING = 1420468587998478376

# Dati rapine — West Coast RP '93 (tabella ufficiale)
RAPINE = {
    "Persona": {
        "emoji": "🧍",
        "criminali": "Da 1 a 6",
        "fdo": "Da 2 a 7",
        "bottino": "Variabile",
        "armi": "Bianche e Pistole",
        "ostaggi": "1",
        "scassinamento": "0 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Negozio Di Tatuaggi": {
        "emoji": "💉",
        "criminali": "Da 1 a 6",
        "fdo": "Da 2 a 7",
        "bottino": "1'000$",
        "armi": "Pistole",
        "ostaggi": "Da 1 a 2",
        "scassinamento": "5 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Negozio Di Vestiti": {
        "emoji": "👕",
        "criminali": "Da 1 a 6",
        "fdo": "Da 2 a 7",
        "bottino": "1'500$",
        "armi": "Pistole",
        "ostaggi": "Da 1 a 2",
        "scassinamento": "5 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Mini-Market": {
        "emoji": "🏪",
        "criminali": "Da 1 a 6",
        "fdo": "Da 2 a 7",
        "bottino": "3'000$",
        "armi": "Pistole",
        "ostaggi": "Da 1 a 2",
        "scassinamento": "7 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Armeria": {
        "emoji": "🔫",
        "criminali": "Da 1 a 6",
        "fdo": "Da 2 a 7",
        "bottino": "8'000$ + 2 Pistole",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 3",
        "scassinamento": "10 Minuti",
        "tetti": "SÌ",
        "fdo_speciali": "SÌ",
    },
    "Banca Fleeca": {
        "emoji": "🏦",
        "criminali": "Da 1 a 8",
        "fdo": "Da 2 a 9",
        "bottino": "30'000$",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 4",
        "scassinamento": "15 Minuti",
        "tetti": "SÌ",
        "fdo_speciali": "SÌ",
    },
    "Portavalori": {
        "emoji": "🚚",
        "criminali": "Da 1 a 8",
        "fdo": "Da 2 a 9",
        "bottino": "Variabile",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 4",
        "scassinamento": "10 Minuti",
        "tetti": "NO",
        "fdo_speciali": "SÌ",
    },
    "Banca Paleto Bay": {
        "emoji": "🏛️",
        "criminali": "Da 1 a 8",
        "fdo": "Da 2 a 9",
        "bottino": "100'000$",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 5",
        "scassinamento": "20 Minuti",
        "tetti": "SÌ",
        "fdo_speciali": "SÌ",
    },
}


def setup_robbery_commands(bot):

    @bot.tree.command(name="rapina", description="Avvia una rapina a Los Santos (azione illegale)")
    @app_commands.describe(bersaglio="Scegli il tipo di rapina")
    @app_commands.choices(bersaglio=[
        app_commands.Choice(name="🧍 Persona",              value="Persona"),
        app_commands.Choice(name="💉 Negozio Di Tatuaggi",  value="Negozio Di Tatuaggi"),
        app_commands.Choice(name="👕 Negozio Di Vestiti",   value="Negozio Di Vestiti"),
        app_commands.Choice(name="🏪 Mini-Market",          value="Mini-Market"),
        app_commands.Choice(name="🔫 Armeria",              value="Armeria"),
        app_commands.Choice(name="🏦 Banca Fleeca",         value="Banca Fleeca"),
        app_commands.Choice(name="🚚 Portavalori",          value="Portavalori"),
        app_commands.Choice(name="🏛️ Banca Paleto Bay",     value="Banca Paleto Bay"),
    ])
    async def rapina(interaction: discord.Interaction, bersaglio: str):
        if not _criminali_attivi():
            await interaction.response.send_message(
                "❌ Le **azioni criminali** sono attualmente **offline**.\nAttendi che lo Staff le riattivi.",
                ephemeral=True)
            return
        r = RAPINE[bersaglio]

        embed = discord.Embed(
            title=f"{r['emoji']} 𝐑𝐀𝐏𝐈𝐍𝐀 — {bersaglio.upper()}",
            color=discord.Color(0x8B0000),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="👥 Criminali richiesti", value=r["criminali"],     inline=True)
        embed.add_field(name="🚔 FDO richieste",       value=r["fdo"],           inline=True)
        embed.add_field(name="💰 Bottino",             value=r["bottino"],       inline=False)
        embed.add_field(name="🔫 Armi consentite",     value=r["armi"],          inline=True)
        embed.add_field(name="🙋 Ostaggi",             value=r["ostaggi"],       inline=True)
        embed.add_field(name="⏱️ Tempo scassinamento", value=r["scassinamento"], inline=True)
        embed.add_field(name="🏠 Accesso tetti",       value=r["tetti"],         inline=True)
        embed.add_field(name="⭐ FDO speciali",        value=r["fdo_speciali"],  inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Rapina")

        ping_content = f"<@&{FDO_PING}> <@&{CRIMINALI_PING}>"
        await interaction.response.send_message(content=ping_content, embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(
                    title="🚨 𝐋𝐎𝐆 𝐑𝐀𝐏𝐈𝐍𝐀",
                    color=discord.Color(0x8B0000),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="👤 Avviata da", value=interaction.user.mention, inline=True)
                log.add_field(name="🎯 Tipo",        value=bersaglio,               inline=True)
                await ch.send(embed=log)
        except Exception:
            pass
