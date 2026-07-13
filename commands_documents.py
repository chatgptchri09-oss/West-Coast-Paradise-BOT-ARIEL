import discord
from discord import app_commands
import database
import aiosqlite
from constants import STATO_ROLE_ID, LOG_CHANNEL_ID, has_sceriffo, DATABASE_NAME, STAFF_ROLE_ID

# ── Ruoli ─────────────────────────────────────────────────────────────────────
STAFF_VEDI_DOC   = {STAFF_ROLE_ID, 1524525114526269470}
FALSARIO_ROLE_ID = 1525816899987046491

def has_stato(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id == STATO_ROLE_ID for r in interaction.user.roles)

def has_staff_doc(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id in STAFF_VEDI_DOC for r in interaction.user.roles)

def has_falsario(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id == FALSARIO_ROLE_ID for r in interaction.user.roles)


# ═════════════════════════════════════════════════════════════════════════════
#  BUILDER EMBED DOCUMENTO
# ═════════════════════════════════════════════════════════════════════════════
def _build_doc_embed(cittadino, emittente, data: dict, foto_url, falso: bool = False):
    if falso:
        titolo = "🪪  DOCUMENTO D'IDENTITÀ — FALSO"
        colore = discord.Color(0x1a1a2e)
        footer = "⚠️ Documento NON autentico — West Coast RP"
    else:
        titolo = "🪪  DOCUMENTO D'IDENTITÀ — LSPD"
        colore = discord.Color(0x1565C0)
        footer = "🏙️ West Coast RP '93 — Ufficio Anagrafe LSPD"

    embed = discord.Embed(title=titolo, color=colore, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=cittadino.display_avatar.url)

    embed.add_field(name="🆔 ID PSN",          value=f"`{data.get('psn_id','—')}`",       inline=True)
    embed.add_field(name="💬 Discord",          value=cittadino.mention,                   inline=True)
    embed.add_field(name="\u200b",              value="\u200b",                            inline=False)
    embed.add_field(name="👤 Nome",             value=data.get("nome","—"),                inline=True)
    embed.add_field(name="👥 Cognome",          value=data.get("cognome","—"),             inline=True)
    embed.add_field(name="📅 Data di Nascita",  value=data.get("data_nascita","—"),        inline=True)
    embed.add_field(name="🎂 Età",              value=str(data.get("eta","—")),            inline=True)
    embed.add_field(name="📍 Residenza",        value=data.get("residenza","—"),           inline=True)
    embed.add_field(name="🌍 Nazionalità",      value=data.get("nazionalita","—"),         inline=True)
    embed.add_field(name="⚧ Sesso",             value=data.get("sesso","—"),               inline=True)
    embed.add_field(name="\u200b",              value="\u200b",                            inline=False)
    embed.add_field(name="💇 Capelli",          value=data.get("capelli","—"),             inline=True)
    embed.add_field(name="👁️ Occhi",            value=data.get("occhi","—"),               inline=True)
    embed.add_field(name="🎨 Carnagione",       value=data.get("carnagione","—"),          inline=True)
    embed.add_field(name="🔍 Segni Particolari",value=data.get("segni","—"),               inline=True)

    if foto_url:
        embed.set_image(url=foto_url)

    embed.add_field(name="🔏 Emesso da", value=emittente.mention if emittente else "—", inline=True)
    if falso:
        embed.add_field(name="⚠️ STATO", value="**🔴 DOCUMENTO FALSO**", inline=True)

    embed.set_footer(text=footer)
    return embed


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW MOSTRA DOCUMENTO
# ═════════════════════════════════════════════════════════════════════════════
class MostraDocumentoView(discord.ui.View):
    def __init__(self, embed_vero, embed_falso, richiedente):
        super().__init__(timeout=300)
        self.embed_vero  = embed_vero
        self.embed_falso = embed_falso
        self.richiedente = richiedente

    @discord.ui.button(label="🪪 Mostra Documento Ufficiale", style=discord.ButtonStyle.success)
    async def mostra_vero(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.richiedente.id:
            await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            content=f"📋 {self.richiedente.mention} mostra il proprio documento.",
            embed=self.embed_vero
        )

    @discord.ui.button(label="🪪 Mostra Documento Falso", style=discord.ButtonStyle.danger)
    async def mostra_falso(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.richiedente.id:
            await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
        if not self.embed_falso:
            await interaction.response.send_message("❌ Non possiedi un documento falso.", ephemeral=True); return
        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            content=f"🪪 {self.richiedente.mention} mostra un documento.",
            embed=self.embed_falso
        )


class MostraDocumentoViewSemplice(discord.ui.View):
    def __init__(self, embed, richiedente):
        super().__init__(timeout=300)
        self.embed = embed; self.richiedente = richiedente

    @discord.ui.button(label="📢 Mostra Documento", style=discord.ButtonStyle.primary)
    async def mostra(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.richiedente.id:
            await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            content=f"📋 {self.richiedente.mention} mostra il proprio documento.",
            embed=self.embed
        )


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 2 e STEP 3
# ═════════════════════════════════════════════════════════════════════════════
class Step2View(discord.ui.View):
    def __init__(self, bot, cittadino, foto_url, emittente, data1, falso=False):
        super().__init__(timeout=300)
        self.bot = bot; self.cittadino = cittadino; self.foto_url = foto_url
        self.emittente = emittente; self.data1 = data1; self.falso = falso

    @discord.ui.button(label="➡️ Continua — Sezione 2", style=discord.ButtonStyle.primary)
    async def apri_step2(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        bot = self.bot; cittadino = self.cittadino; foto_url = self.foto_url
        emittente = self.emittente; data1 = self.data1; falso = self.falso

        class Modal2(discord.ui.Modal, title="📋 Documento — Sezione 2"):
            residenza   = discord.ui.TextInput(label="Residenza",      style=discord.TextStyle.short, required=True,  max_length=80,  placeholder="Es: Viale Grove, Los Santos")
            nazionalita = discord.ui.TextInput(label="Nazionalità",    style=discord.TextStyle.short, required=True,  max_length=50,  placeholder="Es: Americana")
            sesso       = discord.ui.TextInput(label="Sesso",          style=discord.TextStyle.short, required=True,  max_length=10,  placeholder="Uomo / Donna")
            capelli     = discord.ui.TextInput(label="Colore Capelli", style=discord.TextStyle.short, required=True,  max_length=30)
            occhi       = discord.ui.TextInput(label="Colore Occhi",   style=discord.TextStyle.short, required=True,  max_length=30)

            async def on_submit(self2, inter):
                data2 = {"residenza": self2.residenza.value, "nazionalita": self2.nazionalita.value,
                         "sesso": self2.sesso.value, "capelli": self2.capelli.value, "occhi": self2.occhi.value}
                view3 = Step3View(bot, cittadino, foto_url, emittente, {**data1, **data2}, falso)
                await inter.response.send_message("✅ **Sezione 2 completata!** Premi per concludere.", view=view3, ephemeral=True)

        await interaction.response.send_modal(Modal2())


class Step3View(discord.ui.View):
    def __init__(self, bot, cittadino, foto_url, emittente, data12, falso=False):
        super().__init__(timeout=300)
        self.bot = bot; self.cittadino = cittadino; self.foto_url = foto_url
        self.emittente = emittente; self.data12 = data12; self.falso = falso

    @discord.ui.button(label="➡️ Concludi — Sezione 3", style=discord.ButtonStyle.success)
    async def apri_step3(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        bot = self.bot; cittadino = self.cittadino; foto_url = self.foto_url
        emittente = self.emittente; data12 = self.data12; falso = self.falso

        class Modal3(discord.ui.Modal, title="📋 Documento — Sezione 3"):
            carnagione = discord.ui.TextInput(label="Carnagione",        style=discord.TextStyle.short, required=True,  max_length=30)
            segni      = discord.ui.TextInput(label="Segni Particolari", style=discord.TextStyle.short, required=False, max_length=100, placeholder="Lascia vuoto se nessuno")

            async def on_submit(self3, inter):
                full = {**data12, "carnagione": self3.carnagione.value, "segni": self3.segni.value or "Nessuno"}
                try: eta_int = int(full["eta"])
                except: await inter.response.send_message("❌ Età non valida.", ephemeral=True); return

                extra = {k: full.get(k, "—") for k in
                         ["psn_id","data_nascita","nazionalita","capelli","occhi","carnagione","segni"]}

                if falso:
                    await database.set_fake_document(str(cittadino.id), full["nome"], full["cognome"],
                                                     eta_int, full["sesso"], full["residenza"], foto_url, extra=extra)
                    embed = _build_doc_embed(cittadino, emittente, full, foto_url, falso=True)

                    conf = discord.Embed(
                        title="✅ Documento Falso Creato",
                        description=(
                            f"Documento falso registrato per {cittadino.mention}.\n\n"
                            f"**Identità falsa:** `{full['nome']} {full['cognome']}`\n"
                            f"**Età:** `{eta_int}` • **Sesso:** `{full['sesso']}`"
                        ),
                        color=discord.Color(0x1a1a2e), timestamp=discord.utils.utcnow()
                    )
                    conf.set_footer(text="🏙️ West Coast RP '93 — Documenti Falsi")
                    await inter.response.send_message(embed=conf, ephemeral=True)

                    try:
                        dm = discord.Embed(
                            title="🕵️ Hai ricevuto un documento falso",
                            description=(
                                f"Qualcuno ti ha procurato documenti falsi.\n"
                                f"Usali con cautela — la polizia di Los Santos è ovunque.\n\n"
                                f"**Identità falsa:** `{full['nome']} {full['cognome']}`"
                            ),
                            color=discord.Color(0x1a1a2e), timestamp=discord.utils.utcnow()
                        )
                        dm.set_thumbnail(url=cittadino.display_avatar.url)
                        dm.set_footer(text="🏙️ West Coast RP '93 — Documenti Falsi")
                        await cittadino.send(embed=dm)
                    except Exception: pass

                    try:
                        ch = bot.get_channel(LOG_CHANNEL_ID)
                        if ch:
                            log = discord.Embed(title="🕵️ LOG — Documento Falso Creato",
                                                color=discord.Color(0x1a1a2e), timestamp=discord.utils.utcnow())
                            log.add_field(name="🎭 Autore",       value=emittente.mention, inline=True)
                            log.add_field(name="👤 Intestatario", value=cittadino.mention, inline=True)
                            log.add_field(name="📛 Nome Falso",   value=f"`{full['nome']} {full['cognome']}`", inline=True)
                            log.set_footer(text="🏙️ West Coast RP '93 — LOG")
                            await ch.send(embed=log)
                    except Exception: pass

                else:
                    await database.set_document(str(cittadino.id), full["nome"], full["cognome"],
                                                eta_int, full["sesso"], full["residenza"], foto_url, extra=extra)
                    embed = _build_doc_embed(cittadino, emittente, full, foto_url, falso=False)
                    view = MostraDocumentoViewSemplice(embed, inter.user)
                    await inter.response.send_message(
                        content="✅ **Documento registrato con successo!**",
                        embed=embed, view=view, ephemeral=True
                    )
                    try:
                        await cittadino.send(content="📋 Il tuo documento d'identità è stato registrato.", embed=embed)
                    except Exception: pass
                    try:
                        ch = bot.get_channel(LOG_CHANNEL_ID)
                        if ch: await ch.send(embed=embed)
                    except Exception: pass

        await interaction.response.send_modal(Modal3())


# ═════════════════════════════════════════════════════════════════════════════
#  COMANDI
# ═════════════════════════════════════════════════════════════════════════════
def setup_document_commands(bot):

    # ── /documento ────────────────────────────────────────────────────────────
    @bot.tree.command(name="documento", description="[Stato] Registra il documento d'identità ufficiale di un cittadino")
    @app_commands.describe(cittadino="Il cittadino", foto="Foto del personaggio (obbligatoria)")
    async def documento(interaction: discord.Interaction, cittadino: discord.Member, foto: discord.Attachment):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Solo il ruolo **Stato** può emettere documenti.", ephemeral=True); return
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Carica un'immagine valida.", ephemeral=True); return
        if await database.get_document(str(cittadino.id)):
            await interaction.response.send_message(
                f"❌ {cittadino.mention} ha già un documento registrato.\nUsa `/rimuovi-documento` prima.", ephemeral=True); return

        foto_url = foto.url; emittente = interaction.user

        class Modal1(discord.ui.Modal, title="📋 Documento LSPD — Sezione 1"):
            psn_id       = discord.ui.TextInput(label="ID PSN",         style=discord.TextStyle.short, required=True, max_length=50)
            nome         = discord.ui.TextInput(label="Nome",            style=discord.TextStyle.short, required=True, max_length=50)
            cognome      = discord.ui.TextInput(label="Cognome",         style=discord.TextStyle.short, required=True, max_length=50)
            data_nascita = discord.ui.TextInput(label="Data di Nascita", style=discord.TextStyle.short, required=True, max_length=20, placeholder="Es: 14/07/1968")
            eta          = discord.ui.TextInput(label="Età",             style=discord.TextStyle.short, required=True, max_length=3)

            async def on_submit(self, inter):
                data1 = {"psn_id": self.psn_id.value, "nome": self.nome.value, "cognome": self.cognome.value,
                         "data_nascita": self.data_nascita.value, "eta": self.eta.value}
                view2 = Step2View(bot, cittadino, foto_url, emittente, data1, falso=False)
                await inter.response.send_message("✅ **Sezione 1 completata!** Premi per continuare.", view=view2, ephemeral=True)

        await interaction.response.send_modal(Modal1())

    # ── /documento-falso ──────────────────────────────────────────────────────
    @bot.tree.command(name="documento-falso", description="[Mercato Nero] Crea un documento falso per un cittadino")
    @app_commands.describe(cittadino="Il cittadino", foto="Foto falsa del personaggio (obbligatoria)")
    async def documento_falso(interaction: discord.Interaction, cittadino: discord.Member, foto: discord.Attachment):
        if not has_falsario(interaction):
            await interaction.response.send_message("❌ Non hai i permessi per falsificare documenti.", ephemeral=True); return
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Carica un'immagine valida.", ephemeral=True); return
        if await database.get_fake_document(str(cittadino.id)):
            await interaction.response.send_message(
                f"❌ {cittadino.mention} ha già un documento falso registrato.", ephemeral=True); return

        foto_url = foto.url; emittente = interaction.user

        class Modal1F(discord.ui.Modal, title="🕵️ Documento Falso — Sezione 1"):
            psn_id       = discord.ui.TextInput(label="ID PSN Falso",         style=discord.TextStyle.short, required=True, max_length=50)
            nome         = discord.ui.TextInput(label="Nome Falso",            style=discord.TextStyle.short, required=True, max_length=50)
            cognome      = discord.ui.TextInput(label="Cognome Falso",         style=discord.TextStyle.short, required=True, max_length=50)
            data_nascita = discord.ui.TextInput(label="Data di Nascita Falsa", style=discord.TextStyle.short, required=True, max_length=20, placeholder="Es: 03/11/1971")
            eta          = discord.ui.TextInput(label="Età Falsa",             style=discord.TextStyle.short, required=True, max_length=3)

            async def on_submit(self, inter):
                data1 = {"psn_id": self.psn_id.value, "nome": self.nome.value, "cognome": self.cognome.value,
                         "data_nascita": self.data_nascita.value, "eta": self.eta.value}
                view2 = Step2View(bot, cittadino, foto_url, emittente, data1, falso=True)
                await inter.response.send_message("✅ **Sezione 1 completata!** Premi per continuare.", view=view2, ephemeral=True)

        await interaction.response.send_modal(Modal1F())

    # ── /rimuovi-documento ────────────────────────────────────────────────────
    @bot.tree.command(name="rimuovi-documento", description="[Stato] Rimuovi il documento di un cittadino")
    @app_commands.describe(cittadino="Il cittadino", tipo="Tipo di documento")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="📄 Documento Ufficiale", value="vero"),
        app_commands.Choice(name="🕵️ Documento Falso",    value="falso"),
    ])
    async def rimuovi_documento(interaction: discord.Interaction, cittadino: discord.Member, tipo: str = "vero"):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        if tipo == "falso":
            await database.delete_fake_document(str(cittadino.id))
            titolo = "🗑️ Documento Falso Rimosso"
        else:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute("DELETE FROM documents WHERE user_id=?", (str(cittadino.id),))
                await db.commit()
            titolo = "🗑️ Documento Ufficiale Rimosso"
        embed = discord.Embed(title=titolo, color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Cittadino",  value=cittadino.mention,        inline=True)
        embed.add_field(name="🔏 Rimosso da", value=interaction.user.mention, inline=True)
        embed.add_field(name="📋 Tipo",       value=tipo.capitalize(),        inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Anagrafe LSPD")
        await interaction.response.send_message(embed=embed)

    # ── /mostra-documento ─────────────────────────────────────────────────────
    @bot.tree.command(name="mostra-documento", description="Mostra il tuo documento d'identità")
    async def mostra_documento(interaction: discord.Interaction):
        uid = str(interaction.user.id)
        doc      = await database.get_document(uid)
        doc_fake = await database.get_fake_document(uid)
        if not doc and not doc_fake:
            await interaction.response.send_message("❌ Non hai nessun documento registrato.", ephemeral=True); return

        def _parse(d, fake=False):
            extra = d.get("extra") or {}
            return {
                "psn_id": extra.get("psn_id","—"), "nome": d.get("nome","—"),
                "cognome": d.get("cognome","—"), "data_nascita": extra.get("data_nascita","—"),
                "eta": str(d.get("eta","—")), "residenza": d.get("luogo_nascita","—"),
                "nazionalita": extra.get("nazionalita","—"), "sesso": d.get("sesso","—"),
                "capelli": extra.get("capelli","—"), "occhi": extra.get("occhi","—"),
                "carnagione": extra.get("carnagione","—"), "segni": extra.get("segni","—"),
            }

        embed_vero  = _build_doc_embed(interaction.user, interaction.user, _parse(doc), doc.get("foto_url"), False) if doc else None
        embed_falso = _build_doc_embed(interaction.user, interaction.user, _parse(doc_fake), doc_fake.get("foto_url"), True) if doc_fake else None

        if embed_vero and embed_falso:
            anteprima = discord.Embed(
                title="🪪  I TUOI DOCUMENTI",
                description=(
                    "Possiedi **entrambi** i documenti.\n"
                    "Scegli quale mostrare:\n\n"
                    "🟢 **Documento Ufficiale** — Registrato dall'LSPD\n"
                    "🔴 **Documento Falso** — Identità contraffatta"
                ),
                color=discord.Color(0x1565C0), timestamp=discord.utils.utcnow()
            )
            anteprima.set_thumbnail(url=interaction.user.display_avatar.url)
            anteprima.set_footer(text="🏙️ West Coast RP '93 — Solo tu puoi vedere questo pannello")
            await interaction.response.send_message(embed=anteprima, view=MostraDocumentoView(embed_vero, embed_falso, interaction.user), ephemeral=True)
        elif embed_vero:
            await interaction.response.send_message(embed=embed_vero, view=MostraDocumentoViewSemplice(embed_vero, interaction.user), ephemeral=True)
        else:
            anteprima = discord.Embed(title="🪪  I TUOI DOCUMENTI", description="Possiedi solo un **documento falso**.", color=discord.Color(0x1a1a2e))
            await interaction.response.send_message(embed=anteprima, view=MostraDocumentoView(None, embed_falso, interaction.user), ephemeral=True)

    # ── /cercapersona ─────────────────────────────────────────────────────────
    @bot.tree.command(name="cercapersona", description="[FDO] Cerca una persona nel registro LSPD")
    @app_commands.describe(cittadino="Il cittadino da cercare")
    async def cercapersona(interaction: discord.Interaction, cittadino: discord.Member):
        if not (has_sceriffo(interaction) or has_stato(interaction)):
            await interaction.response.send_message("❌ Solo Forze dell'Ordine o Stato.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        doc     = await database.get_document(str(cittadino.id))
        fines   = await database.get_fines(str(cittadino.id))
        records = await database.get_criminal_records(str(cittadino.id))

        embed = discord.Embed(
            title=f"🔍  RICERCA NEL REGISTRO LSPD",
            color=discord.Color(0x1565C0), timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Soggetto", value=f"{cittadino.mention}\n`{cittadino.display_name}`", inline=False)

        if doc:
            embed.add_field(name="📋 Identità Registrata", value=(
                f"**Nome:** `{doc.get('nome','—')} {doc.get('cognome','—')}`\n"
                f"**Età:** `{doc.get('eta','—')}` • **Sesso:** `{doc.get('sesso','—')}`\n"
                f"**Residenza:** `{doc.get('luogo_nascita','—')}`"
            ), inline=False)
            if doc.get("foto_url"): embed.set_image(url=doc["foto_url"])
        else:
            embed.add_field(name="📋 Identità", value="⚠️ *Nessun documento registrato nel sistema.*", inline=False)

        stato_taglie  = f"🔴 `{len(fines)} attive` — Totale: `${sum(f['amount'] for f in fines):,}`" if fines else "🟢 `Nessuna taglia`"
        stato_crimini = f"🔴 `{len(records)} precedenti`" if records else "🟢 `Fedina penale pulita`"

        embed.add_field(name="💰 Taglie",    value=stato_taglie,  inline=True)
        embed.add_field(name="⚖️ Precedenti", value=stato_crimini, inline=True)
        embed.set_footer(text=f"🏙️ West Coast RP '93 — Consultato da: {interaction.user.display_name}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /vedi-documento ───────────────────────────────────────────────────────
    @bot.tree.command(name="vedi-documento", description="[Staff] Visualizza il documento di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def vedi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_staff_doc(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        doc = await database.get_document(str(cittadino.id))
        if not doc:
            await interaction.followup.send(f"❌ {cittadino.mention} non ha un documento registrato.", ephemeral=True); return
        extra = doc.get("extra") or {}
        data = {
            "psn_id": extra.get("psn_id","—"), "nome": doc.get("nome","—"),
            "cognome": doc.get("cognome","—"), "data_nascita": extra.get("data_nascita","—"),
            "eta": str(doc.get("eta","—")), "residenza": doc.get("luogo_nascita","—"),
            "nazionalita": extra.get("nazionalita","—"), "sesso": doc.get("sesso","—"),
            "capelli": extra.get("capelli","—"), "occhi": extra.get("occhi","—"),
            "carnagione": extra.get("carnagione","—"), "segni": extra.get("segni","—"),
        }
        embed = _build_doc_embed(cittadino, interaction.user, data, doc.get("foto_url"))
        await interaction.followup.send(embed=embed, ephemeral=True)
        try:
            dm = discord.Embed(
                title="👁️ Il tuo documento è stato consultato",
                description=f"Lo staff {interaction.user.mention} ha visualizzato il tuo documento d'identità.",
                color=discord.Color(0x1565C0), timestamp=discord.utils.utcnow()
            )
            dm.set_footer(text="🏙️ West Coast RP '93 — LSPD")
            await cittadino.send(embed=dm)
        except Exception: pass
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="👁️ LOG — Documento Consultato",
                                    color=discord.Color(0x1565C0), timestamp=discord.utils.utcnow())
                log.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
                log.add_field(name="👤 Cittadino", value=cittadino.mention,        inline=True)
                log.set_footer(text="🏙️ West Coast RP '93 — LOG")
                await ch.send(embed=log)
        except Exception: pass
