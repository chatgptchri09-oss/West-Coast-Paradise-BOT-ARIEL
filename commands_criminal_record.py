import discord
from discord import app_commands
import database
from constants import has_sceriffo, LOG_CHANNEL_ID


def setup_criminal_record_commands(bot):

    # ── /miafedinapenale ──────────────────────────────────────────────────────
    @bot.tree.command(name="miafedinapenale", description="Visualizza i tuoi precedenti penali")
    async def mia_fedina(interaction: discord.Interaction):
        records = await database.get_criminal_records(str(interaction.user.id))

        embed = discord.Embed(
            title=f"📋 𝐏𝐫𝐞𝐜𝐞𝐝𝐞𝐧𝐭𝐢 𝐏𝐞𝐧𝐚𝐥𝐢 — {interaction.user.display_name}",
            color=discord.Color(0x1565C0),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if not records:
            embed.description = "✅ *Nessun precedente penale registrato. Sei un cittadino modello.*"
            embed.color = discord.Color.green()
        else:
            embed.description = f"⚠️ **{len(records)} precedente/i registrato/i nel sistema.**"
            for r in records[:8]:
                embed.add_field(
                    name=f"🚨 {r['crime']}",
                    value=(
                        f"⚖️ **Sentenza:** {r['sentence']}\n"
                        f"👮 **Agente:** {r['officer']}\n"
                        f"📅 **Data:** {r['created_at']}"
                    ),
                    inline=False
                )
            if len(records) > 8:
                embed.add_field(
                    name="...",
                    value=f"*e altri {len(records) - 8} precedenti non mostrati.*",
                    inline=False
                )

        embed.set_footer(text="🏙️ West Coast RP — Registro Penale LSPD")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /puliziafedinapenale ──────────────────────────────────────────────────
    @bot.tree.command(name="puliziafedinapenale", description="[FDO] Pulisci i precedenti penali di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def pulisci_fedina(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message(
                "❌ Solo le **Forze dell'Ordine** possono usare questo comando.", ephemeral=True
            ); return

        await database.clear_criminal_record(str(cittadino.id))

        embed = discord.Embed(
            title="✅ 𝐏𝐫𝐞𝐜𝐞𝐝𝐞𝐧𝐭𝐢 𝐏𝐞𝐧𝐚𝐥𝐢 𝐀𝐳𝐳𝐞𝐫𝐚𝐭𝐢",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Cittadino", value=cittadino.mention,        inline=True)
        embed.add_field(name="👮 Agente",    value=interaction.user.mention, inline=True)
        embed.add_field(
            name="📋 Stato",
            value="Il registro penale è stato **completamente azzerato** nel sistema LSPD.",
            inline=False
        )
        embed.set_footer(text="🏙️ West Coast RP — Registro Penale LSPD")
        await interaction.response.send_message(embed=embed)

        # DM al cittadino
        try:
            dm = discord.Embed(
                title="✅ I tuoi precedenti penali sono stati azzerati",
                description=(
                    "Le **Forze dell'Ordine** hanno cancellato tutti i tuoi precedenti penali "
                    "dal sistema LSPD.\n\n"
                    "Hai una seconda possibilità — non sprecarla. 🏙️"
                ),
                color=discord.Color.green()
            )
            dm.set_footer(text="🏙️ West Coast RP — LSPD")
            await cittadino.send(embed=dm)
        except Exception:
            pass

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(
                    title="📋 LOG — Precedenti Penali Azzerati",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="👮 Agente",    value=interaction.user.mention, inline=True)
                log.add_field(name="👤 Cittadino", value=cittadino.mention,        inline=True)
                log.set_footer(text="🏙️ West Coast RP — Registro Penale LSPD")
                await ch.send(embed=log)
        except Exception:
            pass
