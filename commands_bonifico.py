import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database
from constants import LOG_CHANNEL_ID

LOG_CHANNEL_MONEY_ID = 1459209240450433094

async def _log(bot, channel_id: int, embed: discord.Embed = None):
    try:
        ch = bot.get_channel(channel_id)
        if ch:
            await ch.send(embed=embed)
    except Exception:
        pass


def setup_wallet_commands(bot: commands.Bot):

    # ── /paga ─────────────────────────────────────────────────────────────────
    @bot.tree.command(name="paga", description="Invia denaro tramite pagamento fisico (dalla banca)")
    @app_commands.describe(
        utente="L'utente a cui dare il denaro",
        importo="La cifra da inviare dalla tua banca",
        motivo="Il motivo del pagamento"
    )
    async def paga(interaction: discord.Interaction, utente: discord.Member, importo: int, motivo: str):
        sender_id   = str(interaction.user.id)
        receiver_id = str(utente.id)

        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            return

        try:
            if importo <= 0:
                await interaction.followup.send("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
                return
            if sender_id == receiver_id:
                await interaction.followup.send("❌ Non puoi pagare te stesso!", ephemeral=True)
                return
            if utente.bot:
                await interaction.followup.send("❌ Non puoi pagare un bot!", ephemeral=True)
                return

            sender_data   = await database.get_user(sender_id)
            receiver_data = await database.get_user(receiver_id)

            if sender_data["bank"] < importo:
                await interaction.followup.send(
                    f"❌ Non hai abbastanza fondi in banca! (Saldo: **${sender_data['bank']:,}**)",
                    ephemeral=True
                )
                return

            new_sender_bank   = sender_data["bank"] - importo
            new_receiver_bank = receiver_data["bank"] + importo

            await database.update_balance(sender_id,   bank=new_sender_bank)
            await database.update_balance(receiver_id, bank=new_receiver_bank)

            # DM al destinatario
            try:
                dm = discord.Embed(
                    title="💸 Pagamento Ricevuto!",
                    description=f"Hai ricevuto **${importo:,}** in banca da {interaction.user.mention}.",
                    color=discord.Color.green()
                )
                dm.add_field(name="📝 Motivo", value=f"_{motivo}_", inline=False)
                dm.set_footer(text=f"🏙️ West Coast RP — Il tuo nuovo saldo: ${new_receiver_bank:,}")
                await utente.send(embed=dm)
            except Exception:
                pass

            # Messaggio pubblico nel canale
            await interaction.channel.send(
                f"✅ {interaction.user.mention} ha inviato **${importo:,}** a {utente.mention} per: _{motivo}_"
            )

            await interaction.followup.send(
                f"<a:spunta:1431937738256552036> Pagamento completato! Hai inviato **${importo:,}** a {utente.mention}.\n"
                f"Il tuo nuovo saldo bancario è: **${new_sender_bank:,}**",
                ephemeral=True
            )

            # Log money
            log_embed = discord.Embed(title="💸 LOG PAGAMENTO", color=discord.Color.green())
            log_embed.add_field(name="📤 Mittente",          value=interaction.user.mention, inline=True)
            log_embed.add_field(name="📥 Destinatario",      value=utente.mention,           inline=True)
            log_embed.add_field(name="💰 Importo",           value=f"${importo:,}",          inline=True)
            log_embed.add_field(name="📝 Motivo",            value=motivo[:1024],            inline=False)
            log_embed.add_field(name="💳 Nuovo saldo mitt.", value=f"${new_sender_bank:,}",  inline=True)
            log_embed.add_field(name="💳 Nuovo saldo dest.", value=f"${new_receiver_bank:,}", inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            log_embed.set_footer(text="🏙️ West Coast RP — Money Log")
            await _log(bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)

        except Exception as e:
            print(f"[/paga] Errore: {e}", flush=True)
            err_embed = discord.Embed(title="❌ LOG ERRORE PAGAMENTO", color=discord.Color.dark_red())
            err_embed.add_field(name="Mittente",     value=interaction.user.mention, inline=True)
            err_embed.add_field(name="Destinatario", value=utente.mention,           inline=True)
            err_embed.add_field(name="Importo",      value=f"${importo:,}",          inline=True)
            err_embed.add_field(name="Errore",       value=str(e)[:1000],            inline=False)
            err_embed.timestamp = discord.utils.utcnow()
            err_embed.set_footer(text="🏙️ West Coast RP — Errore")
            await _log(bot, LOG_CHANNEL_ID, embed=err_embed)
            await interaction.followup.send("❌ Errore critico durante il pagamento.", ephemeral=True)
