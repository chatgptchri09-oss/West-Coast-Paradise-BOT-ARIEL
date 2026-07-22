import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_sceriffo

# Canale dove viene postato il manifesto dei ricercati
RICERCATI_CHANNEL_ID = 1525157991123390475   # ⚠️ DA AGGIORNARE con il nuovo ID canale GTA
CITTADINI_ROLE_ID    = 1414752091607535727   # ⚠️ DA AGGIORNARE con il nuovo ID ruolo cittadini


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — Modulo Multa
# ══════════════════════════════════════════════════════════════════════════════
class MultaModal(discord.ui.Modal, title="🚔 𝐌𝐨𝐝𝐮𝐥𝐨 𝐝𝐢 𝐌𝐮𝐥𝐭𝐚"):
    luogo = discord.ui.TextInput(
        label="Luogo",
        placeholder="Es: Vinewood Blvd",
        required=True, max_length=100
    )
    nome_cognome = discord.ui.TextInput(
        label="Nome e Cognome multato",
        placeholder="Es: John Smith",
        required=True, max_length=100
    )
    indirizzo = discord.ui.TextInput(
        label="Indirizzo abitazione",
        placeholder="Es: Grove Street 12",
        required=True, max_length=100
    )
    marca_modello = discord.ui.TextInput(
        label="Marca e Modello veicolo",
        placeholder="Es: Bravado Buffalo (lascia vuoto se nessuno)",
        required=False, max_length=100
    )
    violazione = discord.ui.TextInput(
        label="Violazione",
        style=discord.TextStyle.paragraph,
        placeholder="Descrivi la violazione commessa...",
        required=True, max_length=500
    )

    def __init__(self, bot, sospettato: discord.Member, importo: int, foto: discord.Attachment = None):
        super().__init__()
        self.bot        = bot
        self.sospettato = sospettato
        self.importo    = importo
        self.foto       = foto

    async def on_submit(self, interaction: discord.Interaction):
        now = discord.utils.utcnow()
        agente = interaction.user

        await database.add_fine(
            str(self.sospettato.id), self.importo, self.violazione.value, agente.display_name
        )

        embed = discord.Embed(
            title="🚔 𝐌𝐔𝐋𝐓𝐀 𝐄𝐌𝐄𝐒𝐒𝐀",
            color=discord.Color(0x1E90FF),
            timestamp=now
        )
        embed.set_thumbnail(url=self.sospettato.display_avatar.url)
        embed.add_field(name="🕐 Data e Orario",       value=discord.utils.format_dt(now, style='F'), inline=False)
        embed.add_field(name="📍 Luogo",               value=self.luogo.value,                        inline=True)
        embed.add_field(name="🧑 Multato",             value=self.nome_cognome.value,                 inline=True)
        embed.add_field(name="🏠 Indirizzo",           value=self.indirizzo.value,                    inline=False)
        if self.marca_modello.value:
            embed.add_field(name="🚗 Veicolo",         value=self.marca_modello.value,                inline=False)
        embed.add_field(name="📋 Violazione",          value=self.violazione.value,                   inline=False)
        embed.add_field(name="👮 Agente",              value=agente.mention,                          inline=True)
        embed.add_field(name="💰 Multa",               value=f"${self.importo:,}",                    inline=True)
        embed.add_field(name="🎯 Tag Discord",         value=self.sospettato.mention,                 inline=True)
        if self.foto and self.foto.content_type and self.foto.content_type.startswith("image/"):
            embed.set_image(url=self.foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
        await interaction.response.send_message(embed=embed)

        # ── Annuncio nel canale ricercati ─────────────────────────────────────
        try:
            ricercati_ch = self.bot.get_channel(RICERCATI_CHANNEL_ID)
            if ricercati_ch:
                manifesto = discord.Embed(
                    title="🔴 𝐑𝐈𝐂𝐄𝐑𝐂𝐀𝐓𝐎 — 𝐌𝐔𝐋𝐓𝐀 𝐄𝐌𝐄𝐒𝐒𝐀",
                    color=discord.Color.red(),
                    timestamp=now
                )
                manifesto.set_thumbnail(url=self.sospettato.display_avatar.url)
                manifesto.add_field(name="🧑 Nome",      value=self.nome_cognome.value,   inline=True)
                manifesto.add_field(name="💰 Multa",     value=f"${self.importo:,}",      inline=True)
                manifesto.add_field(name="📋 Reato",     value=self.violazione.value,     inline=False)
                manifesto.add_field(name="👮 Emessa da", value=agente.mention,            inline=True)
                if self.foto and self.foto.content_type and self.foto.content_type.startswith("image/"):
                    manifesto.set_image(url=self.foto.url)
                manifesto.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
                await ricercati_ch.send(content=f"<@&{CITTADINI_ROLE_ID}>", embed=manifesto)
        except Exception:
            pass

        # ── DM al sospettato ──────────────────────────────────────────────────
        try:
            await self.sospettato.send(embed=discord.Embed(
                title="🚔 𝐇𝐚𝐢 𝐫𝐢𝐜𝐞𝐯𝐮𝐭𝐨 𝐮𝐧𝐚 𝐦𝐮𝐥𝐭𝐚!",
                description=(
                    f"L'agente **{agente.display_name}** ti ha comminato una multa "
                    f"di **${self.importo:,}** a **{self.luogo.value}**.\n**Violazione:** {self.violazione.value}"
                ),
                color=discord.Color.red()
            ))
        except Exception:
            pass

        # ── Log ───────────────────────────────────────────────────────────────
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — Modulo Arresto
# ══════════════════════════════════════════════════════════════════════════════
class ArrestoModal(discord.ui.Modal, title="⛓️ 𝐌𝐨𝐝𝐮𝐥𝐨 𝐝𝐢 𝐀𝐫𝐫𝐞𝐬𝐭𝐨"):
    luogo = discord.ui.TextInput(
        label="Luogo",
        placeholder="Es: Vinewood Blvd",
        required=True, max_length=100
    )
    nome_cognome = discord.ui.TextInput(
        label="Nome e Cognome arrestato",
        placeholder="Es: John Smith",
        required=True, max_length=100
    )
    indirizzo = discord.ui.TextInput(
        label="Indirizzo abitazione",
        placeholder="Es: Grove Street 12",
        required=True, max_length=100
    )
    reato = discord.ui.TextInput(
        label="Reato / Motivo dell'arresto",
        style=discord.TextStyle.paragraph,
        placeholder="Descrivi il reato commesso...",
        required=True, max_length=500
    )
    durata = discord.ui.TextInput(
        label="Durata pena",
        placeholder="Es: 10 minuti di prigione",
        required=True, max_length=50
    )

    def __init__(self, bot, sospettato: discord.Member, foto: discord.Attachment = None):
        super().__init__()
        self.bot        = bot
        self.sospettato = sospettato
        self.foto       = foto

    async def on_submit(self, interaction: discord.Interaction):
        now    = discord.utils.utcnow()
        agente = interaction.user

        await database.add_arrest(
            str(self.sospettato.id), self.reato.value, self.durata.value, agente.display_name
        )

        embed = discord.Embed(
            title="⛓️ 𝐀𝐑𝐑𝐄𝐒𝐓𝐎 𝐄𝐅𝐅𝐄𝐓𝐓𝐔𝐀𝐓𝐎",
            color=discord.Color(0x8B0000),
            timestamp=now
        )
        embed.set_thumbnail(url=self.sospettato.display_avatar.url)
        embed.add_field(name="🕐 Data e Orario",  value=discord.utils.format_dt(now, style='F'), inline=False)
        embed.add_field(name="📍 Luogo",          value=self.luogo.value,                        inline=True)
        embed.add_field(name="🧑 Arrestato",      value=self.nome_cognome.value,                 inline=True)
        embed.add_field(name="🏠 Indirizzo",      value=self.indirizzo.value,                    inline=False)
        embed.add_field(name="📋 Reato",          value=self.reato.value,                        inline=False)
        embed.add_field(name="⏱️ Durata pena",    value=self.durata.value,                       inline=True)
        embed.add_field(name="👮 Agente",         value=agente.mention,                          inline=True)
        embed.add_field(name="🎯 Tag Discord",    value=self.sospettato.mention,                 inline=True)
        if self.foto and self.foto.content_type and self.foto.content_type.startswith("image/"):
            embed.set_image(url=self.foto.url)
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
        await interaction.response.send_message(embed=embed)

        # ── DM all'arrestato ──────────────────────────────────────────────────
        try:
            await self.sospettato.send(embed=discord.Embed(
                title="⛓️ 𝐒𝐞𝐢 𝐬𝐭𝐚𝐭𝐨 𝐚𝐫𝐫𝐞𝐬𝐭𝐚𝐭𝐨!",
                description=(
                    f"L'agente **{agente.display_name}** ti ha arrestato a **{self.luogo.value}**.\n"
                    f"**Reato:** {self.reato.value}\n**Durata pena:** {self.durata.value}"
                ),
                color=discord.Color(0x8B0000)
            ))
        except Exception:
            pass

        # ── Log ───────────────────────────────────────────────────────────────
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass


def setup_fine_commands(bot):

    # ── /multa ────────────────────────────────────────────────────────────────
    @bot.tree.command(name="multa", description="[FDO] Emetti una multa su un sospettato")
    @app_commands.describe(
        sospettato="Il sospettato",
        importo="Valore della multa",
        foto="Foto del sospettato/verbale (opzionale)"
    )
    async def multa(
        interaction: discord.Interaction,
        sospettato: discord.Member,
        importo: int,
        foto: discord.Attachment = None
    ):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo le FDO possono emettere multe.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)
            return

        modal = MultaModal(bot, sospettato, importo, foto)
        await interaction.response.send_modal(modal)

    # ── /modulo-arresto ───────────────────────────────────────────────────────
    @bot.tree.command(name="modulo-arresto", description="[FDO] Compila il modulo di arresto ufficiale")
    @app_commands.describe(
        sospettato="La persona da arrestare",
        foto="Foto del sospettato/verbale (opzionale)"
    )
    async def modulo_arresto(
        interaction: discord.Interaction,
        sospettato: discord.Member,
        foto: discord.Attachment = None
    ):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo le FDO possono effettuare arresti.", ephemeral=True)
            return
        if sospettato.bot:
            await interaction.response.send_message("❌ Non puoi arrestare un bot.", ephemeral=True)
            return

        modal = ArrestoModal(bot, sospettato, foto)
        await interaction.response.send_modal(modal)

    # ── /paga-multa ───────────────────────────────────────────────────────────
    @bot.tree.command(name="paga-multa", description="Paga le multe a tuo carico")
    async def paga_multa(interaction: discord.Interaction):
        uid   = str(interaction.user.id)
        fines = await database.get_fines(uid)
        if not fines:
            await interaction.response.send_message("✅ Non hai multe attive!", ephemeral=True)
            return
        totale = sum(f["amount"] for f in fines)
        user   = await database.get_user(uid)
        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti.\nTotale multe: **${totale:,}** — Tuoi: **${user['cash']:,}**",
                ephemeral=True
            )
            return
        await database.update_balance(uid, cash=user["cash"] - totale)
        for f in fines:
            await database.pay_fine(f["id"])
        embed = discord.Embed(
            title="✅ 𝐌𝐮𝐥𝐭𝐞 𝐒𝐚𝐥𝐝𝐚𝐭𝐞",
            description=f"Hai pagato **${totale:,}**. Sei tornato in regola con la legge.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /controlla-multa ──────────────────────────────────────────────────────
    @bot.tree.command(name="controlla-multa", description="[FDO] Verifica le multe di un giocatore")
    @app_commands.describe(giocatore="Il giocatore")
    async def controlla_multa(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        fines = await database.get_fines(str(giocatore.id))
        embed = discord.Embed(
            title=f"🚔 𝐌𝐮𝐥𝐭𝐞 𝐝𝐢 {giocatore.display_name}",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        if not fines:
            embed.description = "✅ Nessuna multa attiva."
        else:
            for f in fines:
                embed.add_field(
                    name=f"Multa #{f['id']} — ${f['amount']:,}",
                    value=f"📋 {f['reason']}\n👮 {f['issued_by']}\n📅 {f['created_at']}",
                    inline=False
                )
            embed.add_field(name="💰 Totale", value=f"${sum(f['amount'] for f in fines):,}", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /assegno ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="assegno", description="Emetti un assegno bancario a un altro giocatore")
    @app_commands.describe(
        destinatario="Il giocatore che riceverà i soldi",
        importo="Importo dell'assegno (prelevato dalla tua banca)",
        motivazione="Motivo dell'assegno"
    )
    async def assegno(
        interaction: discord.Interaction,
        destinatario: discord.Member,
        importo: int,
        motivazione: str
    ):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi fare un assegno a te stesso.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        uid      = str(interaction.user.id)
        mittente = await database.get_user(uid)

        if mittente["bank"] < importo:
            await interaction.response.send_message(
                f"❌ Fondi bancari insufficienti!\n"
                f"Importo assegno: **${importo:,}** — Tua banca: **${mittente['bank']:,}**\n"
                f"*(I soldi dell'assegno devono essere in banca, non in contanti.)*",
                ephemeral=True
            )
            return

        dest = await database.get_user(str(destinatario.id))

        await database.update_balance(uid, bank=mittente["bank"] - importo)
        await database.update_balance(str(destinatario.id), bank=dest["bank"] + importo)

        embed = discord.Embed(
            title="🏦 𝐀𝐬𝐬𝐞𝐠𝐧𝐨 𝐄𝐦𝐞𝐬𝐬𝐨",
            color=discord.Color(0x4682B4),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Mittente",     value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 Destinatario", value=destinatario.mention,     inline=True)
        embed.add_field(name="\u200b",           value="\u200b",                inline=False)
        embed.add_field(name="💵 Importo",       value=f"${importo:,}",         inline=True)
        embed.add_field(name="📋 Motivazione",   value=motivazione,             inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Assegno Bancario")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="🏦 Hai ricevuto un assegno!",
                description=(
                    f"**{interaction.user.display_name}** ti ha inviato **${importo:,}** in banca.\n\n"
                    f"**Motivazione:** {motivazione}"
                ),
                color=discord.Color(0x4682B4)
            )
            await destinatario.send(embed=dm)
        except Exception:
            pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
