import discord
from discord import app_commands
import database

AGENCY_ROLE = 1404051965364670545


def has_staff(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == AGENCY_ROLE for r in interaction.user.roles)


def setup_property_commands(bot):
    PROPERTY_TYPES = [
        app_commands.Choice(name="🏡 Villa",           value="Villa"),
        app_commands.Choice(name="🏢 Appartamento",    value="Appartamento"),
        app_commands.Choice(name="🏙️ Attico",          value="Attico"),
        app_commands.Choice(name="🚗 Garage",          value="Garage"),
        app_commands.Choice(name="📦 Magazzino",       value="Magazzino"),
        app_commands.Choice(name="🏢 Ufficio",         value="Ufficio"),
        app_commands.Choice(name="🏚️ Casa Popolare",   value="Casa Popolare"),
        app_commands.Choice(name="🕳️ Bunker",          value="Bunker"),
    ]

    @bot.tree.command(name="daiproprieta", description="Registra una proprietà per un cittadino")
    @app_commands.describe(
        cittadino="Il proprietario",
        nome="Nome della proprietà",
        tipo="Tipo di proprietà",
        luogo="Ubicazione a Los Santos"
    )
    @app_commands.choices(tipo=PROPERTY_TYPES)
    async def dai_proprieta(
        interaction: discord.Interaction,
        cittadino: discord.Member,
        nome: str,
        tipo: str,
        luogo: str
    ):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        await database.add_property(str(cittadino.id), nome, tipo, luogo)
        embed = discord.Embed(
            title="🏡 𝐏𝐫𝐨𝐩𝐫𝐢𝐞𝐭à 𝐑𝐞𝐠𝐢𝐬𝐭𝐫𝐚𝐭𝐚",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Proprietario", value=cittadino.mention, inline=True)
        embed.add_field(name="🏠 Nome",         value=nome,              inline=True)
        embed.add_field(name="🏷️ Tipo",         value=tipo,              inline=True)
        embed.add_field(name="📍 Ubicazione",   value=luogo,             inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Registro Proprietà")
        await interaction.response.send_message(embed=embed)
        try:
            dm = discord.Embed(
                title="🏡 Nuova Proprietà!",
                description=f"Sei diventato proprietario di **{nome}** ({tipo}) a **{luogo}**!",
                color=discord.Color(0x1E90FF)
            )
            await cittadino.send(embed=dm)
        except Exception:
            pass

    @bot.tree.command(name="mie-proprieta", description="Visualizza le tue proprietà a Los Santos")
    async def mie_proprieta(interaction: discord.Interaction):
        props = await database.get_properties(str(interaction.user.id))
        embed = discord.Embed(
            title=f"🏡 𝐏𝐫𝐨𝐩𝐫𝐢𝐞𝐭à 𝐝𝐢 {interaction.user.display_name}",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not props:
            embed.description = "*Non possiedi ancora nessuna proprietà a Los Santos.*"
        else:
            for p in props:
                embed.add_field(
                    name=f"{p['property_type']} — {p['property_name']}",
                    value=f"📍 {p['location']}\n📅 {p['created_at']}",
                    inline=False
                )
        embed.set_footer(text="🏙️ West Coast RP '93 — Registro Proprietà")
        await interaction.response.send_message(embed=embed, ephemeral=True)
