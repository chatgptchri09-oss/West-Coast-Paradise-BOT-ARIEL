import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database
from constants import (
    DATABASE_NAME, LOG_CHANNEL_ID, CONCESSIONARIO_ROLE_ID,
    LIBRETTO_PERSONALE_CH, LIBRETTO_AZIENDALE_CH
)

VEHICLE_LOG_CHANNEL_ID = 1414759489998946396
LFD_ROLE_ID = 1524525114526269470
OFFICINA_ROLE_ID = 1415240071216500746
LOG_CHANNEL_MODIFICHE_ID = 1415038985037807746


def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)


async def log_command(bot, channel_id: int, content=None, embed=None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(content=content, embed=embed)
    except Exception as e:
        print(f"Errore nell'invio del log al canale {channel_id}: {e}")


TIPO_VEICOLO_CHOICES = [
    app_commands.Choice(name="🚗 Veicolo personale",  value="personale"),
    app_commands.Choice(name="🏢 Veicolo aziendale",  value="aziendale"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — dati di registrazione veicolo
# ══════════════════════════════════════════════════════════════════════════════
class LibrettoModal(discord.ui.Modal, title="🚗 𝐑𝐞𝐠𝐢𝐬𝐭𝐫𝐚𝐳𝐢𝐨𝐧𝐞 𝐕𝐞𝐢𝐜𝐨𝐥𝐨"):
    nome_cognome = discord.ui.TextInput(
        label="Nome e Cognome cliente",
        placeholder="Es: John Smith",
        required=True, max_length=100
    )
    marca_modello = discord.ui.TextInput(
        label="Marca e Modello veicolo",
        placeholder="Es: Bravado Buffalo",
        required=True, max_length=100
    )
    targa = discord.ui.TextInput(
        label="Targa",
        placeholder="Es: WC93-1234",
        required=True, max_length=20
    )
    prezzo = discord.ui.TextInput(
        label="Prezzo di vendita ($)",
        placeholder="Es: 25000",
        required=True, max_length=10
    )

    def __init__(self, bot, cliente: discord.Member, tipo: str, foto: discord.Attachment):
        super().__init__()
        self.bot     = bot
        self.cliente = cliente
        self.tipo    = tipo
        self.foto    = foto

    async def on_submit(self, interaction: discord.Interaction):
        # ── Validazione ───────────────────────────────────────────────────────
        try:
            prezzo_val = int(self.prezzo.value.replace(",", "").replace("$", "").strip())
            if prezzo_val < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Prezzo non valido. Inserisci un numero intero.", ephemeral=True)
            return

        parti_nome = self.nome_cognome.value.strip().split(maxsplit=1)
        nome_cliente    = parti_nome[0] if parti_nome else self.nome_cognome.value
        cognome_cliente = parti_nome[1] if len(parti_nome) > 1 else ""

        parti_veicolo = self.marca_modello.value.strip().split(maxsplit=1)
        marca_veicolo  = parti_veicolo[0] if parti_veicolo else self.marca_modello.value
        modello_veicolo = parti_veicolo[1] if len(parti_veicolo) > 1 else ""

        targa_val = self.targa.value.strip().upper()

        # Controllo targa duplicata
        esistente = await database.get_vehicle_by_plate(targa_val)
        if esistente:
            await interaction.response.send_message(
                f"❌ Esiste già un veicolo registrato con targa **{targa_val}**!", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        veh_id = await database.add_vehicle(
            user_id=str(self.cliente.id),
            client_name=nome_cliente,
            client_surname=cognome_cliente,
            vehicle_brand=marca_veicolo,
            vehicle_model=modello_veicolo,
            plate=targa_val,
            price=prezzo_val,
            vehicle_type=self.tipo,
            photo_url=self.foto.url,
            registered_by=str(interaction.user.id)
        )

        emoji_tipo  = "🚗" if self.tipo == "personale" else "🏢"
        label_tipo  = "Veicolo Personale" if self.tipo == "personale" else "Veicolo Aziendale"
        canale_id   = LIBRETTO_PERSONALE_CH if self.tipo == "personale" else LIBRETTO_AZIENDALE_CH

        embed = discord.Embed(
            title=f"{emoji_tipo} 𝐋𝐈𝐁𝐑𝐄𝐓𝐓𝐎 𝐃𝐈 𝐂𝐈𝐑𝐂𝐎𝐋𝐀𝐙𝐈𝐎𝐍𝐄 — {label_tipo.upper()}",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=self.cliente.display_avatar.url)
        embed.add_field(name="👤 Proprietario", value=f"{nome_cliente} {cognome_cliente}\n{self.cliente.mention}", inline=True)
        embed.add_field(name="🚙 Veicolo", value=f"{marca_veicolo} {modello_veicolo}".strip(), inline=True)
        embed.add_field(name="🔖 Targa", value=f"`{targa_val}`", inline=True)
        embed.add_field(name="💰 Prezzo di vendita", value=f"${prezzo_val:,}", inline=True)
        embed.add_field(name="🏷️ Tipo", value=label_tipo, inline=True)
        embed.add_field(name="🏪 Venduto da", value=interaction.user.mention, inline=True)
        embed.set_image(url=self.foto.url)
        embed.set_footer(text=f"🏙️ West Coast RP '93 — Libretto #{veh_id}")

        # ── Canale libretto ───────────────────────────────────────────────────
        try:
            canale = self.bot.get_channel(canale_id)
            if canale:
                await canale.send(embed=embed)
        except Exception:
            pass

        # ── DM al cliente ─────────────────────────────────────────────────────
        try:
            dm = discord.Embed(
                title="🚗 Hai ricevuto un nuovo veicolo!",
                description=(
                    f"Il Concessionario ti ha registrato un **{marca_veicolo} {modello_veicolo}**.\n\n"
                    f"🔖 **Targa:** `{targa_val}`\n"
                    f"💰 **Prezzo:** ${prezzo_val:,}\n"
                    f"🏷️ **Tipo:** {label_tipo}\n\n"
                    f"Puoi consultare i tuoi libretti con `/portafoglio`."
                ),
                color=discord.Color(0x1E90FF)
            )
            dm.set_image(url=self.foto.url)
            dm.set_footer(text="🏙️ West Coast RP '93 — Concessionario")
            await self.cliente.send(embed=dm)
        except Exception:
            pass

        await interaction.followup.send(
            f"✅ Veicolo registrato con successo a {self.cliente.mention}! (Libretto #{veh_id})", ephemeral=True
        )

        # ── Log ───────────────────────────────────────────────────────────────
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🚗 LOG — Libretto Registrato", color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
                log.add_field(name="🏪 Venditore", value=interaction.user.mention, inline=True)
                log.add_field(name="👤 Cliente",   value=self.cliente.mention,     inline=True)
                log.add_field(name="🔖 Targa",     value=targa_val,                inline=True)
                await ch.send(embed=log)
        except Exception:
            pass


def setup_vehicle_commands(bot: commands.Bot):

    # ── /dai-libretto ────────────────────────────────────────────────────────
    @bot.tree.command(name="dai-libretto", description="[Concessionario] Registra un veicolo a un cliente")
    @app_commands.describe(
        utente="Il cliente a cui registrare il veicolo",
        tipo="Tipo di veicolo",
        foto_veicolo="Foto del veicolo"
    )
    @app_commands.choices(tipo=TIPO_VEICOLO_CHOICES)
    async def dai_libretto(
        interaction: discord.Interaction,
        utente: discord.Member,
        tipo: str,
        foto_veicolo: discord.Attachment
    ):
        if not has_role(interaction, CONCESSIONARIO_ROLE_ID):
            await interaction.response.send_message("❌ Solo il Concessionario può usare questo comando!", ephemeral=True)
            return
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi registrare un veicolo a un bot.", ephemeral=True)
            return
        if not foto_veicolo.content_type or not foto_veicolo.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
            return

        modal = LibrettoModal(bot, utente, tipo, foto_veicolo)
        await interaction.response.send_modal(modal)

    # ── /controllatarga ──────────────────────────────────────────────────────
    @bot.tree.command(name="controllatarga", description="[LFD] Controlla la targa di un veicolo")
    @app_commands.describe(targa="La targa del veicolo da controllare")
    async def controllatarga(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            vehicle = await database.get_vehicle_by_plate(targa.strip().upper())

            if not vehicle:
                await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"🚗 CONTROLLO TARGA: {vehicle['plate']}",
                color=discord.Color.blue()
            )
            embed.add_field(name="👤 Proprietario", value=f"{vehicle['client_name']} {vehicle['client_surname']} (<@{vehicle['user_id']}>)", inline=False)
            embed.add_field(name="🚙 Veicolo", value=f"{vehicle.get('vehicle_brand','')} {vehicle['vehicle_model']}".strip(), inline=True)
            embed.add_field(name="🔖 Targa", value=vehicle['plate'], inline=True)
            embed.add_field(name="🏷️ Tipo", value="Aziendale" if vehicle.get("vehicle_type") == "aziendale" else "Personale", inline=True)
            embed.add_field(name="📋 Assicurazione", value="✅ Presente" if vehicle['insurance'] else "❌ Assente", inline=False)
            embed.add_field(name="🔧 Modifiche", value=vehicle['modifications'] if vehicle['modifications'] and vehicle['modifications'] != "/////" else "Nessuna", inline=False)

            stato_text = "⚠️ SEQUESTRATO" if vehicle['seized'] else "✅ Regolare"
            if vehicle.get('illegal'):
                stato_text += " 🏴‍☠️ (ILLEGALE)"
            embed.add_field(name="🚨 Stato", value=stato_text, inline=False)
            if vehicle.get("photo_url"):
                embed.set_thumbnail(url=vehicle["photo_url"])

            await interaction.followup.send(embed=embed, ephemeral=True)

            log_embed = discord.Embed(title="🚗 LOG CONTROLLO TARGA", color=discord.Color.blue())
            log_embed.add_field(name="👮 Controllato da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🔖 Targa", value=vehicle['plate'], inline=True)
            log_embed.add_field(name="👤 Proprietario", value=f"{vehicle['client_name']} {vehicle['client_surname']} (<@{vehicle['user_id']}>)", inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in controllatarga: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)

    # ── /assicurazione ───────────────────────────────────────────────────────
    @bot.tree.command(name="assicurazione", description="[OFFICINA] Gestisci l'assicurazione di un veicolo")
    @app_commands.describe(targa="La targa del veicolo", stato="Aggiungi o rimuovi l'assicurazione")
    @app_commands.choices(stato=[
        app_commands.Choice(name="Aggiungi", value="aggiungi"),
        app_commands.Choice(name="Rimuovi", value="rimuovi"),
    ])
    async def assicurazione(interaction: discord.Interaction, targa: str, stato: str):
        if not has_role(interaction, OFFICINA_ROLE_ID):
            await interaction.response.send_message("❌ Solo l'Officina può usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            targa_val = targa.strip().upper()
            vehicle = await database.get_vehicle_by_plate(targa_val)
            if not vehicle:
                await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return

            new_insurance_status = 1 if stato == "aggiungi" else 0
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute("UPDATE vehicle_registrations SET insurance = ? WHERE plate = ?", (new_insurance_status, targa_val))
                await db.commit()

            action = "aggiunta" if stato == "aggiungi" else "rimossa"
            await interaction.followup.send(f"✅ Assicurazione {action} per il veicolo con targa **{targa_val}**!", ephemeral=True)

            log_embed = discord.Embed(
                title=f"📋 ASSICURAZIONE {'AGGIUNTA' if stato == 'aggiungi' else 'RIMOSSA'}",
                color=discord.Color.green() if stato == "aggiungi" else discord.Color.red()
            )
            log_embed.add_field(name="👨‍🔧 Eseguito da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🔖 Targa", value=targa_val, inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MODIFICHE_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in assicurazione: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)

    # ── /modificaveicolo ─────────────────────────────────────────────────────
    @bot.tree.command(name="modificaveicolo", description="[OFFICINA] Modifica un veicolo")
    @app_commands.describe(targa="La targa del veicolo", modifiche="Le modifiche applicate al veicolo")
    async def modificaveicolo(interaction: discord.Interaction, targa: str, modifiche: str):
        if not has_role(interaction, OFFICINA_ROLE_ID):
            await interaction.response.send_message("❌ Solo l'Officina può usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            targa_val = targa.strip().upper()
            vehicle = await database.get_vehicle_by_plate(targa_val)
            if not vehicle:
                await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return

            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute("UPDATE vehicle_registrations SET modifications = ? WHERE plate = ?", (modifiche, targa_val))
                await db.commit()

            await interaction.followup.send(f"✅ Modifiche registrate per il veicolo con targa **{targa_val}**!", ephemeral=True)

            log_embed = discord.Embed(title="🔧 MODIFICA VEICOLO", color=discord.Color.blue())
            log_embed.add_field(name="👨‍🔧 Eseguito da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🔖 Targa", value=targa_val, inline=True)
            log_embed.add_field(name="🔧 Modifiche", value=modifiche[:1024], inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MODIFICHE_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in modificaveicolo: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)

    # ── /sequestraveicolo ────────────────────────────────────────────────────
    @bot.tree.command(name="sequestraveicolo", description="[LFD] Sequestra un veicolo")
    @app_commands.describe(targa="La targa del veicolo da sequestrare")
    async def sequestraveicolo(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            targa_val = targa.strip().upper()
            vehicle = await database.get_vehicle_by_plate(targa_val)
            if not vehicle:
                await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return

            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute("UPDATE vehicle_registrations SET seized = 1 WHERE plate = ?", (targa_val,))
                await db.commit()

            embed = discord.Embed(
                title="<a:sirena:1431792628332101723> VEICOLO SEQUESTRATO",
                description=f"Il veicolo con targa **{targa_val}** è stato contrassegnato come sequestrato.",
                color=discord.Color.red()
            )
            embed.add_field(name="👮 Esecutore", value=interaction.user.mention, inline=True)
            embed.add_field(name="👤 Proprietario Registrato", value=f"{vehicle['client_name']} {vehicle['client_surname']} (<@{vehicle['user_id']}>)", inline=True)
            embed.set_footer(text=f"ID Utente: {interaction.user.id}")

            await interaction.followup.send(f"✅ Veicolo con targa **{targa_val}** sequestrato!", ephemeral=True)
            await log_command(bot, VEHICLE_LOG_CHANNEL_ID, embed=embed)
        except Exception as e:
            print(f"Errore in sequestraveicolo: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)

    # ── /dissequestraveicolo ─────────────────────────────────────────────────
    @bot.tree.command(name="dissequestraveicolo", description="[LFD] Rimuovi il sequestro da un veicolo")
    @app_commands.describe(targa="La targa del veicolo da dissequestrare")
    async def dissequestraveicolo(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            targa_val = targa.strip().upper()
            vehicle = await database.get_vehicle_by_plate(targa_val)
            if not vehicle:
                await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return

            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute("UPDATE vehicle_registrations SET seized = 0 WHERE plate = ?", (targa_val,))
                await db.commit()

            embed = discord.Embed(
                title="<a:si:1433573748891582566> SEQUESTRO RIMOSSO",
                description=f"Il sequestro è stato rimosso dal veicolo con targa **{targa_val}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="👮 Esecutore", value=interaction.user.mention, inline=True)
            embed.add_field(name="👤 Proprietario Registrato", value=f"{vehicle['client_name']} {vehicle['client_surname']} (<@{vehicle['user_id']}>)", inline=True)
            embed.set_footer(text=f"ID Utente: {interaction.user.id}")

            await interaction.followup.send(f"✅ Sequestro rimosso dal veicolo con targa **{targa_val}**!", ephemeral=True)
            await log_command(bot, VEHICLE_LOG_CHANNEL_ID, embed=embed)
        except Exception as e:
            print(f"Errore in dissequestraveicolo: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)

    # ── /rimuovilibretto ─────────────────────────────────────────────────────
    @bot.tree.command(name="rimuovilibretto", description="[LFD] Rimuovi un libretto di circolazione")
    @app_commands.describe(targa="La targa del veicolo")
    async def rimuovilibretto(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            targa_val = targa.strip().upper()
            async with aiosqlite.connect(DATABASE_NAME) as db:
                cursor = await db.execute("DELETE FROM vehicle_registrations WHERE plate = ?", (targa_val,))
                await db.commit()

                if cursor.rowcount > 0:
                    await interaction.followup.send(f"✅ Libretto per il veicolo con targa **{targa_val}** rimosso!", ephemeral=True)

                    log_embed = discord.Embed(title="🗑️ LOG LIBRETTO RIMOSSO", color=discord.Color.red())
                    log_embed.add_field(name="👮 Rimosso da", value=interaction.user.mention, inline=True)
                    log_embed.add_field(name="🔖 Targa", value=targa_val, inline=True)
                    log_embed.timestamp = discord.utils.utcnow()
                    await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
                else:
                    await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa_val}**!", ephemeral=True)
        except Exception as e:
            print(f"Errore in rimuovilibretto: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
